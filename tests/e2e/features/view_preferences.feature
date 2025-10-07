Feature: View and logging preferences
  Users can switch themes and log verbosity via the application menus.

  Scenario: Switching to the dark theme via the View menu persists the choice
    Given the arranger app is running
    When the user selects the "Dark" theme from the View menu
    Then the active theme is "Dark"
    And the theme preference was saved as "dark"
    And a theme diagnostic log was emitted for "dark"

  Scenario: Selecting verbose log output persists the setting
    Given the arranger app is running
    And log verbosity changes are tracked
    When the user selects "Verbose" log verbosity from the Logs menu
    Then log verbosity was applied as "verbose"
    And the log verbosity preference was saved as "verbose"
