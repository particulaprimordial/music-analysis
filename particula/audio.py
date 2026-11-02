"""Lightweight reference renderer and audio feature measurements.

The built-in renderer is deliberately labelled a reference synth. REAPER or a
SoundFont-based renderer should be used for production-quality arrangements.
"""
from __future__ import annotations

import math
import shutil
import subprocess
import wave
from pathlib import Path

import mido
import numpy as np

from .midi_tools import _absolute_note_events


def _tempo_map(mid: mido.MidiFile):
    events = []
    for track in mid.tracks:
        tick = 0
        for msg in track:
            tick += msg.time
            if msg.is_meta and msg.type == "set_tempo":
                events.append((tick, msg.tempo))
    events.sort(key=lambda x: x[0])
    compact = [(0, 500000)]
    for tick, tempo in events:
        if compact[-1][0] == tick:
            compact[-1] = (tick, tempo)
        elif compact[-1][1] != tempo:
            compact.append((tick, tempo))
    return compact


def _tick_to_seconds(tick: int, ppq: int, tempo_map) -> float:
    seconds = 0.0
    for i, (start_tick, tempo) in enumerate(tempo_map):
        if tick <= start_tick:
            break
        end_tick = min(tick, tempo_map[i + 1][0] if i + 1 < len(tempo_map) else tick)
        seconds += max(0, end_tick - start_tick) * (tempo / 1_000_000.0) / ppq
        if tick <= end_tick:
            break
    return seconds


def midi_notes_seconds(path: str | Path):
    mid = mido.MidiFile(str(path))
    tempo_map = _tempo_map(mid)
    notes = []
    for track in mid.tracks:
        for note in _absolute_note_events(track, mid.ticks_per_beat):
            start = _tick_to_seconds(note["start_tick"], mid.ticks_per_beat, tempo_map)
            end = _tick_to_seconds(note["end_tick"], mid.ticks_per_beat, tempo_map)
            notes.append((start, max(start + 0.025, end), note["pitch"], note["velocity"], note["channel"]))
    return notes


def render_reference_wav(midi_path: str | Path, wav_path: str | Path,
                          sample_rate: int = 22050, max_seconds: float = 240.0) -> Path:
    notes = midi_notes_seconds(midi_path)
    if not notes:
        raise ValueError("No notes available for audio rendering")
    duration = min(max_seconds, max(end for _start, end, *_ in notes) + 0.5)
    total = max(1, int(duration * sample_rate))
    left = np.zeros(total, dtype=np.float32)
    right = np.zeros(total, dtype=np.float32)
    # A soft additive tone with a short attack and release; not a piano sample library.
    harmonics = ((1, 1.0), (2, 0.24), (3, 0.08), (4, 0.035))
    for start, end, pitch, velocity, channel in notes:
        start_idx = max(0, int(start * sample_rate))
        end_idx = min(total, int(end * sample_rate))
        count = end_idx - start_idx
        if count < 2:
            continue
        t = np.arange(count, dtype=np.float32) / sample_rate
        freq = 440.0 * (2.0 ** ((pitch - 69) / 12.0))
        tone = np.zeros(count, dtype=np.float32)
        for harmonic, weight in harmonics:
            tone += weight * np.sin(2 * np.pi * freq * harmonic * t)
        attack = min(0.025, max(0.004, (end - start) * 0.12))
        decay = min(0.18, max(0.02, (end - start) * 0.3))
        release = min(0.16, max(0.02, (end - start) * 0.25))
        envelope = np.ones(count, dtype=np.float32) * 0.58
        a = min(count, int(attack * sample_rate))
        d = min(max(0, count - a), int(decay * sample_rate))
        r = min(count, int(release * sample_rate))
        if a:
            envelope[:a] = np.linspace(0.0, 1.0, a, endpoint=False, dtype=np.float32)
        if d:
            envelope[a:a+d] = np.linspace(1.0, 0.58, d, endpoint=False, dtype=np.float32)
        if r:
            envelope[-r:] *= np.linspace(1.0, 0.0, r, dtype=np.float32)
        amp = min(1.0, max(0.05, velocity / 110.0)) * 0.12
        sample = tone * envelope * amp
        # Subtle pitch-dependent stereo spread.
        pan = 0.5 + 0.18 * math.sin(pitch * 0.41)
        left[start_idx:end_idx] += sample * math.sqrt(1.0 - pan)
        right[start_idx:end_idx] += sample * math.sqrt(pan)
    peak = max(float(np.max(np.abs(left))), float(np.max(np.abs(right))), 1e-8)
    scale = min(0.92 / peak, 1.0)
    stereo = np.stack((left * scale, right * scale), axis=1)
    pcm = np.clip(stereo * 32767, -32768, 32767).astype("<i2")
    out = Path(wav_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return out


def wav_to_mp3(wav_path: str | Path, mp3_path: str | Path) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg was not found. Install FFmpeg to create MP3 files; WAV export remains available.")
    out = Path(mp3_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(wav_path),
                    "-codec:a", "libmp3lame", "-qscale:a", "3", str(out)],
                   check=True, capture_output=True, text=True)
    return out


def audio_features(audio_path: str | Path) -> dict:
    """Compute basic mono signal measurements from WAV PCM data."""
    with wave.open(str(audio_path), "rb") as wf:
        channels, sample_width, sample_rate, frames = (wf.getnchannels(), wf.getsampwidth(),
                                                       wf.getframerate(), wf.getnframes())
        raw = wf.readframes(frames)
    if sample_width == 2:
        data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    elif sample_width == 4:
        data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
    elif sample_width == 1:
        data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128) / 128.0
    else:
        raise ValueError(f"Unsupported WAV sample width: {sample_width}")
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if not len(data):
        raise ValueError("Audio file is empty")
    peak = float(np.max(np.abs(data)))
    rms = float(np.sqrt(np.mean(data ** 2)))
    zcr = float(np.mean(np.abs(np.diff(np.signbit(data)))))
    frame_len = min(4096, max(256, 2 ** int(math.floor(math.log2(min(len(data), 4096))))))
    frames_arr = [data[i:i+frame_len] for i in range(0, len(data) - frame_len + 1, frame_len)]
    centroids = []
    if frames_arr:
        freqs = np.fft.rfftfreq(frame_len, 1 / sample_rate)
        for frame in frames_arr[:500]:
            mag = np.abs(np.fft.rfft(frame * np.hanning(frame_len)))
            denom = float(mag.sum())
            if denom > 0:
                centroids.append(float((freqs * mag).sum() / denom))
    return {"sample_rate": sample_rate, "channels": channels, "duration_seconds": len(data) / sample_rate,
            "peak": peak, "rms": rms, "zero_crossing_rate": zcr,
            "spectral_centroid_hz_mean": float(np.mean(centroids)) if centroids else 0.0}
