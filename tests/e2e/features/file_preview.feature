Feature: File selection and preview rendering
  Users can pick input scores and manage preview outcomes.

  Scenario: Render preview for selected score
    Given the arranger app is running
    And the next file open selection is "scores/example.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    Then the status bar shows "Preview rendered."
    And the app recorded a preview request for "scores/example.musicxml"

  Scenario: Cancel selecting a score
    Given the arranger app is running
    And the next file open selection is cancelled
    When the user chooses a score
    Then the status bar shows "Ready."
    And no preview requests were recorded

  Scenario: Preview failure surfaces an error
    Given the arranger app is running
    And the next file open selection is "scores/bad.musicxml"
    And the preview service will fail with "Preview failed to build"
    When the user chooses a score
    And the user renders previews
    Then the status bar shows "Preview failed: Preview failed to build"
    And the last preview attempt failed
    And an error dialog was shown with title "Preview failed"
    And the error message contains "Preview failed to build"

  Scenario: Re-rendering without changes re-runs the preview build
    Given the arranger app is running
    And the next file open selection is "scores/repeat.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the user renders previews
    Then the preview service recorded 3 calls
    And the status bar shows "Preview rendered."
