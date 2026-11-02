# Architecture and execution boundaries

## Layer 1 — File ingestion

- Standard MIDI (`.mid`, `.midi`) is the canonical representation for note-event analysis.
- WAV PCM is the canonical audio input for the lightweight signal feature module.
- REAPER `.RPP` text is parsed for project inventory only.
- REAPER's ReaScript API is used by the optional Lua script for note-level export from selected MIDI takes.

## Layer 2 — Musical event representation

Each note event is represented by:

`track, track_name, pitch, note_name, velocity, channel, start_beats, end_beats, duration_beats`

MIDI event positions are stored in integer ticks relative to pulses per quarter note (PPQ). Conversion from ticks to beats requires the file's PPQ resolution. Conversion from ticks to seconds additionally requires the active tempo map.

## Layer 3 — Temporal normalization

For a target grid `g` quarter-note beats, note onset `t` is mapped to:

`q(t) = round(t / g) * g`

The first quantized onset is translated to beat zero. If uniform duration `d` is enabled, each note interval becomes `[q(t) - q(t0), q(t) - q(t0) + d]`. The output MIDI contains one tempo event, a 4/4 time-signature event and the selected note stream(s).

This changes note timing and duration but intentionally leaves pitch, velocity and channel untouched. The operation is not a transcription or pitch-correction algorithm.

## Layer 4 — Tonal transposition

A scale is an interval vector `S = (s0, s1, ..., sn)` with `s0 = 0`. For tonic pitch class `r`, generated pitch classes are `(r + si) mod 12`. The same interval vector can therefore be used with any tonic in 12-TET.

The scale dictionary is data-driven so additional interval collections can be registered without changing the composition algorithms.

## Layer 5 — Diatonic extended harmony

A chord is constructed by selecting alternate positions from the ordered scale collection. For a seven-note scale, a 13th stack uses scale degrees 1, 3, 5, 7, 9, 11 and 13. Non-heptatonic collections cycle through available degrees; chord-symbol labels in those cases are intentionally treated as approximations.

## Layer 6 — Algorithmic contour

The seven contour methods produce deterministic scale-degree sequences from a seed. A seed and method index fully identify a generated melodic contour. They do not encode a claim that a mathematical sequence is inherently musical; they are controlled transformations for analysis and compositional exploration.

## Layer 7 — Audio output

The built-in synth is a minimal additive preview. Native audio fidelity is delegated to a DAW or SoundFont engine. In REAPER mode, the project retains control of instrument choice, routing, FX, region bounds and render settings.

## Execution boundary

A public Streamlit app cannot assume access to the user's local DAW, VST instruments, media files or license-protected assets. For this reason the cloud dashboard analyses uploaded project text and standalone media; local REAPER rendering is a separate host-side operation.
