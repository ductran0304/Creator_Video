"""Âm thanh: giải mã bằng ffmpeg (đi kèm imageio-ffmpeg) và trộn bằng numpy."""
import subprocess
import wave

import imageio_ffmpeg
import numpy as np

SR = 44100
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def decode(path, sr=SR):
    """File audio bất kỳ → mảng float32 mono ở tần số sr."""
    out = subprocess.run([FFMPEG, "-v", "error", "-i", path, "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(out, dtype=np.float32).copy()


def trim_silence(x, thresh=0.01, keep=0.05, sr=SR, with_lead=False):
    """Cắt khoảng lặng đầu/cuối của một câu TTS (giữ lại `keep` giây) để nhịp đọc đều, tự điều khiển bằng gap.
    with_lead=True → trả thêm số giây đã cắt ở đầu (để dời mốc thời gian từng từ)."""
    idx = np.flatnonzero(np.abs(x) > thresh)
    if not len(idx):
        return (x, 0.0) if with_lead else x
    pad = int(keep * sr)
    a = max(0, idx[0] - pad)
    y = x[a: min(len(x), idx[-1] + pad)]
    return (y, a / sr) if with_lead else y


def silence(seconds, sr=SR):
    return np.zeros(int(round(seconds * sr)), dtype=np.float32)


def place(track, clip, start_s, gain=1.0, sr=SR):
    i = int(round(start_s * sr))
    if i >= len(track):
        return
    n = min(len(clip), len(track) - i)
    track[i:i + n] += clip[:n] * gain


def loop_to(x, n):
    if not len(x):
        return np.zeros(n, dtype=np.float32)
    reps = int(np.ceil(n / len(x)))
    return np.tile(x, reps)[:n]


def fade(x, fade_in=0.0, fade_out=0.0, sr=SR):
    x = x.copy()
    a, b = int(fade_in * sr), int(fade_out * sr)
    if a:
        x[:a] *= np.linspace(0, 1, a, dtype=np.float32)
    if b:
        x[-b:] *= np.linspace(1, 0, b, dtype=np.float32)
    return x


def normalize(x, peak=0.95):
    """Đưa đỉnh về `peak` (tăng hoặc giảm) để video đủ to mà không vỡ tiếng."""
    m = float(np.max(np.abs(x))) if len(x) else 0
    return x * (peak / m) if m > 0 else x


def limit(x, peak=0.97):
    m = float(np.max(np.abs(x))) if len(x) else 0
    return x * (peak / m) if m > peak else x


def default_page_flip(sr=SR, seed=7):
    """Tiếng lật trang tổng hợp (nhiễu lọc thấp + đường bao) — dùng khi không có file sfx_page.wav."""
    rng = np.random.default_rng(seed)
    n = int(0.4 * sr)
    noise = np.convolve(rng.uniform(-1, 1, n), np.ones(12) / 12, mode="same")
    t = np.arange(n) / sr
    env = np.where(t < 0.12, np.sin(np.pi * t / 0.24), np.exp(-(t - 0.12) * 8))
    env *= 0.85 + 0.15 * np.sin(2 * np.pi * 50 * t)
    return (noise * env * 0.9).astype(np.float32)


def default_pop(sr=SR):
    """Tiếng 'pop' ngắn khi hiện thành phần mới — dùng khi không có file sfx_pop.wav."""
    n = int(0.09 * sr)
    t = np.arange(n) / sr
    freq = 900 - 5500 * t  # quét từ cao xuống thấp
    phase = 2 * np.pi * np.cumsum(freq) / sr
    return (np.sin(phase) * np.exp(-t * 45) * 0.8).astype(np.float32)


def _env(t, attack, decay):
    return np.where(t < attack, t / max(attack, 1e-4), np.exp(-(t - attack) * decay))


def sfx_whoosh(sr=SR, seed=3):
    """Tiếng 'vút' khi vào B-roll: nhiễu lọc thông dải, cường độ phồng lên rồi tắt."""
    rng = np.random.default_rng(seed)
    n = int(0.45 * sr)
    t = np.arange(n) / sr
    noise = rng.uniform(-1, 1, n)
    low = np.convolve(noise, np.ones(18) / 18, mode="same")
    band = low - np.convolve(low, np.ones(90) / 90, mode="same")
    env = np.sin(np.pi * np.clip(t / 0.45, 0, 1)) ** 2.2
    return (band * env * 2.2).astype(np.float32)


def sfx_ding(sr=SR, f=1318.5):
    """Tiếng 'ding' khi tick checklist."""
    n = int(0.6 * sr)
    t = np.arange(n) / sr
    tone = np.sin(2 * np.pi * f * t) + 0.45 * np.sin(2 * np.pi * 2 * f * t) + 0.2 * np.sin(2 * np.pi * 3.01 * f * t)
    return (tone * _env(t, 0.004, 7) * 0.35).astype(np.float32)


def sfx_thud(sr=SR):
    """Tiếng 'thụp' trầm khi hiện con số / chữ to."""
    n = int(0.35 * sr)
    t = np.arange(n) / sr
    f = 110 * np.exp(-t * 9) + 45
    body = np.sin(2 * np.pi * np.cumsum(f) / sr)
    click = np.random.default_rng(5).uniform(-1, 1, n) * np.exp(-t * 180) * 0.3
    return ((body * _env(t, 0.003, 14) + click) * 0.9).astype(np.float32)


def sfx_paper(sr=SR, seed=11):
    """Tiếng giấy sột soạt ngắn khi hiện một thẻ."""
    rng = np.random.default_rng(seed)
    n = int(0.22 * sr)
    t = np.arange(n) / sr
    noise = rng.uniform(-1, 1, n)
    hp = noise - np.convolve(noise, np.ones(6) / 6, mode="same")
    grain = 0.6 + 0.4 * np.sign(np.sin(2 * np.pi * 60 * t + rng.uniform(0, 6)))
    return (hp * grain * _env(t, 0.01, 22) * 0.5).astype(np.float32)


def sfx_scribble(sr=SR, seconds=0.8, seed=13):
    """Tiếng bút dạ sột soạt khi vẽ tay (hiệu ứng vẽ dần)."""
    rng = np.random.default_rng(seed)
    n = int(seconds * sr)
    t = np.arange(n) / sr
    noise = rng.uniform(-1, 1, n)
    hp = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
    strokes = 0.5 + 0.5 * np.sin(2 * np.pi * 7 * t + 2 * np.sin(2 * np.pi * 1.3 * t))
    env = np.clip(t / 0.05, 0, 1) * np.clip((seconds - t) / 0.1, 0, 1)
    return (hp * strokes * env * 0.18).astype(np.float32)


def speech_envelope(voice, sr=SR, win=0.25, thresh=0.02):
    """0..1 theo thời gian: 1 khi đang có giọng đọc (đã làm mượt) — dùng để giảm nhạc nền khi có lời."""
    hop = int(sr * 0.05)
    n = len(voice) // hop + 1
    pad = np.zeros(n * hop, dtype=np.float32)
    pad[:len(voice)] = np.abs(voice)
    act = (pad.reshape(n, hop).max(axis=1) > thresh).astype(np.float32)
    k = max(1, int(win / 0.05))
    act = np.clip(np.convolve(act, np.ones(2 * k + 1) / (2 * k + 1), mode="same") * 2.0, 0, 1)
    return np.interp(np.arange(len(voice)), np.arange(n) * hop, act).astype(np.float32)


def write_wav(path, x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
