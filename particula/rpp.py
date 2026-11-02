"""Conservative parser for REAPER's text-based RPP project inventory.

The parser extracts project settings, track names, media-item positions/lengths,
source paths and FX names. It does not claim to reproduce every REAPER state
chunk, plugin state, tempo-map transformation, take stretch or render result.
"""
from __future__ import annotations

import re
import shlex
from pathlib import Path


def _parse_value(line: str):
    try:
        parts = shlex.split(line, posix=True)
    except ValueError:
        parts = line.split()
    if not parts:
        return ""
    return parts[0] if len(parts) == 1 else parts[1] if len(parts) == 2 else parts[1:]


def parse_rpp(path: str | Path) -> dict:
    project_path = Path(path)
    try:
        lines = project_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        raise ValueError(f"Could not read RPP file: {exc}") from exc
    root = {"kind": "ROOT", "props": {}, "children": []}
    stack = [root]
    for raw in lines:
        text = raw.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("<"):
            chunk = text[1:].split(None, 1)[0].upper()
            node = {"kind": chunk, "header": text[1:], "props": {}, "children": []}
            stack[-1]["children"].append(node)
            stack.append(node)
        elif text == ">":
            if len(stack) > 1:
                stack.pop()
        else:
            key = text.split(None, 1)[0].upper()
            value = _parse_value(text)
            # Keep repeated keys as arrays instead of discarding information.
            if key in stack[-1]["props"]:
                prev = stack[-1]["props"][key]
                stack[-1]["props"][key] = prev + [value] if isinstance(prev, list) else [prev, value]
            else:
                stack[-1]["props"][key] = value

    def walk(node, kind):
        found = []
        for child in node.get("children", []):
            if child["kind"] == kind:
                found.append(child)
            found.extend(walk(child, kind))
        return found

    project_nodes = [child for child in root.get("children", []) if child["kind"] == "REAPER_PROJECT"]
    project_props = project_nodes[0]["props"] if project_nodes else root["props"]
    root_props = project_props
    tracks = []
    for ti, track in enumerate(walk(root, "TRACK")):
        name = track["props"].get("NAME", f"Track {ti + 1}")
        items = []
        for ii, item in enumerate(walk(track, "ITEM")):
            source_nodes = walk(item, "SOURCE")
            source_type = source_nodes[0]["header"].split()[0] if source_nodes else "unknown"
            source_file = None
            for source in source_nodes:
                if source.get("props", {}).get("FILE"):
                    source_file = source["props"]["FILE"]
                    break
            pos = item["props"].get("POSITION")
            length = item["props"].get("LENGTH")
            try:
                pos = float(pos)
            except (TypeError, ValueError):
                pos = None
            try:
                length = float(length)
            except (TypeError, ValueError):
                length = None
            resolved = None
            exists = None
            if source_file:
                raw_file = str(source_file)
                candidate = Path(raw_file)
                if not candidate.is_absolute():
                    candidate = project_path.parent / candidate
                resolved = str(candidate.resolve())
                exists = candidate.exists()
            items.append({"index": ii, "position_seconds": pos, "length_seconds": length,
                          "source_type": source_type, "source_file": source_file,
                          "resolved_source_path": resolved, "source_exists_in_runtime": exists})
        fx_names = []
        for fxnode in walk(track, "VST") + walk(track, "AU") + walk(track, "JS") + walk(track, "CLAP"):
            fx_names.append(fxnode.get("header", fxnode["kind"]))
        tracks.append({"index": ti, "name": name, "items": items, "item_count": len(items),
                       "fx_count": len(fx_names), "fx_entries": fx_names})

    tempo_value = root_props.get("TEMPO")
    time_sig = None
    if tempo_value is not None:
        bits = tempo_value if isinstance(tempo_value, list) else [tempo_value]
        # _parse_value returns a string for a one-token setting, list for multiple tokens.
        if len(bits) == 1 and isinstance(bits[0], list):
            bits = bits[0]
        if isinstance(bits, list) and len(bits) >= 3:
            try:
                time_sig = f"{int(float(bits[1]))}/{int(float(bits[2]))}"
            except (ValueError, TypeError):
                pass
    bpm = None
    try:
        if isinstance(tempo_value, list):
            bpm = float(tempo_value[0])
        elif tempo_value is not None:
            bpm = float(tempo_value)
    except (ValueError, TypeError):
        pass
    return {"project_file": project_path.name, "project_path": str(project_path),
            "tempo_bpm": bpm, "time_signature": time_sig,
            "track_count": len(tracks), "item_count": sum(t["item_count"] for t in tracks),
            "tracks": tracks,
            "scope_note": "RPP inventory parser only; not a complete REAPER state-chunk interpreter."}
