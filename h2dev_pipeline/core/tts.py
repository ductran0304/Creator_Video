"""Tạo giọng đọc cho từng câu thoại. Cache theo nội dung (giọng + tốc độ + câu) nên sửa một câu
chỉ phải đọc lại đúng câu đó. Kèm file .words.json (mốc thời gian từng từ do edge-tts trả về) cho phụ đề karaoke.

Nhiều giọng: scenes.json có "voices": {"chu_tiem": {"voice": "vi-VN-HoaiMyNeural", "rate": "+6%", "name": "Chủ tiệm"}}
và câu thoại ghi "speaker": "chu_tiem"; câu không có speaker dùng giọng người dẫn (voice/voice_rate của project)."""
import asyncio
import hashlib
import json
import os
import shlex
import subprocess

import edge_tts

DEFAULT_VOICES = {"en": "en-US-EmmaNeural", "vi": "vi-VN-HoaiMyNeural"}


def pick_voice(project, cfg):
    lang = project.get("language", "en")
    voice = project.get("voice") or cfg.get("voice_name") or DEFAULT_VOICES[lang]
    if not voice.lower().startswith(f"{lang}-"):
        voice = DEFAULT_VOICES[lang]
    return voice


def _key(*parts):
    return hashlib.sha1("\x1f".join(parts).encode("utf-8")).hexdigest()[:16]


def words_path(audio_path):
    return os.path.splitext(audio_path)[0] + ".words.json"


def load_words(audio_path):
    """[(giây bắt đầu, giây kết thúc, từ)] tính từ đầu file audio, hoặc None nếu chưa có."""
    p = words_path(audio_path)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return [tuple(w) for w in json.load(f)]


async def _edge_one(text, voice, rate, path, sem, retries=5):
    async with sem:
        for attempt in range(retries):
            try:
                tmp = path + ".part"
                words = []
                with open(tmp, "wb") as f:
                    async for chunk in edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary").stream():
                        if chunk["type"] == "audio":
                            f.write(chunk["data"])
                        elif chunk["type"] == "WordBoundary":  # offset/duration theo đơn vị 100 ns
                            st = chunk["offset"] / 1e7
                            words.append((round(st, 3), round(st + chunk["duration"] / 1e7, 3), chunk["text"]))
                if os.path.getsize(tmp) < 500:
                    raise RuntimeError("file audio rỗng")
                os.replace(tmp, path)
                with open(words_path(path), "w", encoding="utf-8") as f:
                    json.dump(words, f, ensure_ascii=False)
                return
            except Exception as e:  # mạng chập chờn → thử lại
                if attempt == retries - 1:
                    raise RuntimeError(f"edge-tts lỗi sau {retries} lần với câu: {text[:60]!r} ({e})")
                await asyncio.sleep(2 * (attempt + 1))


def _omnivoice_one(text, path, cfg):
    cmd = [t.strip('"') for t in shlex.split(cfg.get("omnivoice_cli_path", "python -m omnivoice"),
                                             posix=(os.name != "nt"))]
    cmd += ["--text", text, "--ref_audio", cfg.get("omnivoice_ref_audio", "ref_voice.wav"), "--output", path]
    for flag, key in (("--model", "omnivoice_model"), ("--language", "omnivoice_language"),
                      ("--ref_text", "omnivoice_ref_text")):
        if cfg.get(key):
            cmd += [flag, cfg[key]]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def voice_for(project, cfg, speaker=None):
    """(voice, rate) của người dẫn hoặc của speaker khai báo trong project["voices"]."""
    base_voice = pick_voice(project, cfg)
    base_rate = project.get("voice_rate") or cfg.get("voice_rate", "+0%")
    v = (project.get("voices") or {}).get(speaker) if speaker else None
    if not v:
        return base_voice, base_rate
    voice = v.get("voice") or base_voice
    lang = project.get("language", "en")
    if not voice.lower().startswith(f"{lang}-"):
        voice = base_voice
    return voice, v.get("rate", base_rate)


def synthesize(texts, cache_dir, project, cfg, log=print, concurrency=4):
    """texts: list câu thoại (str) hoặc (câu, speaker) → list đường dẫn audio tương ứng (theo thứ tự)."""
    os.makedirs(cache_dir, exist_ok=True)
    use_omni = cfg.get("use_omnivoice", False)
    items = [(t, None) if isinstance(t, str) else tuple(t) for t in texts]
    voice, rate = voice_for(project, cfg)
    engine = "omnivoice" if use_omni else f"edge:{voice}:{rate}"
    ext = ".wav" if use_omni else ".mp3"
    per = []  # (text, voice, rate, path)
    for t, spk in items:
        v, r = (voice, rate) if use_omni else voice_for(project, cfg, spk)
        eng = "omnivoice" if use_omni else f"edge:{v}:{r}"
        per.append((t, v, r, os.path.join(cache_dir, _key(eng, t) + ext)))
    paths = [p for *_, p in per]
    todo = [(t, v, r, p) for t, v, r, p in per if not (os.path.exists(p) and os.path.getsize(p) > 500)]
    n_voices = len({(v, r) for _, v, r, _ in per})
    extra = f" + {n_voices - 1} giọng khác" if n_voices > 1 else ""
    log(f"[TTS] {engine}{extra} — {len(texts) - len(todo)} câu có sẵn trong cache, cần đọc {len(todo)} câu")
    if not todo:
        return paths
    if use_omni:
        for i, (t, _v, _r, p) in enumerate(todo, 1):
            try:
                _omnivoice_one(t, p, cfg)
            except Exception as e:
                log(f"  [!] OmniVoice lỗi ({e}) → dùng edge-tts cho câu này")
                asyncio.run(_edge_one(t, voice, rate, p.replace(".wav", ".mp3"), asyncio.Semaphore(1)))
                os.replace(p.replace(".wav", ".mp3"), p)
            log(f"  {i}/{len(todo)}")
        return paths

    async def run():
        sem = asyncio.Semaphore(concurrency)
        done = 0

        async def one(t, v, r, p):
            nonlocal done
            await _edge_one(t, v, r, p, sem, retries=2)
            done += 1
            if done % 10 == 0 or done == len(todo):
                log(f"  [TTS] {done}/{len(todo)}")
        results = await asyncio.gather(*(one(*it) for it in todo), return_exceptions=True)
        failed = [it for it, res in zip(todo, results) if isinstance(res, Exception)]
        if failed:
            # edge-tts hay chập chờn khi gửi dồn ("No audio was received"): thử lại lần lượt từng câu, nghỉ lâu hơn
            log(f"  [TTS] {len(failed)} câu lỗi tạm thời — thử lại lần lượt...")
            one_by_one = asyncio.Semaphore(1)
            for t, v, r, p in failed:
                await asyncio.sleep(1.5)
                await _edge_one(t, v, r, p, one_by_one, retries=6)
    asyncio.run(run())
    return paths
