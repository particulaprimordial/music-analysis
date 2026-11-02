"""Musical feature summaries for MIDI note tables."""
from __future__ import annotations

import pandas as pd

PITCH_CLASS_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def summarize_notes(notes: pd.DataFrame) -> dict:
    if notes.empty:
        return {"note_count": 0, "pitch_range": None, "mean_velocity": None,
                "mean_duration_beats": None, "pitch_class_counts": pd.Series(dtype=int)}
    pc_counts = notes["pitch"].mod(12).value_counts().reindex(range(12), fill_value=0)
    pc_counts.index = PITCH_CLASS_NAMES
    return {"note_count": int(len(notes)), "pitch_min": int(notes.pitch.min()),
            "pitch_max": int(notes.pitch.max()), "mean_velocity": float(notes.velocity.mean()),
            "mean_duration_beats": float(notes.duration_beats.mean()),
            "mean_start_interval_beats": float(notes.start_beats.sort_values().diff().dropna().mean())
            if len(notes) > 1 else 0.0,
            "pitch_class_counts": pc_counts}
