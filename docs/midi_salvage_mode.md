# MIDI Salvage Mode Guide

Salvage mode is the lenient MIDI decoding strategy that keeps imports usable when
strict parsing fails. The importer switches to salvage mode automatically when
`read_midi` is called in `auto` mode and a track raises a strict decoding
error. The lenient decoder keeps reading the track, records the issues it
encountered, and produces MusicXML output whenever it can reconstruct note
boundaries.

## What Salvage Mode Guarantees

- **Forward progress:** malformed events never abort decoding once the lenient
  decoder takes over. Stray bytes, incomplete channel events, and truncated meta
  or SysEx payloads are skipped with a recorded `MidiTrackIssue`.
- **Structured reporting:** every recovery is recorded with `track_index`,
  `offset`, `tick`, and a terse description so that QA and support can trace the
  exact byte that required intervention.
- **Synthetic end-of-track markers:** when the original data omits `0xFF 0x2F 0x00`
  the decoder appends a synthetic EOT issue so downstream tooling knows that the
  track terminated early.
- **Stable running status:** salvage mode resets the running-status cache after
  corrupt events and can resume decoding when a valid status byte reappears.

## Known Limitations

- The lenient decoder cannot invent missing delta-times; overlong or fully
  malformed variable-length quantities stop decoding for the rest of the track.
- Notes without a matching note-off (or velocity-zero note-on) are dropped
  because the decoder never guesses at durations.
- Payload trimming only removes bytes that are still present in the track. If
  the payload length is overstated and the file ends immediately, no subsequent
  events can be recovered.
- Salvage mode ignores trailing junk after the end-of-track meta event. The
  bytes are left in place so tools with stricter validation can flag them later.

## Acceptance Criteria

The following scenarios must remain green to consider salvage mode healthy:

1. **VLQ overrun is contained**  
   **Given** a track whose first delta-time exceeds the 4-byte VLQ limit  
   **When** the strict decoder runs  
   **Then** it raises `ValueError("Variable-length quantity exceeds maximum length.")`  
   **And** salvage mode still produces a report with a synthetic end-of-track
   issue.

2. **Truncated channel events are reported**  
   **Given** a note-on event that omits its velocity byte  
   **When** salvage mode decodes the track  
   **Then** the result contains a `"Truncated note event"` issue and marks the
   track as synthetically terminated.

3. **Regression fixture is salvageable**  
   **Given** `tests/fixtures/midi/adagio-2-100.mid`  
   **When** the importer runs in strict mode  
   **Then** it raises `ValueError` before emitting any notes  
   **And When** the importer runs in auto/lenient mode  
   **Then** it returns at least one MusicXML note, records the ignored stray
   status byte, and reports no synthetic end-of-track markers because the fixture
   includes a valid `0xFF 0x2F 0x00` terminator.

These criteria map directly to automated tests in `tests/ocarina_tools` and
`tests/integration`, providing an executable specification of the salvage
runtime contract.
