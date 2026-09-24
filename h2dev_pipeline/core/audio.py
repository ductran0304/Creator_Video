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


def trim_silence(x, thresh=0.01, keep=0.05, sr=SR):
    """Cắt khoảng lặng đầu/cuối của một câu TTS (giữ lại `keep` giây) để nhịp đọc đều, tự điều khiển bằng gap."""
    idx = np.flatnonzero(np.abs(x) > thresh)
    if not len(idx):
        return x
    pad = int(keep * sr)
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]


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


def write_wav(path, x, sr=SR):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
