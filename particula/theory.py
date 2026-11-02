"""Transposable scale and diatonic-extension utilities.

Scale definitions are interval recipes in semitones. They are independent of tonic.
The catalogue is intentionally extensible; no finite list can represent every scale
used across musical cultures and tuning systems.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import mido

NOTE_TO_PC = {
    "C": 0, "B#": 0,
    "C#": 1, "Db": 1,
    "D": 2,
    "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4,
    "E#": 5, "F": 5,
    "F#": 6, "Gb": 6,
    "G": 7,
    "G#": 8, "Ab": 8,
    "A": 9,
    "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11,
}
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]

SCALES: dict[str, tuple[int, ...]] = {
    "Major (Ionian)": (0, 2, 4, 5, 7, 9, 11),
    "Natural Minor (Aeolian)": (0, 2, 3, 5, 7, 8, 10),
    "Harmonic Minor": (0, 2, 3, 5, 7, 8, 11),
    "Melodic Minor (ascending)": (0, 2, 3, 5, 7, 9, 11),
    "Dorian": (0, 2, 3, 5, 7, 9, 10),
    "Phrygian": (0, 1, 3, 5, 7, 8, 10),
    "Lydian": (0, 2, 4, 6, 7, 9, 11),
    "Mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "Locrian": (0, 1, 3, 5, 6, 8, 10),
    "Major Pentatonic": (0, 2, 4, 7, 9),
    "Minor Pentatonic": (0, 3, 5, 7, 10),
    "Major Blues": (0, 2, 3, 4, 7, 9),
    "Minor Blues": (0, 3, 5, 6, 7, 10),
    "Whole Tone": (0, 2, 4, 6, 8, 10),
    "Diminished (whole-half)": (0, 2, 3, 5, 6, 8, 9, 11),
    "Diminished (half-whole)": (0, 1, 3, 4, 6, 7, 9, 10),
    "Double Harmonic Major": (0, 1, 4, 5, 7, 8, 11),
    "Hungarian Minor": (0, 2, 3, 6, 7, 8, 11),
    "Neapolitan Minor": (0, 1, 3, 5, 7, 8, 11),
    "Phrygian Dominant": (0, 1, 4, 5, 7, 8, 10),
    "Chromatic": tuple(range(12)),
}


def parse_tonic(tonic: str) -> int:
    """Return pitch class for a note name such as C, F# or Bb."""
    value = tonic.strip().replace("♯", "#").replace("♭", "b")
    if value not in NOTE_TO_PC:
        raise ValueError(f"Unsupported tonic '{tonic}'. Use a note name such as C, F# or Bb.")
    return NOTE_TO_PC[value]


def midi_note_name(note: int, prefer_flats: bool = False, include_octave: bool = True) -> str:
    names = FLAT_NAMES if prefer_flats else SHARP_NAMES
    name = names[int(note) % 12]
    return f"{name}{int(note) // 12 - 1}" if include_octave else name


def scale_intervals(scale_name: str) -> tuple[int, ...]:
    try:
        return SCALES[scale_name]
    except KeyError as exc:
        raise ValueError(f"Unknown scale '{scale_name}'. Available: {', '.join(SCALES)}") from exc


def scale_midi_notes(tonic: str, scale_name: str, octaves: int = 2, start_octave: int = 4) -> list[int]:
    if octaves < 1 or octaves > 6:
        raise ValueError("octaves must be between 1 and 6")
    base = 12 * (start_octave + 1) + parse_tonic(tonic)
    intervals = scale_intervals(scale_name)
    notes = [base + 12 * octave + interval for octave in range(octaves) for interval in intervals]
    notes.append(base + 12 * octaves)
    return notes


def make_scale_midi(tonic: str, scale_name: str, bpm: float = 90, octaves: int = 2,
                    start_octave: int = 4, note_beats: float = 0.85) -> mido.MidiFile:
    if bpm <= 0 or note_beats <= 0:
        raise ValueError("bpm and note_beats must be positive")
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name=f"{tonic} {scale_name}", time=0))
    track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
    step = 1.0
    notes = scale_midi_notes(tonic, scale_name, octaves, start_octave)
    events: list[tuple[int, int, mido.Message]] = []
    for i, pitch in enumerate(notes + list(reversed(notes[:-1]))):
        start = round(i * step * mid.ticks_per_beat)
        end = round((i * step + note_beats) * mid.ticks_per_beat)
        events.append((start, 1, mido.Message("note_on", note=pitch, velocity=82, channel=0, time=0)))
        events.append((end, 0, mido.Message("note_off", note=pitch, velocity=0, channel=0, time=0)))
    previous = 0
    for tick, _priority, msg in sorted(events, key=lambda x: (x[0], x[1])):
        msg.time = max(0, tick - previous)
        track.append(msg)
        previous = tick
    track.append(mido.MetaMessage("end_of_track", time=1))
    return mid


def _stacked_scale_pitches(tonic_pc: int, intervals: tuple[int, ...], degree: int,
                           tone_count: int, octave: int = 3) -> list[int]:
    """Stack alternate scale degrees; wraps scale cycles into higher octaves."""
    base = 12 * (octave + 1) + tonic_pc
    count = len(intervals)
    root_cycle, root_idx = divmod(degree, count)
    pitches = []
    for k in range(tone_count):
        raw_index = root_idx + 2 * k
        cycle, idx = divmod(raw_index, count)
        pitches.append(base + 12 * (root_cycle + cycle) + intervals[idx])
    return pitches


def chord_symbol(pitches: Iterable[int], prefer_flats: bool = False) -> str:
    values = list(pitches)
    if not values:
        return "N.C."
    root = values[0]
    intervals = sorted({(p - root) % 12 for p in values})
    triad = intervals[:]
    if 4 in triad and 7 in triad:
        quality = ""
    elif 3 in triad and 7 in triad:
        quality = "m"
    elif 3 in triad and 6 in triad:
        quality = "dim"
    elif 4 in triad and 8 in triad:
        quality = "aug"
    elif 5 in triad and 7 in triad:
        quality = "sus4"
    else:
        quality = "(scale)"
    if len(values) >= 7:
        ext = "13"
    elif len(values) == 6:
        ext = "11"
    elif len(values) == 5:
        ext = "9"
    elif len(values) == 4:
        seventh = (values[3] - root) % 12
        if seventh == 11:
            ext = "maj7"
        elif seventh == 10:
            ext = "7"
        elif seventh == 9:
            ext = "6"
        else:
            ext = "7"
    else:
        ext = ""
    return f"{midi_note_name(root, prefer_flats, False)}{quality}{ext}"


def diatonic_chord(tonic: str, scale_name: str, degree: int, extension: int = 7,
                   octave: int = 3) -> tuple[list[int], str]:
    """Return a diatonic tertian chord using 3/4/5/6/7 stacked scale tones.

    extension is one of 3, 7, 9, 11, 13. For non-heptatonic scales, stacked
    thirds are cycled through the available scale degrees; the result remains
    a scale-derived sonority, though conventional chord labels may be approximate.
    """
    tone_counts = {3: 3, 7: 4, 9: 5, 11: 6, 13: 7}
    if extension not in tone_counts:
        raise ValueError("extension must be one of 3, 7, 9, 11 or 13")
    pitches = _stacked_scale_pitches(parse_tonic(tonic), scale_intervals(scale_name), degree,
                                    tone_counts[extension], octave)
    return pitches, chord_symbol(pitches)


def write_scale_catalog(tonic: str, output_dir: str | Path, bpm: float = 90,
                        octaves: int = 2) -> list[dict[str, str]]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    records = []
    for scale_name in SCALES:
        filename = re.sub(r"[^A-Za-z0-9]+", "_", f"{tonic}_{scale_name}").strip("_").lower() + ".mid"
        path = out / filename
        make_scale_midi(tonic, scale_name, bpm=bpm, octaves=octaves).save(path)
        records.append({"tonic": tonic, "scale": scale_name, "filename": filename,
                        "intervals": ",".join(map(str, SCALES[scale_name]))})
    return records
