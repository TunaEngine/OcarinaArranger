Feature: Transform settings and instrument changes
  Users can adjust transpose offsets and switch fingering instruments.

  Background:
    Given the arranger app is running
    And the next file open selection is "scores/transform.musicxml"
    When the user chooses a score
    And the user renders previews successfully

  Scenario: Applying a transpose offset re-renders the preview
    Given another preview result is queued
    When the user applies a transpose offset of 2
    Then the transpose offset is 2
    And the preview service recorded 3 calls

  Scenario: Cancelling the transpose offset restores the previous value
    Given another preview result is queued
    When the user applies a transpose offset of 5
    And the user modifies the transpose offset to 3
    And the user cancels the transpose change
    Then the transpose offset is 5

  Scenario: Switching fingering instruments updates the range
    When the user switches the fingering instrument to "alto_c_6"
    Then the arranger instrument is alto_c_6
    And the arranged range spans C4 to F4
