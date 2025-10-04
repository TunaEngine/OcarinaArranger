Feature: Score conversion and export
  Users can convert arranged scores and handle cancellation or failure.

  Scenario: Convert a selected score successfully
    Given the arranger app is running
    And the next file open selection is "scores/convert.musicxml"
    And the next save destination is "exports/convert.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the user converts the score
    Then the conversion completes successfully
    And the conversion request used "scores/convert.musicxml" and "exports/convert.musicxml"

  Scenario: Conversion is cancelled at the save dialog
    Given the arranger app is running
    And the next file open selection is "scores/cancel.musicxml"
    And the next save destination is cancelled
    When the user chooses a score
    And the user renders previews successfully
    And the user converts the score
    Then no conversion calls were recorded
    And no info dialogs were shown
    And the status bar shows "Preview rendered."

  Scenario: Conversion failure surfaces an error
    Given the arranger app is running
    And the next file open selection is "scores/fail.musicxml"
    And the next save destination is "exports/fail.musicxml"
    And the conversion service will fail with "Unable to export"
    When the user chooses a score
    And the user renders previews successfully
    And the user converts the score
    Then the status bar shows "Conversion failed."
    And the last conversion attempt failed
    And an error dialog was shown with title "Conversion failed"
    And the error message contains "Unable to export"

  Scenario: Custom PDF options are respected
    Given the arranger app is running
    And the next file open selection is "scores/custom.musicxml"
    And the next save destination is "exports/custom.musicxml"
    And the PDF export options are customised by the user
    When the user chooses a score
    And the user renders previews successfully
    And the user converts the score
    Then the conversion request used "scores/custom.musicxml" and "exports/custom.musicxml"
