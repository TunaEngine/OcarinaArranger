Feature: Window lifecycle
  Users can complete a full session and close the application without errors.

  Scenario: Closing the window after arranging a score
    Given the arranger app is running
    And the next file open selection is "scores/session.musicxml"
    And the next save destination is "exports/session.musicxml"
    And the next project save destination is "projects/session.ocarina"
    When the user chooses a score
    And the user renders previews successfully
    And the user converts the score
    And the user saves the project
    And the user closes the application
    Then the window teardown completed
