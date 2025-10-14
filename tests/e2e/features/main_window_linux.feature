Feature: Linux X11 automation for the main window
  These scenarios reuse keyboard navigation to exercise the Ocarina Arranger
  menus under an Openbox-managed X11 session.

  Background:
    Given the Ocarina Arranger app is launched with Linux X11 automation

  @e2e @linux
  Scenario: Drive the File menu via xdotool
    Then xdotool should detect a window titled "Ocarina Arranger"
    And the Linux Ocarina Arranger window title should start with "Ocarina Arranger v"
    When on Linux I send the keys "alt+F Down Escape" to the Ocarina Arranger window
    Then the Linux Ocarina Arranger process should still be running

  @e2e @linux
  Scenario: Drive the Tools menu via xdotool
    When on Linux I send the keys "alt+T Down Escape" to the Ocarina Arranger window
    Then the Linux Ocarina Arranger process should still be running

  @e2e @linux
  Scenario: Drive the Help menu via xdotool
    When on Linux I send the keys "alt+H Down Escape" to the Ocarina Arranger window
    Then the Linux Ocarina Arranger process should still be running

  @e2e @linux
  Scenario: Capture light and dark theme screenshots for documentation
    Then xdotool should detect a window titled "Ocarina Arranger"
    And on Linux I wait 1.5 seconds
    And on Linux I capture a full screen screenshot named "main-window"
    When on Linux I select the "fingerings" tab via automation
    And on Linux I wait 1.0 seconds
    Then on Linux I capture a screenshot of the active window named "tab-fingerings"
    When on Linux I select the "original" tab via automation
    And on Linux I wait for the seeded preview data to render
    And on Linux I wait 0.3 seconds
    And on Linux I capture a screenshot of the active window named "tab-original"
    When on Linux I select the "arranged" tab via automation
    And on Linux I wait for the seeded preview data to render
    And on Linux I wait 0.3 seconds
    And on Linux I capture a screenshot of the active window named "tab-arranged"
    And on Linux I wait 0.4 seconds
    When on Linux I open the Instrument Layout Editor via the menu
    And on Linux I wait 1.0 seconds
    When on Linux I focus the window titled "Instrument Layout Editor"
    Then on Linux I capture a screenshot of the active window named "instrument-layout-editor"
    When on Linux I send the keys "alt+F4" to the window titled "Instrument Layout Editor"
    When on Linux I focus the window titled "Ocarina Arranger"
    When on Linux I open the Third-Party Licenses via the menu
    And on Linux I wait 0.5 seconds
    When on Linux I focus the window titled "Third-Party Licenses"
    Then on Linux I capture a screenshot of the active window named "third-party-licenses"
    When on Linux I send the keys "alt+F4" to the window titled "Third-Party Licenses"
    When on Linux I focus the window titled "Ocarina Arranger"
    When on Linux I activate the "dark" theme via automation
    And on Linux I wait 0.8 seconds
    And on Linux I capture a full screen screenshot named "main-window-dark"
    When on Linux I select the "fingerings" tab via automation
    And on Linux I wait 0.5 seconds
    Then on Linux I capture a screenshot of the active window named "tab-fingerings-dark"
    When on Linux I select the "original" tab via automation
    And on Linux I wait 0.3 seconds
    And on Linux I capture a screenshot of the active window named "tab-original-dark"
    When on Linux I select the "arranged" tab via automation
    And on Linux I wait 0.3 seconds
    And on Linux I capture a screenshot of the active window named "tab-arranged-dark"
    And on Linux I wait 0.4 seconds
    When on Linux I open the Instrument Layout Editor via the menu
    And on Linux I wait 0.5 seconds
    When on Linux I focus the window titled "Instrument Layout Editor"
    Then on Linux I capture a screenshot of the active window named "instrument-layout-editor-dark"
    When on Linux I send the keys "alt+F4" to the window titled "Instrument Layout Editor"
    When on Linux I focus the window titled "Ocarina Arranger"
    When on Linux I open the Third-Party Licenses via the menu
    And on Linux I wait 0.5 seconds
    When on Linux I focus the window titled "Third-Party Licenses"
    Then on Linux I capture a screenshot of the active window named "third-party-licenses-dark"
    When on Linux I send the keys "alt+F4" to the window titled "Third-Party Licenses"
    When on Linux I focus the window titled "Ocarina Arranger"
    And on Linux I activate the "light" theme via automation
    Then the Linux Ocarina Arranger process should still be running
