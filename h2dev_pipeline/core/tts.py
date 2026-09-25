"""Tạo giọng đọc cho từng câu thoại. Cache theo nội dung (giọng + tốc độ + câu) nên sửa một câu
chỉ phải đọc lại đúng câu đó."""
import asyncio
import hashlib
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


async def _edge_one(text, voice, rate, path, sem, retries=5):
    async with sem:
        for attempt in range(retries):
            try:
                tmp = path + ".part"
                await edge_tts.Communicate(text, voice, rate=rate).save(tmp)
                if os.path.getsize(tmp) < 500:
                    raise RuntimeError("file audio rỗng")
                os.replace(tmp, path)
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


def synthesize(texts, cache_dir, project, cfg, log=print, concurrency=4):
    """texts: list câu thoại → list đường dẫn audio tương ứng (theo thứ tự)."""
    os.makedirs(cache_dir, exist_ok=True)
    use_omni = cfg.get("use_omnivoice", False)
    voice = pick_voice(project, cfg)
    rate = project.get("voice_rate") or cfg.get("voice_rate", "+0%")
    engine = "omnivoice" if use_omni else f"edge:{voice}:{rate}"
    ext = ".wav" if use_omni else ".mp3"
    paths = [os.path.join(cache_dir, _key(engine, t) + ext) for t in texts]
    todo = [(t, p) for t, p in zip(texts, paths) if not (os.path.exists(p) and os.path.getsize(p) > 500)]
    log(f"[TTS] {engine} — {len(texts) - len(todo)} câu có sẵn trong cache, cần đọc {len(todo)} câu")
    if not todo:
        return paths
    if use_omni:
        for i, (t, p) in enumerate(todo, 1):
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

        async def one(t, p):
            nonlocal done
            await _edge_one(t, voice, rate, p, sem, retries=2)
            done += 1
            if done % 10 == 0 or done == len(todo):
                log(f"  [TTS] {done}/{len(todo)}")
        results = await asyncio.gather(*(one(t, p) for t, p in todo), return_exceptions=True)
        failed = [(t, p) for (t, p), r in zip(todo, results) if isinstance(r, Exception)]
        if failed:
            # edge-tts hay chập chờn khi gửi dồn ("No audio was received"): thử lại lần lượt từng câu, nghỉ lâu hơn
            log(f"  [TTS] {len(failed)} câu lỗi tạm thời — thử lại lần lượt...")
            one_by_one = asyncio.Semaphore(1)
            for t, p in failed:
                await asyncio.sleep(1.5)
                await _edge_one(t, voice, rate, p, one_by_one, retries=6)
    asyncio.run(run())
    return paths
