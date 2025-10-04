"""Pytest configuration applied to the entire test suite."""

# Ensure all BDD step definition modules load before feature parsing so
# pytest-bdd can match scenario text to the registered steps, regardless of
# which subset of tests is collected.
pytest_plugins = [
    "tests.e2e.steps.common",
    "tests.e2e.steps.conversion",
    "tests.e2e.steps.preview",
    "tests.e2e.steps.preview_controls",
    "tests.e2e.steps.projects",
    "tests.e2e.steps.transform",
    "tests.e2e.steps.updates_support",
    "tests.e2e.steps.window",
    "tests.e2e.steps.view_preferences",
]
