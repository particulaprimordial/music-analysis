from __future__ import annotations

import io
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from particula.audio import audio_features, render_reference_wav, wav_to_mp3
from particula.composition import PROGRESSION_TEMPLATES, generate_composition_pack
from particula.exports import write_analysis_csv, write_json
from particula.features import summarize_notes
from particula.midi_tools import inspect_midi, normalize_midi
from particula.rpp import parse_rpp
from particula.theory import SCALES, write_scale_catalog

st.set_page_config(page_title="Particula Primordial", page_icon="◌", layout="wide")

TONICS = ["C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"]

def _zip_folder(folder: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in folder.rglob("*"):
            if path.is_file():
                archive.write(path, path.relative_to(folder))
    return buffer.getvalue()

def _display_notes(notes: pd.DataFrame, key: str):
    if notes.empty:
        st.info("No MIDI note events were found.")
        return
    summary = summarize_notes(notes)
    a, b, c, d = st.columns(4)
    a.metric("Notes", summary["note_count"])
    b.metric("Pitch range", f"{summary['pitch_min']}–{summary['pitch_max']}")
    c.metric("Mean velocity", f"{summary['mean_velocity']:.1f}")
    d.metric("Mean duration", f"{summary['mean_duration_beats']:.2f} beats")
    plot = px.scatter(notes, x="start_beats", y="pitch", color="track_name" if "track_name" in notes else None,
                      size="velocity", hover_data=[c for c in ["note_name", "duration_beats", "velocity"] if c in notes],
                      title=key, labels={"start_beats": "Position (quarter-note beats)", "pitch": "MIDI pitch"})
    plot.update_traces(marker={"symbol": "square", "opacity": 0.82})
    plot.update_layout(height=360, legend_title_text="Track")
    st.plotly_chart(plot, use_container_width=True)
    pc = summary["pitch_class_counts"].rename_axis("Pitch class").reset_index(name="Note count")
    st.plotly_chart(px.bar(pc, x="Pitch class", y="Note count", title="Pitch-class distribution"), use_container_width=True)
    st.dataframe(notes.head(250), use_container_width=True, hide_index=True)

st.title("Particula Primordial")
st.caption("Computational music analysis · scale-transposable composition · reproducible MIDI research")
st.markdown("The selected tonic and scale are parameters. The same algorithms run after transposition to any supported tonic.")

with st.sidebar:
    st.header("Research configuration")
    tonic = st.selectbox("Tonic", TONICS, index=0)
    scale_name = st.selectbox("Scale", list(SCALES.keys()), index=list(SCALES).index("Natural Minor (Aeolian)"))
    st.caption("The scale catalogue is extensible. A scale is represented as a semitone-interval recipe relative to the tonic.")
    st.divider()
    st.markdown("**Modes**")
    st.caption("Offline analysis works without REAPER. Full project rendering is delegated to a local REAPER installation.")

home, midi_tab, scales_tab, composition_tab, reaper_tab, research_tab = st.tabs(
    ["Overview", "MIDI normalizer", "Scale catalogue", "Composition lab", "REAPER & audio", "Research notes"])

with home:
    st.subheader("Research workflow")
    c1, c2, c3 = st.columns(3)
    c1.metric("Scale recipes", len(SCALES))
    c2.metric("Progression templates", len(PROGRESSION_TEMPLATES))
    c3.metric("Time standard", "4/4")
    st.markdown("""
    **1 · Normalize** an existing MIDI performance without changing note pitches.

    **2 · Generalize** the selected tonic across a scale catalogue of transposed MIDI exercises.

    **3 · Compose** scale-derived extended harmony, deterministic algorithmic melodies and an open-ended sustained study.

    **4 · Analyze** standard MIDI, WAV audio and REAPER project inventories. REAPER-native rendering stays a separate local operation.
    """)
    st.info("Important distinction: onset quantization and note-duration standardization are temporal edits. They do not correct a wrong pitch or infer a different scale.")

with midi_tab:
    st.subheader("MIDI normalization and audit")
    uploaded = st.file_uploader("Upload a Standard MIDI File (.mid / .midi)", type=["mid", "midi"], key="normalizer_midi")
    if uploaded:
        midi_bytes = uploaded.getvalue()
        try:
            notes, tracks = inspect_midi(midi_bytes)
            st.write("**MIDI tracks**")
            st.dataframe(pd.DataFrame(tracks), use_container_width=True, hide_index=True)
            if notes.empty:
                st.warning("This MIDI file contains no note events.")
            else:
                _display_notes(notes, "Input MIDI piano roll")
                track_options = [t["index"] for t in tracks if t["note_count"] > 0]
                with st.form("normalize_form"):
                    selected_track = st.selectbox("Source track", track_options)
                    target_bpm = st.slider("Target tempo (BPM)", 40, 220, 90)
                    grid = st.selectbox("Onset grid (quarter-note beats)", [1.0, 0.5, 0.25, 0.125], index=0,
                                        format_func=lambda x: {1.0: "Quarter note", 0.5: "Eighth note", 0.25: "16th note", 0.125: "32nd note"}[x])
                    duration = st.number_input("Uniform note duration (beats)", min_value=0.05, max_value=4.0, value=0.92, step=0.05)
                    all_tracks = st.checkbox("Normalize all note-bearing tracks", value=False)
                    submitted = st.form_submit_button("Normalize to 4/4")
                if submitted:
                    with tempfile.TemporaryDirectory() as tmp:
                        source_path = Path(tmp) / uploaded.name
                        source_path.write_bytes(midi_bytes)
                        out_path = Path(tmp) / "normalized_4_4.mid"
                        try:
                            out_path, stats = normalize_midi(source_path, out_path, bpm=target_bpm,
                                grid_beats=grid, note_duration_beats=duration, track_index=selected_track,
                                all_tracks=all_tracks)
                            normalized_notes, _ = inspect_midi(out_path)
                            st.success("MIDI normalized. Pitch, note order, velocity and channel are preserved for the selected track(s).")
                            st.json(stats)
                            _display_notes(normalized_notes, "Normalized 4/4 piano roll")
                            st.download_button("Download normalized MIDI", out_path.read_bytes(),
                                               file_name="normalized_4_4.mid", mime="audio/midi")
                            wav_path = Path(tmp) / "normalized_reference.wav"
                            try:
                                render_reference_wav(out_path, wav_path)
                                st.audio(wav_path.read_bytes(), format="audio/wav")
                                st.download_button("Download reference WAV", wav_path.read_bytes(),
                                                   file_name="normalized_reference.wav", mime="audio/wav")
                                try:
                                    mp3_path = Path(tmp) / "normalized_reference.mp3"
                                    wav_to_mp3(wav_path, mp3_path)
                                    st.download_button("Download reference MP3", mp3_path.read_bytes(),
                                                       file_name="normalized_reference.mp3", mime="audio/mpeg")
                                except Exception as exc:
                                    st.caption(f"MP3 export unavailable: {exc}")
                            except Exception as exc:
                                st.warning(f"Reference audio render unavailable: {exc}")
                            csv_bytes = normalized_notes.to_csv(index=False).encode("utf-8")
                            st.download_button("Download note-event audit CSV", csv_bytes,
                                               file_name="normalized_note_audit.csv", mime="text/csv")
                        except Exception as exc:
                            st.error(f"Normalization failed: {exc}")
        except Exception as exc:
            st.error(f"Could not parse MIDI: {exc}")

with scales_tab:
    st.subheader("Transposable scale catalogue")
    st.write(f"Selected reference: **{tonic} · {scale_name}**. The same scale recipes can be transposed to any supported tonic.")
    octaves = st.slider("Octaves per scale file", 1, 4, 2)
    scale_bpm = st.slider("Scale exercise tempo", 40, 220, 90)
    include_scale_audio = st.checkbox("Also render WAV previews and MP3 copies (FFmpeg required for MP3)", value=False)
    if st.button("Generate MIDI files for all scale recipes", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "scale_catalogue"
            records = write_scale_catalog(tonic, out, bpm=scale_bpm, octaves=octaves)
            audio_rows = []
            if include_scale_audio:
                midi_files = sorted(out.glob("*.mid"))
                progress = st.progress(0, text="Rendering scale reference audio")
                for idx, midi_path in enumerate(midi_files):
                    wav_path = out / f"{midi_path.stem}.wav"
                    try:
                        render_reference_wav(midi_path, wav_path)
                        mp3_result = "created"
                        try:
                            wav_to_mp3(wav_path, out / f"{midi_path.stem}.mp3")
                        except Exception as exc:
                            mp3_result = str(exc)
                        audio_rows.append({"file": midi_path.name, "WAV": "created", "MP3": mp3_result})
                    except Exception as exc:
                        audio_rows.append({"file": midi_path.name, "WAV": str(exc), "MP3": "not attempted"})
                    progress.progress((idx + 1) / len(midi_files), text=f"Rendered {idx + 1}/{len(midi_files)}")
            pd.DataFrame(records).to_csv(out / "scale_catalogue_manifest.csv", index=False)
            st.success(f"Generated {len(records)} scale MIDI files for {tonic}.")
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
            if audio_rows:
                st.dataframe(pd.DataFrame(audio_rows), use_container_width=True, hide_index=True)
            st.download_button("Download complete scale catalogue ZIP", _zip_folder(out),
                               file_name=f"{tonic}_scale_catalogue.zip", mime="application/zip")
    st.caption("This is a practical starter catalogue of common tonal, modal, pentatonic, blues and synthetic collections, not a claim to enumerate every scale in every musical tradition.")

with composition_tab:
    st.subheader("Scale-derived composition lab")
    c1, c2, c3 = st.columns(3)
    with c1:
        comp_bpm = st.slider("Progression tempo", 50, 180, 112)
    with c2:
        asc_bpm = st.slider("Ascension tempo", 40, 100, 72)
    with c3:
        asc_bars = st.select_slider("Ascension length", options=[16, 32, 48, 64, 96], value=32)
    render_audio = st.checkbox("Also render reference WAV and MP3 files", value=True)
    st.write("Seven progression templates are transposed into the selected scale. Chords stack diatonic thirds; extensions cycle through 7, 9, 11 and 13. Seven deterministic contour methods generate corresponding melodies.")
    st.dataframe(pd.DataFrame([{"Study": k, "Scale degrees (1-based)": " – ".join(str(x + 1) for x in v)}
                               for k, v in PROGRESSION_TEMPLATES.items()]), use_container_width=True, hide_index=True)
    if st.button("Generate composition pack", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "composition_pack"
            records = generate_composition_pack(tonic, scale_name, out, bpm=comp_bpm,
                                                ascension_bpm=asc_bpm, ascension_bars=asc_bars)
            audio_status = []
            if render_audio:
                progress = st.progress(0, text="Rendering MIDI reference audio")
                midi_files = sorted(out.glob("*.mid"))
                for idx, midi_path in enumerate(midi_files):
                    try:
                        wav_path = out / f"{midi_path.stem}.wav"
                        render_reference_wav(midi_path, wav_path)
                        try:
                            wav_to_mp3(wav_path, out / f"{midi_path.stem}.mp3")
                            audio_status.append({"file": midi_path.name, "WAV": "created", "MP3": "created"})
                        except Exception as exc:
                            audio_status.append({"file": midi_path.name, "WAV": "created", "MP3": str(exc)})
                    except Exception as exc:
                        audio_status.append({"file": midi_path.name, "WAV": str(exc), "MP3": "not attempted"})
                    progress.progress((idx + 1) / len(midi_files), text=f"Rendered {idx + 1}/{len(midi_files)}")
            pd.DataFrame(records).to_csv(out / "composition_manifest.csv", index=False)
            (out / "README.txt").write_text(
                f"Particula Primordial composition pack\nTonic: {tonic}\nScale: {scale_name}\n"
                f"Progression BPM: {comp_bpm}\nAscension: {asc_bars} bars at {asc_bpm} BPM\n"
                "Audio is a lightweight additive reference render, not a production piano/SoundFont performance.\n",
                encoding="utf-8")
            st.success(f"Generated {len(records)} MIDI composition studies.")
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
            if audio_status:
                st.dataframe(pd.DataFrame(audio_status), use_container_width=True, hide_index=True)
            st.download_button("Download complete composition ZIP", _zip_folder(out),
                               file_name=f"{tonic}_{scale_name.replace(' ', '_')}_composition_pack.zip",
                               mime="application/zip")

with reaper_tab:
    st.subheader("Offline REAPER project analysis")
    st.markdown("Upload an `.RPP` text project to inspect track, item, FX and media-reference inventory. The parser does not attempt to recreate the complete REAPER render graph. Relative media paths are checked only in the runtime where the dashboard runs; a cloud upload cannot see files that remain on your computer.")
    rpp_upload = st.file_uploader("Upload REAPER project (.RPP)", type=["rpp"], key="rpp_file")
    if rpp_upload:
        with tempfile.TemporaryDirectory() as tmp:
            rpp_path = Path(tmp) / rpp_upload.name
            rpp_path.write_bytes(rpp_upload.getvalue())
            try:
                data = parse_rpp(rpp_path)
                a, b, c = st.columns(3)
                a.metric("Tracks", data["track_count"])
                b.metric("Items", data["item_count"])
                c.metric("Tempo", f"{data['tempo_bpm']:.2f} BPM" if data["tempo_bpm"] else "Not found")
                st.json({k: v for k, v in data.items() if k != "tracks"})
                flat = []
                for tr in data["tracks"]:
                    if tr["items"]:
                        for item in tr["items"]:
                            flat.append({"track": tr["name"], **item})
                    else:
                        flat.append({"track": tr["name"], "item_count": 0, "fx_count": tr["fx_count"]})
                st.dataframe(pd.DataFrame(flat), use_container_width=True, hide_index=True)
                st.download_button("Download RPP inventory JSON", json.dumps(data, indent=2).encode("utf-8"),
                                   file_name="reaper_project_inventory.json", mime="application/json")
            except Exception as exc:
                st.error(f"RPP analysis failed: {exc}")
    st.divider()
    st.subheader("REAPER ReaScript note-event CSV")
    reaper_csv = st.file_uploader("Upload particula_primordial_midi_notes.csv", type=["csv"], key="reaper_csv")
    if reaper_csv:
        try:
            raw_df = pd.read_csv(reaper_csv)
            required = {"track_name", "pitch", "velocity", "channel", "start_qn", "end_qn"}
            missing = required - set(raw_df.columns)
            if missing:
                st.error(f"CSV is missing required fields: {', '.join(sorted(missing))}")
            else:
                note_df = pd.DataFrame({
                    "track": raw_df["item_index"] if "item_index" in raw_df else 0,
                    "track_name": raw_df["track_name"].astype(str),
                    "pitch": raw_df["pitch"].astype(int),
                    "note_name": raw_df["pitch"].astype(int).map(lambda p: f"{['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'][p % 12]}{p // 12 - 1}"),
                    "velocity": raw_df["velocity"].astype(int),
                    "channel": raw_df["channel"].astype(int),
                    "start_beats": raw_df["start_qn"].astype(float),
                    "end_beats": raw_df["end_qn"].astype(float),
                    "duration_beats": raw_df["end_qn"].astype(float) - raw_df["start_qn"].astype(float),
                })
                _display_notes(note_df, "REAPER MIDI take piano roll")
                st.download_button("Download normalized-column CSV", note_df.to_csv(index=False).encode("utf-8"),
                                   file_name="reaper_note_event_analysis.csv", mime="text/csv")
        except Exception as exc:
            st.error(f"Could not parse the ReaScript CSV: {exc}")
    st.divider()
    st.subheader("WAV signal measurements")
    wav_upload = st.file_uploader("Upload WAV audio for signal analysis", type=["wav"], key="audio_file")
    if wav_upload:
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / wav_upload.name
            audio_path.write_bytes(wav_upload.getvalue())
            try:
                features = audio_features(audio_path)
                cols = st.columns(4)
                cols[0].metric("Duration", f"{features['duration_seconds']:.2f} s")
                cols[1].metric("Sample rate", f"{features['sample_rate']} Hz")
                cols[2].metric("Peak", f"{features['peak']:.3f}")
                cols[3].metric("RMS", f"{features['rms']:.3f}")
                st.json(features)
                st.download_button("Download audio feature JSON", json.dumps(features, indent=2).encode("utf-8"),
                                   file_name="audio_features.json", mime="application/json")
            except Exception as exc:
                st.error(f"Audio analysis failed: {exc}")
    st.warning("Local REAPER rendering requires a REAPER installation on the machine that runs the renderer. Streamlit Community Cloud does not contain your DAW, plugins, licenses or local SoundFonts.")
    st.code("reaper -renderproject /path/to/project.rpp", language="bash")

with research_tab:
    st.subheader("Research scope and reproducibility")
    st.markdown("""
    **Two execution modes**

    - **Offline mode:** Standard MIDI parsing, note-event reconstruction, grid normalization, scale transposition, composition generation, WAV reference synthesis, audio measurements and RPP project inventory.
    - **REAPER-dependent mode:** Native project playback and arrangement rendering through REAPER, with the project's saved routing, FX, virtual instruments and render settings.

    **Validation boundaries**

    - Pitch values are preserved by normalization; pitch correction is deliberately out of scope.
    - Quantization can alter note timing. The selected grid and fixed duration are explicit user parameters.
    - Chord labels for synthetic or non-heptatonic scales are descriptive approximations; generated pitches are derived from the scale recipe.
    - The built-in audio renderer is a simple additive reference synthesizer. It is not a substitute for a sampled piano, SoundFont, plugin chain or REAPER mix.
    - RPP parsing is an inventory-level parser. It does not claim complete interpretation of every project chunk or every plugin's private state.
    """)
    st.markdown("**Methods and source documentation**")
    st.markdown("- [Mido Standard MIDI Files and tick timing](https://mido.github.io/mido/files/midi.html)")
    st.markdown("- [REAPER ReaScript API](https://www.reaper.fm/sdk/reascript/reascripthelp)")
    st.markdown("- [REAPER ReaScript overview](https://www.reaper.fm/sdk/reascript/reascript.php)")
    st.markdown("- [REAPER command-line options](https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md)")
    st.markdown("- [Streamlit Community Cloud deployment](https://docs.streamlit.io/deploy/streamlit-community-cloud)")
    st.markdown("- [FluidSynth user manual](https://github.com/FluidSynth/fluidsynth/blob/master/doc/wiki/UserManual.md)")
