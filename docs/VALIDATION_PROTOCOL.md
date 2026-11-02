# Validation protocol

## Software-level tests

The automated suite should check the following invariants:

1. **Tonic parsing:** enharmonic names such as F-sharp and G-flat map to the same pitch class.
2. **Scale transposition:** a scale's interval vector remains identical under tonic transposition.
3. **Normalization pitch preservation:** output note pitches, velocity and channel match input note events in the selected tracks.
4. **Onset quantization:** every output onset is an integer multiple of the selected beat grid relative to the new origin.
5. **Duration standardization:** when uniform duration is enabled, all output notes have the selected duration in beats.
6. **Meter and tempo metadata:** normalized MIDI contains one fixed target tempo and a 4/4 time-signature event.
7. **Composition structure:** each progression MIDI has harmony and melody tracks, eight bars, and deterministic outputs for a fixed seed.
8. **Audio file validity:** reference WAV files can be opened and report a nonzero duration and expected sample rate.
9. **RPP inventory:** synthetic project fixtures return expected track, item, position, length, tempo and meter values.

## Empirical validation beyond unit tests

The following studies are proposed, not yet completed:

- Test with a corpus of monophonic scale performances recorded at multiple tempi and with variable expressive timing.
- Measure onset displacement before and after quantization, including median absolute displacement and maximum displacement in milliseconds.
- Measure duration variance before and after fixed-duration normalization.
- Blind-listen to normalized MIDI in several instruments to identify grid choices that damage articulation or phrasing.
- Compare algorithmic outputs with manually composed references for tonal adherence, voice-leading, register, repetition and perceived variety.
- Compare the reference synthesizer with a REAPER/SoundFont render only for workflow demonstration, not as a claim of equal sound quality.
- Record software versions, PPQ, tempo, grid, duration, tonic, scale recipe, algorithm, seed and output hashes for every reproducibility run.

## Limitations

- The normalizer handles note events; it does not preserve all source controller, pitch-bend, aftertouch, program-change, SysEx or automation data.
- Tempo and meter in the standardized output are intentionally flattened to one BPM and 4/4.
- The current tonal engine is 12-TET and uses semitone interval recipes.
- Diatonic chord-symbol naming can be approximate for synthetic or non-heptatonic scales.
- The RPP parser is an inventory parser, not a complete interpreter of REAPER's evolving state-chunk format.
- The additive audio renderer is a reference preview rather than production instrument synthesis.
- The current software tests validate code invariants, not human musical preference or artistic quality.
