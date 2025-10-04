from __future__ import annotations

from pytest_bdd import then, when

from tests.e2e.harness import E2EHarness


@when("the user closes the application")
def close_application(arranger_app: E2EHarness) -> None:
    arranger_app.destroy()


@then("the window teardown completed")
def teardown_completed(arranger_app: E2EHarness) -> None:
    assert arranger_app.window._playback_job is None
