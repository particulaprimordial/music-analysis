"""Scale-derived algorithmic harmony, melody and open-ended ascension studies."""
from __future__ import annotations

import math
import random
from pathlib import Path

import mido

from .theory import SCALES, diatonic_chord, parse_tonic, scale_intervals

PROGRESSION_TEMPLATES = {
    "01 · Tonic departure": (0, 5, 3, 6),
    "02 · Descending cycle": (0, 3, 6, 2),
    "03 · Submediant field": (5, 3, 4, 0),
    "04 · Relative orbit": (3, 0, 5, 6),
    "05 · Open dominant field": (0, 6, 5, 2),
    "06 · Half-diminished color": (1, 0, 3, 5),
    "07 · Mediant return": (3, 5, 0, 6),
}
ALGORITHMS = ["Mirror / reflection", "Modular permutation", "Fibonacci residues",
              "Prime residues", "Logistic map", "Bounded random walk", "Cyclic pendulum"]
EXTENSION_CYCLE = [7, 9, 11, 13]


def _melody_degrees(length: int, scale_size: int, algorithm: int, seed: int) -> list[int]:
    rng = random.Random(seed)
    if algorithm == 0:
        period = max(2, scale_size * 2 - 2)
        seq = [i % period for i in range(length)]
        return [v if v < scale_size else period - v for v in seq]
    if algorithm == 1:
        a = 5 if scale_size != 5 else 2
        return [(a * i + 3) % scale_size for i in range(length)]
    if algorithm == 2:
        a, b, out = 0, 1, []
        for _ in range(length):
            out.append(a % scale_size)
            a, b = b, a + b
        return out
    if algorithm == 3:
        primes = []
        n = 2
        while len(primes) < length:
            if all(n % p for p in range(2, int(math.sqrt(n)) + 1)):
                primes.append(n)
            n += 1
        return [p % scale_size for p in primes]
    if algorithm == 4:
        x, r, out = 0.2718, 3.91, []
        for _ in range(length):
            x = r * x * (1 - x)
            out.append(min(scale_size - 1, int(x * scale_size)))
        return out
    if algorithm == 5:
        pos, out = scale_size // 2, []
        for _ in range(length):
            pos = max(0, min(scale_size - 1, pos + rng.choice([-2, -1, 1, 2])))
            out.append(pos)
        return out
    out = []
    pos = 0
    direction = 1
    for i in range(length):
        if i % max(3, scale_size) == 0:
            direction *= -1
        pos = (pos + direction + (1 if rng.random() < 0.18 else 0)) % scale_size
        out.append(pos)
    return out


def _pitch_for_degree(tonic_pc: int, intervals: tuple[int, ...], degree: int, octave: int = 5) -> int:
    n = len(intervals)
    cycle, idx = divmod(degree, n)
    return 12 * (octave + 1 + cycle) + tonic_pc + intervals[idx]


def make_progression_midi(tonic: str, scale_name: str, progression_name: str,
                          bpm: float = 112, algorithm_index: int = 0,
                          seed: int = 42) -> tuple[mido.MidiFile, list[dict]]:
    if scale_name not in SCALES:
        raise ValueError(f"Unknown scale: {scale_name}")
    degrees = PROGRESSION_TEMPLATES[progression_name]
    intervals = scale_intervals(scale_name)
    tonic_pc = parse_tonic(tonic)
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    harmony = mido.MidiTrack()
    melody = mido.MidiTrack()
    mid.tracks.extend([harmony, melody])
    harmony.append(mido.MetaMessage("track_name", name=f"Harmony · {progression_name}", time=0))
    harmony.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    harmony.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    melody.append(mido.MetaMessage("track_name", name=f"Melody · {ALGORITHMS[algorithm_index]}", time=0))
    chord_events = []
    labels = []
    for bar in range(8):
        degree = degrees[bar % 4] % len(intervals)
        extension = EXTENSION_CYCLE[(bar + algorithm_index) % len(EXTENSION_CYCLE)]
        pitches, label = diatonic_chord(tonic, scale_name, degree, extension, octave=3)
        labels.append({"bar": bar + 1, "degree": degree + 1, "extension": extension, "chord": label})
        start = bar * 4 * 480
        end = start + int(3.88 * 480)
        for pitch in pitches:
            chord_events.append((start, 1, mido.Message("note_on", note=min(108, pitch), velocity=65,
                                                        channel=0, time=0)))
            chord_events.append((end, 0, mido.Message("note_off", note=min(108, pitch), velocity=0,
                                                      channel=0, time=0)))
    previous = 0
    for tick, _priority, msg in sorted(chord_events, key=lambda x: (x[0], x[1])):
        msg.time = max(0, tick - previous)
        harmony.append(msg)
        previous = tick
    harmony.append(mido.MetaMessage("end_of_track", time=1))

    # Eight eighth-notes per bar, 64 total notes across an eight-bar study.
    seq = _melody_degrees(64, len(intervals), algorithm_index, seed + algorithm_index)
    melody_events = []
    for i, degree in enumerate(seq):
        start = round(i * 0.5 * 480)
        duration = round((0.34 + (0.06 if i % 4 == 3 else 0.0)) * 480)
        pitch = _pitch_for_degree(tonic_pc, intervals, degree, octave=5)
        velocity = 62 + ((i * 7 + algorithm_index * 5) % 19)
        melody_events.append((start, 1, mido.Message("note_on", note=min(108, pitch), velocity=velocity,
                                                    channel=1, time=0)))
        melody_events.append((start + duration, 0, mido.Message("note_off", note=min(108, pitch),
                                                               velocity=0, channel=1, time=0)))
    previous = 0
    for tick, _priority, msg in sorted(melody_events, key=lambda x: (x[0], x[1])):
        msg.time = max(0, tick - previous)
        melody.append(msg)
        previous = tick
    melody.append(mido.MetaMessage("end_of_track", time=1))
    return mid, labels


def make_ascension_midi(tonic: str, scale_name: str, bpm: float = 72,
                        bars: int = 64) -> mido.MidiFile:
    """Create an extensible pedal-based study with a deliberately open ending."""
    if bars < 8 or bars > 512:
        raise ValueError("bars must be between 8 and 512")
    intervals = scale_intervals(scale_name)
    tonic_pc = parse_tonic(tonic)
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Ascension · sustained field", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    # Long drone tones: tonic and fifth-degree scale tone.
    base = 12 * 4 + tonic_pc
    fifth = base + (intervals[min(4, len(intervals) - 1)])
    total_ticks = bars * 4 * 480
    events = []
    for pitch, velocity in ((base, 48), (fifth, 36)):
        events.append((0, 1, mido.Message("note_on", note=pitch, velocity=velocity, channel=0, time=0)))
        events.append((total_ticks, 0, mido.Message("note_off", note=pitch, velocity=0, channel=0, time=0)))
    # A slowly shifting upper voice cycles through the scale without landing on tonic at the end.
    for bar in range(bars):
        idx = (bar * 3 + (bar // 7)) % len(intervals)
        pitch = 12 * 6 + tonic_pc + intervals[idx]
        start = bar * 4 * 480
        duration = int(3.65 * 480)
        events.append((start, 1, mido.Message("note_on", note=min(108, pitch), velocity=42 + bar % 12,
                                              channel=1, time=0)))
        events.append((start + duration, 0, mido.Message("note_off", note=min(108, pitch), velocity=0,
                                                         channel=1, time=0)))
    # Finish on a scale degree other than the tonic; the piece remains open-ended.
    end_pitch = 12 * 6 + tonic_pc + intervals[1 % len(intervals)]
    events.append((total_ticks - 1, 1, mido.Message("note_on", note=min(108, end_pitch), velocity=46,
                                                  channel=1, time=0)))
    events.append((total_ticks + int(3.8 * 480), 0, mido.Message("note_off", note=min(108, end_pitch),
                                                               velocity=0, channel=1, time=0)))
    previous = 0
    for tick, priority, msg in sorted(events, key=lambda x: (x[0], x[1])):
        msg.time = max(0, tick - previous)
        track.append(msg)
        previous = tick
    track.append(mido.MetaMessage("end_of_track", time=1))
    return mid


def generate_composition_pack(tonic: str, scale_name: str, output_dir: str | Path,
                              bpm: float = 112, ascension_bpm: float = 72,
                              ascension_bars: int = 32) -> list[dict]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for i, (name, _degrees) in enumerate(PROGRESSION_TEMPLATES.items()):
        mid, chords = make_progression_midi(tonic, scale_name, name, bpm, i)
        safe = name.split("·", 1)[0].strip().replace(" ", "_")
        filename = f"{tonic}_{scale_name.replace(' ', '_')}_{safe}_study.mid"
        path = out / filename
        mid.save(path)
        records.append({"type": "progression", "name": name, "filename": filename,
                        "bpm": bpm, "chords": chords, "algorithm": ALGORITHMS[i]})
    asc = make_ascension_midi(tonic, scale_name, ascension_bpm, ascension_bars)
    asc_name = f"{tonic}_{scale_name.replace(' ', '_')}_ascension.mid"
    asc.save(out / asc_name)
    records.append({"type": "ascension", "name": "Open-ended ascension", "filename": asc_name,
                    "bpm": ascension_bpm, "bars": ascension_bars})
    return records
