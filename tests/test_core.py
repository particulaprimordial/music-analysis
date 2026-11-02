from pathlib import Path

import mido
import pandas as pd

from particula.audio import audio_features, render_reference_wav
from particula.composition import PROGRESSION_TEMPLATES, make_ascension_midi, make_progression_midi
from particula.midi_tools import inspect_midi, normalize_midi
from particula.rpp import parse_rpp
from particula.theory import SCALES, diatonic_chord, make_scale_midi, parse_tonic, scale_midi_notes


def make_input_midi(path: Path):
    mid = mido.MidiFile(ticks_per_beat=480)
    track = mido.MidiTrack()
    mid.tracks.append(track)
    track.append(mido.MetaMessage("track_name", name="Piano", time=0))
    # Deliberately off-grid starts and different lengths.
    events = [
        (37, 1, mido.Message("note_on", note=62, velocity=90, channel=0, time=0)),
        (241, 1, mido.Message("note_on", note=65, velocity=87, channel=0, time=0)),
        (299, 0, mido.Message("note_off", note=62, velocity=0, channel=0, time=0)),
        (699, 0, mido.Message("note_off", note=65, velocity=0, channel=0, time=0)),
    ]
    last = 0
    for tick, _priority, msg in sorted(events, key=lambda x: (x[0], x[1])):
        msg.time = tick - last
        track.append(msg)
        last = tick
    track.append(mido.MetaMessage("end_of_track", time=1))
    mid.save(path)
    return path


def test_any_tonic_scale_transposition():
    assert parse_tonic("C") == 0
    assert parse_tonic("F#") == parse_tonic("Gb") == 6
    c = scale_midi_notes("C", "Major (Ionian)", 1, 4)
    f = scale_midi_notes("F", "Major (Ionian)", 1, 4)
    assert [x % 12 for x in c] == [0, 2, 4, 5, 7, 9, 11, 0]
    assert [x % 12 for x in f] == [5, 7, 9, 10, 0, 2, 4, 5]


def test_scale_catalog_has_multiple_families():
    assert len(SCALES) >= 20
    assert make_scale_midi("Bb", "Harmonic Minor").tracks


def test_diatonic_extensions_stay_scale_derived():
    pitches, symbol = diatonic_chord("C", "Major (Ionian)", 0, 13)
    assert len(pitches) == 7
    assert isinstance(symbol, str) and symbol
    # All pitch classes are in the selected C major scale.
    assert all(p % 12 in {0, 2, 4, 5, 7, 9, 11} for p in pitches)


def test_normalizer_snaps_and_standardizes(tmp_path):
    src = make_input_midi(tmp_path / "source.mid")
    out, stats = normalize_midi(src, tmp_path / "normalized.mid", bpm=100, grid_beats=0.5,
                                note_duration_beats=0.9, track_index=0)
    notes, _ = inspect_midi(out)
    assert stats["input_notes"] == stats["output_notes"] == 2
    assert list(notes["start_beats"]) == [0.0, 0.5]
    assert all(abs(x - 0.9) < 1e-6 for x in notes["duration_beats"])
    assert list(notes["pitch"]) == [62, 65]


def test_normalizer_all_tracks(tmp_path):
    src = make_input_midi(tmp_path / "source.mid")
    out, stats = normalize_midi(src, tmp_path / "all.mid", all_tracks=True)
    assert stats["output_tracks"] == 1
    assert out.exists()


def test_progression_studies_generate_midi():
    assert len(PROGRESSION_TEMPLATES) == 7
    mid, chords = make_progression_midi("F#", "Dorian", "01 · Tonic departure", algorithm_index=2)
    assert len(mid.tracks) == 2
    assert len(chords) == 8
    notes, _ = inspect_midi(mid)
    assert len(notes) >= 64


def test_ascension_is_extensible_and_has_notes():
    mid = make_ascension_midi("Eb", "Lydian", bars=16)
    notes, _ = inspect_midi(mid)
    assert not notes.empty
    assert notes.end_beats.max() > 16 * 4


def test_reference_audio_and_features(tmp_path):
    mid = make_scale_midi("A", "Natural Minor (Aeolian)", octaves=1)
    midi_path = tmp_path / "scale.mid"
    wav_path = tmp_path / "scale.wav"
    mid.save(midi_path)
    render_reference_wav(midi_path, wav_path, sample_rate=8000)
    features = audio_features(wav_path)
    assert features["duration_seconds"] > 0
    assert 0 <= features["peak"] <= 1
    assert features["sample_rate"] == 8000


def test_rpp_inventory_parser(tmp_path):
    project = tmp_path / "test.rpp"
    project.write_text('''<REAPER_PROJECT 0.1 "7.0" 0\nTEMPO 120 4 4\n<TRACK {ABC}\nNAME "Piano"\n<ITEM\nPOSITION 1.25\nLENGTH 4.0\n<SOURCE MIDI\nFILE "piano.mid"\n>\n>\n>\n>\n''', encoding="utf-8")
    result = parse_rpp(project)
    assert result["track_count"] == 1
    assert result["item_count"] == 1
    assert result["tempo_bpm"] == 120
    assert result["time_signature"] == "4/4"
    assert result["tracks"][0]["name"] == "Piano"
    assert result["tracks"][0]["items"][0]["position_seconds"] == 1.25


def test_all_track_normalization_keeps_relative_entry_offsets(tmp_path):
    mid = mido.MidiFile(type=1, ticks_per_beat=480)
    t0 = mido.MidiTrack(); t1 = mido.MidiTrack(); mid.tracks.extend([t0, t1])
    t0.extend([mido.MetaMessage("track_name", name="A", time=0),
               mido.Message("note_on", note=60, velocity=80, time=100),
               mido.Message("note_off", note=60, velocity=0, time=200)])
    t1.extend([mido.MetaMessage("track_name", name="B", time=0),
               mido.Message("note_on", note=67, velocity=80, time=580),
               mido.Message("note_off", note=67, velocity=0, time=200)])
    src = tmp_path / "two_tracks.mid"; mid.save(src)
    out, stats = normalize_midi(src, tmp_path / "two_tracks_norm.mid", grid_beats=0.25, all_tracks=True)
    note_table, _ = inspect_midi(out)
    a = note_table[note_table.track_name == "A"].iloc[0].start_beats
    b = note_table[note_table.track_name == "B"].iloc[0].start_beats
    assert abs((b - a) - 1.0) < 1e-6
    assert stats["output_tracks"] == 2
