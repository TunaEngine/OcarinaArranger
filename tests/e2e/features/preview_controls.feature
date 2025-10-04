Feature: Preview playback controls
  Users can tweak playback tempo, looping, and auto-scroll modes.

  Background:
    Given the arranger app is running
    And the next file open selection is "scores/playback.musicxml"
    When the user chooses a score
    And the user renders previews successfully

  Scenario: Adjusting tempo updates playback state
    When the user adjusts the arranged preview tempo to 140 bpm
    Then the arranged preview playback tempo is 140 bpm

  Scenario: Enabling looping captures loop bounds
    When the user enables looping from beat 2 to 4
    Then the arranged preview loop spans beats 2 to 4

  Scenario: Switching auto scroll mode persists the preference
    When the user switches auto scroll mode to "continuous"
    Then the auto scroll preference is "continuous"

  Scenario: Toggling the metronome updates playback state
    When the user enables the arranged metronome
    Then the arranged preview metronome is enabled

  Scenario: Changing the preview layout persists the preference
    When the user switches preview layout mode to "staff"
    Then the preview layout preference is "staff"
