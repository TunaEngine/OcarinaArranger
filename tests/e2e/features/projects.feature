Feature: Project persistence workflows
  Users can save and load arranger projects with recent history tracking.

  Scenario: Save the current project successfully
    Given the arranger app is running
    And the next file open selection is "scores/save.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the next project save destination is "projects/save.ocarina"
    When the user saves the project
    Then the project service saved to "projects/save.ocarina"
    And the status bar shows "Project saved."
    And the recent projects list contains "projects/save.ocarina"

  Scenario: Saving the project fails gracefully
    Given the arranger app is running
    And the next file open selection is "scores/save_fail.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the next project save destination is "projects/save_fail.ocarina"
    And the project service will fail to save with "Disk full"
    When the user saves the project
    Then the last project save failed
    And an error dialog was shown with title "Save Project"
    And the error message contains "Disk full"

  Scenario: Load a saved project
    Given the arranger app is running
    And the next file open selection is "scores/load.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the next project save destination is "projects/load.ocarina"
    And the user saves the project
    And the next project open selection is "projects/load.ocarina"
    When the user loads the project
    Then the project service loaded from "projects/load.ocarina"
    And the status bar shows "Preview rendered."

  Scenario: Loading failure surfaces an error
    Given the arranger app is running
    And the next project open selection is "projects/missing.ocarina"
    And loading the project will fail with "Archive missing"
    When the user loads the project
    Then the last project load failed
    And an error dialog was shown with title "Open Project"
    And the error message contains "Archive missing"

  Scenario: Cancelling the project open dialog does nothing
    Given the arranger app is running
    And the next project open selection is cancelled
    When the user loads the project
    Then no project loads were attempted
    And the status bar shows "Ready."

  Scenario: Load the most recent project from the File menu
    Given the arranger app is running
    And the next file open selection is "scores/recent.musicxml"
    When the user chooses a score
    And the user renders previews successfully
    And the next project save destination is "projects/recent.ocarina"
    And the user saves the project
    When the user loads the most recent project from the File menu
    Then the project service loaded from "projects/recent.ocarina"
    And the status bar shows "Preview rendered."

  Scenario: Exit the application through the File menu
    Given the arranger app is running
    When the user exits the application from the File menu
    Then the main window destruction sequence ran
