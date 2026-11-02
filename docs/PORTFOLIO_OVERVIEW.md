# Portfolio overview

## Project positioning

**Particula Primordial is a computational music research platform, not only a MIDI converter.** It connects three research components:

### 1. Computational music analysis

Transforms musical performance files into auditable event data: note pitch, duration, velocity, channel, beat position, rhythmic density, pitch-class distribution, and basic audio signal measurements.

### 2. Music information visualization

Represents MIDI events through piano-roll plots, pitch-class distributions and project/audio summaries. The dashboard exposes parameters and downloadable evidence rather than hiding transformations behind a black box.

### 3. Computational composition

Uses a user-selected tonic and scale interval recipe to generate transposed scale exercises, diatonic extended sonorities, progression variants, algorithmic melodic contours and open-ended sustained studies.

## Intended users

- Music students and teachers who want to compare scale structures and harmonic extensions.
- Producers who want to inspect and standardize MIDI material before arranging it in a DAW.
- Researchers exploring rule-based composition, MIDI representation and reproducible music analysis.

## What the current release demonstrates

- A reusable, tonic-independent software architecture.
- A Streamlit interface for analysis and generation.
- A Google Colab entry point for MIDI cleanup and scale generation.
- A REAPER integration boundary based on the host's own scripting and rendering capabilities.
- Synthetic unit tests, reproducibility documentation and explicit limitations.

## What it does not yet demonstrate

- Automatic transcription of audio recordings into MIDI.
- Automatic key or mode inference.
- Musicological validation across diverse global scale traditions.
- Perceptual evaluation of generated compositions.
- Production-grade sampled piano or orchestral rendering.
- A cloud-hosted REAPER or VST execution service.
