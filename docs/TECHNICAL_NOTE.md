# Particula Primordial: An Auditable Toolkit for MIDI Normalization, Transposable Scale Studies and Computational Composition

**Technical note · Version 0.2.0 · 1 November 2026**  
**Project:** Particula Primordial  
**Software license:** MIT

## Abstract

Particula Primordial is an open-source prototype for a reproducible workflow that connects MIDI event analysis, temporal normalization, transposable tonal material, algorithmic composition and digital-audio-workstation project inspection. Its primary input is a user-supplied Standard MIDI File containing a performance, exercise or musical fragment. The system reconstructs note events from MIDI note-on and note-off messages, represents event positions in quarter-note beats, and can standardize note onset positions to a configurable grid, note durations to a fixed value, tempo to a single target BPM and meter to 4/4. The normalization stage preserves pitch, velocity and channel for the selected note streams and does not perform automatic pitch correction.

A parameterized scale engine represents each scale as an interval vector relative to a tonic, allowing the same recipe to be transposed across the twelve pitch classes of twelve-tone equal temperament (12-TET). The current prototype includes 21 practical interval recipes. A composition engine derives extended tertian sonorities from the selected scale, applies seven progression templates, and generates deterministic melodic contours using reflection, modular arithmetic, Fibonacci residues, prime residues, a logistic map, bounded random walks and cyclic motion. A sustained ascension generator creates an extensible, deliberately open-ended MIDI study.

The application also includes WAV signal measurements and a conservative parser for REAPER `.RPP` project inventories. It separates offline file analysis from full arrangement rendering through REAPER, because project-native instruments, effects, routing and media dependencies must be evaluated by the DAW that owns them. The Streamlit dashboard provides an accessible interface for file upload, visualization and export. The included test suite verifies selected software invariants using synthetic fixtures. The prototype does not claim transcription accuracy, perceptual superiority or production-grade synthesis; those properties require separate empirical evaluation.

**Keywords:** computational musicology, MIDI, quantization, music information retrieval, algorithmic composition, scale transposition, REAPER, Streamlit, reproducibility.

## 1. Introduction

A short piano scale recording or MIDI exercise is often useful as source material for further study, but its event timing may be inconsistent. Note onsets can fall between intended beat locations, note lengths can vary unintentionally, and the file may contain tempo or meter metadata that complicates notation-oriented work. A practical research workflow should preserve the performed pitch sequence while making its temporal organization explicit and reproducible.

Particula Primordial addresses this narrow problem and extends it into a compositional research environment. The platform does not assume that the source is in a particular key. A user chooses a tonic and an interval recipe; the same procedure can then create scale exercises and composition studies in another key without rewriting the algorithm.

The implementation uses Standard MIDI Files as the canonical note-event interchange format. MIDI timing is tick-based: events store delta times, and the PPQ resolution together with tempo metadata determines the mapping between ticks, beats and seconds [1]. The software therefore distinguishes beat-domain quantization from second-domain audio measurements.

## 2. System architecture

The application consists of five interoperable layers:

1. **Input and parsing:** Standard MIDI, WAV and REAPER project text are ingested through separate readers.
2. **Event representation:** MIDI note-on and note-off events are paired into note records with pitch, velocity, channel and beat positions.
3. **Transformation:** note onset quantization and duration standardization are applied with explicit user parameters.
4. **Tonal and compositional generation:** scale recipes are transposed by tonic; extended harmony and deterministic melody contours are derived from the chosen collection.
5. **Visualization and export:** Streamlit plots event distributions and provides MIDI, CSV, JSON, WAV and optional MP3 artifacts.

The architecture exposes two execution modes. Offline mode operates on uploaded files and does not require REAPER. The second mode is host-dependent: REAPER itself loads the project, resolves its media, plugins and routing, and renders the complete arrangement. REAPER stores project structure in `.RPP` files, which the REAPER user guide describes as text-based project files holding track, media and settings information [2]. Its ReaScript interface exposes functions for MIDI event and note access [3], and its command-line interface includes a `-renderproject` option [4].

The RPP reader in this repository is deliberately limited to project inventory: tempo/meter when present, track names, media-item positions and lengths, source references and visible effect-chunk labels. Media-path accessibility is evaluated only in the process environment and cannot prove availability on the original user workstation. It is not a complete parser of every REAPER chunk or plugin state. A separate Lua ReaScript uses the host API to export note-level information from selected MIDI takes as CSV. This avoids misrepresenting an offline parser as a full DAW execution environment.

## 3. MIDI event model and temporal normalization

### 3.1 Note-event reconstruction

Within a MIDI track, each message has a delta time in ticks. The implementation accumulates delta times into absolute tick positions. A positive-velocity `note_on` begins a note; a matching `note_off` or zero-velocity `note_on` closes it. Matching uses MIDI channel and pitch. The resulting event record is:

\[
 n_i = (p_i, v_i, c_i, t_{i,on}, t_{i,off})
\]

where \(p_i\) is MIDI pitch, \(v_i\) velocity, \(c_i\) channel and the two time values are absolute ticks. With PPQ resolution \(P\), beat position is computed as \(b=t/P\). The implementation preserves the source PPQ in the normalized output.

### 3.2 Grid quantization

Let the user-selected onset grid be \(g\) quarter-note beats. The quantized onset of note \(i\) is:

\[
 q_i = \operatorname{round}\left(\frac{b_{i,on}}{g}\right)g
\]

The earliest quantized onset is shifted to beat zero:

\[
 q_i' = q_i - \min_j(q_j)
\]

When uniform duration is enabled, each output note ends at:

\[
 b'_{i,off}=q_i' + d
\]

where \(d\) is the user-selected duration in beats. When uniform duration is disabled, the original duration is rounded to the selected grid, with a minimum of one grid interval. The output writes a single target BPM and a 4/4 time-signature event.

This normalization can change articulation, overlaps and phrase timing. Consequently, grid size and duration are user-controlled, not estimated as universally optimal values. The algorithm leaves note pitch, velocity and channel unchanged. It does not identify wrong notes, infer a key, or rewrite harmonic content.

## 4. Transposable scale representation

A scale is stored as a set of ascending semitone offsets from its tonic:

\[
 S=(0,s_1,s_2,\ldots,s_{m-1})
\]

For tonic pitch class \(r\), each scale pitch class is:

\[
 pc_i=(r+s_i)\bmod 12
\]

This interval-vector representation makes the scale engine independent of the key. The repository currently includes 21 recipes covering common major/minor collections, modal collections, pentatonic and blues collections, whole-tone and diminished collections, selected synthetic scales and the chromatic collection. This is a practical 12-TET starter dictionary; it is not an exhaustive taxonomy of scales across musical cultures, tuning systems or microtonal practice.

Each generated scale MIDI file includes a track name, tempo and 4/4 time signature. It contains an ascending sequence followed by a descending sequence over a configurable octave range. The scale manifest records tonic, recipe name, interval vector and filename, allowing outputs to be audited and regenerated.

## 5. Scale-derived harmony and algorithmic melody

The composition engine uses seven four-chord degree templates. For each chord root, alternate scale degrees are stacked to create triadic and extended sonorities. Seven-note collections produce conventional tertian stacks: 1, 3, 5, 7, 9, 11 and 13. For non-heptatonic scales, the stack cycles through the available degrees; chord-symbol labels may then be approximate, but the generated MIDI pitches remain traceable to the interval recipe.

The seven progression templates are generic degree patterns rather than key-specific chord strings. Their degree indices are resolved against the selected scale at runtime. The extension sequence rotates through 7th, 9th, 11th and 13th structures. This provides a controlled basis for comparing progression behavior across tonal centers and scale families.

Melodic contours are deterministic functions of a sequence index and seed. The included methods are: reflection, modular permutation, Fibonacci residues, prime residues, logistic-map iteration, bounded random walk and cyclic pendulum. These transformations generate scale-degree indices; the scale engine maps those indices to MIDI pitches in a selected register. The methods are computational pattern generators rather than claims that mathematical sequences are intrinsically musical. Musical evaluation must consider voice-leading, register, rhythmic hierarchy, repetition and listening perception.

The ascension study sustains a tonic-centered pedal field while allowing an upper voice to move through the selected collection. Its length is configurable. The final sonority is designed to remain open rather than provide a conventional cadence. The study is extensible but finite in any exported file.

## 6. Audio measurement and rendering

The WAV feature module reports duration, sample rate, channel count, absolute peak, RMS, zero-crossing rate and a frame-averaged spectral centroid. These measurements describe selected signal properties; they do not by themselves determine perceived loudness, timbre quality, musicality or production quality.

A minimal additive renderer is included to create reference WAV previews from MIDI notes. MP3 conversion is performed through FFmpeg when it is installed. The reference renderer is intentionally not represented as a piano sample library or a replacement for REAPER. For DAW-native audio, REAPER must resolve the project's own instruments, effects, routing and render configuration. Streamlit Community Cloud supports deployment from a GitHub repository with dependency files [5], but the hosted application cannot assume access to a user's local DAW installation or proprietary plugins. FluidSynth provides an alternative SoundFont-based MIDI rendering route when a compatible SoundFont and the required runtime are installed [6].

## 7. Dashboard and reproducibility

The Streamlit dashboard groups the workflow into overview, MIDI normalization, scale catalogue, composition lab, REAPER/audio analysis and research notes. Output artifacts are downloadable individually or as ZIP archives. CSV manifests and JSON project summaries provide traceable records of selected parameters.

Reproducibility depends on recording the source file, software version, PPQ, target BPM, grid, duration, tonic, scale interval vector, progression template, algorithm and seed. A future version should add content hashes and a formal experiment log for every export.

## 8. Validation strategy

The automated test suite uses synthetic fixtures to test the following software invariants: tonic parsing and enharmonic equivalence; scale transposition; chord pitch membership; note pitch and velocity preservation during normalization; onset-grid alignment; fixed output duration; 4/4/tempo metadata; composition track structure; reference WAV validity; and expected RPP inventory extraction.

These tests validate implementation behavior, not artistic outcomes. Empirical evaluation remains necessary. A future study should use a corpus of scale performances with measured onset variation, compare pre/post quantization displacement, measure duration variance, and conduct listening tests to assess whether grid choices retain expressive intent. Composition outputs should be evaluated through both computational checks (scale membership, register, voice-leading and structural repetition) and blinded human listening.

## 9. Limitations and future work

The current normalizer focuses on note-on and note-off events and does not guarantee preservation of all controllers, aftertouch, pitch bend, program changes, SysEx or automation. It intentionally flattens tempo and meter. The scale system is 12-TET and requires the user to select tonic and scale; it does not automatically detect a key. Chord labels are approximations for some scale families. The reference renderer is intentionally simple. The RPP inventory parser is not a full REAPER project interpreter. The test suite is synthetic and no peer-reviewed user study has been completed.

Future work should include a broader MIDI event-preservation mode, optional tempo-map-aware quantization, key/scale hypotheses with uncertainty estimates, user-defined interval recipes, microtonal support, improved voicing and voice-leading constraints, SoundFont-backed rendering, corpus-based evaluation and a machine-readable experiment archive.

## References

1. Mido. *Standard MIDI Files — time attributes, PPQ, tempo and tick conversion*. https://mido.github.io/mido/files/midi.html
2. Cockos. *REAPER User Guide*, section on REAPER file types (`.RPP`). https://reaper.fm/userguide/ReaperUserGuide716c.pdf
3. Cockos. *REAPER ReaScript API documentation*. https://www.reaper.fm/sdk/reascript/reascripthelp
4. ReaTeam. *REAPER CLI options*. https://github.com/ReaTeam/Doc/blob/master/REAPER-CLI.md
5. Streamlit. *Streamlit Community Cloud documentation*. https://docs.streamlit.io/deploy/streamlit-community-cloud
6. FluidSynth. *User Manual*. https://github.com/FluidSynth/fluidsynth/blob/master/doc/wiki/UserManual.md
