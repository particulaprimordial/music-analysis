# Data dictionary

## MIDI note-event table

| Field | Type | Meaning |
|---|---|---|
| `track` | integer | Zero-based source track index |
| `track_name` | string | MIDI track name, or generated fallback |
| `pitch` | integer | MIDI note number (0–127) |
| `note_name` | string | Note label derived from the MIDI note number |
| `velocity` | integer | Note-on velocity (1–127) |
| `channel` | integer | MIDI channel index (0–15) |
| `start_beats` | float | Note onset in quarter-note beats relative to track start |
| `end_beats` | float | Note offset in quarter-note beats |
| `duration_beats` | float | Note duration in quarter-note beats |

## Normalization metadata

| Field | Meaning |
|---|---|
| `bpm` | Output tempo in quarter notes per minute |
| `time_signature` | Output meter; fixed to 4/4 in normalizer |
| `grid_beats` | Onset quantization grid in quarter-note beats |
| `note_duration_beats` | Fixed output duration when uniform mode is enabled |
| `input_notes` / `output_notes` | Note counts before and after the transformation |

## Audio measurements

| Field | Unit / interpretation |
|---|---|
| `sample_rate` | Samples per second (Hz) |
| `channels` | Number of interleaved PCM channels |
| `duration_seconds` | Decoded audio length in seconds |
| `peak` | Absolute sample peak, normalized to approximately 0–1 |
| `rms` | Root-mean-square amplitude, normalized to approximately 0–1 |
| `zero_crossing_rate` | Fraction of adjacent sample pairs crossing zero |
| `spectral_centroid_hz_mean` | Mean magnitude-weighted FFT frequency over analyzed frames |

## RPP project inventory

The RPP report includes project file name/path, tempo and time signature when detected, track/item counts, track names, item position/length, source type, source path, resolved path, path accessibility flag in the current runtime (not proof of availability on the original REAPER machine) and visible FX chunk labels. Missing or unsupported properties are represented as `null` or omitted rather than guessed.
