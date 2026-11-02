"""Standard MIDI inspection, 4/4 normalization and feature extraction."""
from __future__ import annotations

from collections import defaultdict, deque
from pathlib import Path
from typing import BinaryIO

import mido
import pandas as pd


def _load_midi(source) -> mido.MidiFile:
    if isinstance(source, mido.MidiFile):
        return source
    if isinstance(source, (bytes, bytearray)):
        import io
        return mido.MidiFile(file=io.BytesIO(source))
    if hasattr(source, "read"):
        return mido.MidiFile(file=source)
    return mido.MidiFile(str(source))


def _absolute_note_events(track: mido.MidiTrack, ppq: int) -> list[dict]:
    tick = 0
    pending: dict[tuple[int, int], deque] = defaultdict(deque)
    notes: list[dict] = []
    for msg in track:
        tick += msg.time
        if not msg.is_meta and msg.type == "note_on" and msg.velocity > 0:
            pending[(msg.channel, msg.note)].append((tick, msg.velocity))
        elif not msg.is_meta and (msg.type == "note_off" or
                                  (msg.type == "note_on" and msg.velocity == 0)):
            key = (msg.channel, msg.note)
            if pending[key]:
                start, velocity = pending[key].popleft()
                notes.append({"start_tick": start, "end_tick": max(start + 1, tick),
                              "pitch": msg.note, "velocity": velocity,
                              "channel": msg.channel})
    final_tick = tick
    for (channel, pitch), queue in pending.items():
        while queue:
            start, velocity = queue.popleft()
            notes.append({"start_tick": start, "end_tick": max(start + ppq, final_tick),
                          "pitch": pitch, "velocity": velocity, "channel": channel})
    return sorted(notes, key=lambda n: (n["start_tick"], n["pitch"]))


def _pitch_label(pitch: int) -> str:
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    return f"{names[int(pitch) % 12]}{int(pitch) // 12 - 1}"


def inspect_midi(source) -> tuple[pd.DataFrame, list[dict]]:
    mid = _load_midi(source)
    tracks = []
    rows = []
    for idx, track in enumerate(mid.tracks):
        name = next((m.name for m in track if m.is_meta and m.type == "track_name"), f"Track {idx + 1}")
        notes = _absolute_note_events(track, mid.ticks_per_beat)
        tracks.append({"index": idx, "name": name, "note_count": len(notes)})
        for note in notes:
            rows.append({"track": idx, "track_name": name, "pitch": note["pitch"],
                         "note_name": _pitch_label(note["pitch"]),
                         "velocity": note["velocity"], "channel": note["channel"],
                         "start_beats": note["start_tick"] / mid.ticks_per_beat,
                         "end_beats": note["end_tick"] / mid.ticks_per_beat,
                         "duration_beats": (note["end_tick"] - note["start_tick"]) / mid.ticks_per_beat})
    return pd.DataFrame(rows), tracks


def normalize_midi(source, output_path: str | Path, bpm: float = 90,
                   grid_beats: float = 1.0, note_duration_beats: float = 0.92,
                   track_index: int = 0, uniform_duration: bool = True,
                   all_tracks: bool = False) -> tuple[Path, dict]:
    """Quantize note onsets onto a beat grid and standardize to one 4/4 tempo.

    This function intentionally preserves pitch, channel and velocity. It does
    not infer or repair wrong pitches. It removes other MIDI event types and
    writes note data from the chosen track (or every note-bearing track).
    """
    if bpm <= 0:
        raise ValueError("bpm must be positive")
    if grid_beats <= 0 or grid_beats > 4:
        raise ValueError("grid_beats must be > 0 and <= 4")
    if note_duration_beats <= 0 or note_duration_beats > 16:
        raise ValueError("note_duration_beats must be > 0 and <= 16")
    mid = _load_midi(source)
    note_tracks = [(i, t) for i, t in enumerate(mid.tracks) if _absolute_note_events(t, mid.ticks_per_beat)]
    if not note_tracks:
        raise ValueError("No note events were found in this MIDI file.")
    if all_tracks:
        selected = note_tracks
    else:
        match = next(((i, t) for i, t in note_tracks if i == track_index), None)
        if match is None:
            available = ", ".join(str(i) for i, _ in note_tracks)
            raise ValueError(f"Track {track_index} has no notes. Note-bearing track indexes: {available}")
        selected = [match]

    ppq = mid.ticks_per_beat
    new_mid = mido.MidiFile(type=1 if len(selected) > 1 else 0, ticks_per_beat=ppq)
    stats = {"input_tracks": len(mid.tracks), "output_tracks": len(selected),
             "input_notes": 0, "output_notes": 0, "bpm": float(bpm),
             "time_signature": "4/4", "grid_beats": float(grid_beats),
             "note_duration_beats": float(note_duration_beats), "tracks": []}
    preloaded = []
    all_snapped = []
    for old_idx, old_track in selected:
        track_notes = _absolute_note_events(old_track, ppq)
        stats["input_notes"] += len(track_notes)
        track_snapped = [round((n["start_tick"] / ppq) / grid_beats) * grid_beats for n in track_notes]
        preloaded.append((old_idx, old_track, track_notes, track_snapped))
        all_snapped.extend(track_snapped)
    if not all_snapped:
        raise ValueError("No note events were found in the selected tracks.")
    # A shared origin preserves the relative entry points of tracks when the
    # all-tracks option is enabled; single-track mode naturally uses its own first note.
    shared_origin = min(all_snapped)
    stats["origin_beats_removed"] = float(shared_origin)
    for old_idx, old_track, notes, snapped in preloaded:
        if not notes:
            continue
        origin = shared_origin
        new_track = mido.MidiTrack()
        name = next((m.name for m in old_track if m.is_meta and m.type == "track_name"), f"Track {old_idx + 1}")
        new_track.append(mido.MetaMessage("track_name", name=name, time=0))
        if len(new_mid.tracks) == 0:
            new_track.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
            new_track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        events = []
        for n, snapped_start in zip(notes, snapped):
            start = max(0.0, snapped_start - origin)
            if uniform_duration:
                duration = note_duration_beats
            else:
                raw_duration = max(grid_beats, (n["end_tick"] - n["start_tick"]) / ppq)
                duration = max(grid_beats, round(raw_duration / grid_beats) * grid_beats)
            start_tick = round(start * ppq)
            end_tick = max(start_tick + 1, round((start + duration) * ppq))
            on = mido.Message("note_on", note=n["pitch"], velocity=n["velocity"],
                              channel=n["channel"], time=0)
            off = mido.Message("note_off", note=n["pitch"], velocity=0,
                               channel=n["channel"], time=0)
            events.append((start_tick, 1, on))
            events.append((end_tick, 0, off))
        previous = 0
        for tick, _priority, msg in sorted(events, key=lambda x: (x[0], x[1])):
            msg.time = max(0, tick - previous)
            new_track.append(msg)
            previous = tick
        new_track.append(mido.MetaMessage("end_of_track", time=1))
        new_mid.tracks.append(new_track)
        stats["output_notes"] += len(notes)
        stats["tracks"].append({"source_index": old_idx, "name": name, "notes": len(notes)})
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    new_mid.save(out)
    return out, stats
