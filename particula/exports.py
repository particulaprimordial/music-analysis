"""Convenience helpers for writing tabular audit reports."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def write_analysis_csv(notes: pd.DataFrame, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    notes.to_csv(out, index=False)
    return out


def write_json(data: dict, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return out
