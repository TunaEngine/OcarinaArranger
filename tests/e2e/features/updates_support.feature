Feature: Updates and support entry points
  Users can check for updates and access support resources.

  Scenario: Manual update installs the available release
    Given the arranger app is running
    And an update is available with version "1.2.3"
    When the user runs a manual update check
    Then the user was prompted to install the update
    And an info dialog was shown with title "Update Available"
    And the update installer was launched

  Scenario: Manual update failure shows an error
    Given the arranger app is running
    And the update check will fail with "Network unavailable"
    When the user runs a manual update check
    Then an error dialog was shown with title "Check for Updates"
    And the error message contains "Network unavailable"
    And no update was downloaded

  Scenario: Declining the update keeps the installer idle
    Given the arranger app is running
    And an update is available with version "1.2.4"
    And the user declines the update prompt
    When the user runs a manual update check
    Then no update was downloaded

  Scenario: Enabling automatic updates persists the preference
    Given the arranger app is running
    When automatic updates are toggled on
    Then the auto update preference is true

  Scenario: Selecting the beta update channel persists the choice
    Given the arranger app is running
    And an update channel "beta" service is registered
    When the user selects the "Beta Releases" update channel
    Then the update channel preference is "beta"

  Scenario: Prior update failure notice is displayed
    Given the arranger app is running
    And a prior update failure notice reports "Hash mismatch" with advice "Download again"
    Then an error dialog was shown with title "Update Failed"
    And the error message contains "Hash mismatch"

  Scenario: Opening the feedback form launches the browser
    Given the arranger app is running
    When the user opens the feedback form
    Then a browser tab opened for "forms"
    And the support form router is "General feedback"

  Scenario: Opening the Discord link launches the browser
    Given the arranger app is running
    When the user opens the Discord community link
    Then a browser tab opened for "discord"

  Scenario: Reporting a problem routes to the bug report form
    Given the arranger app is running
    When the user opens the report a problem form
    Then a browser tab opened for "forms"
    And the support form router is "Bug report"

  Scenario: Suggesting a feature routes to the feature request form
    Given the arranger app is running
    When the user opens the suggest a feature form
    Then a browser tab opened for "forms"
    And the support form router is "Feature request"

  Scenario: Opening the instrument layout editor in headless mode reports the limitation
    Given the arranger app is running
    When the user opens the instrument layout editor
    Then the status bar shows "Layout editor requires a graphical display."
    And no instrument layout editor window was created
