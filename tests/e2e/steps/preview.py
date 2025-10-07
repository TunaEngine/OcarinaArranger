from __future__ import annotations

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from pytest_bdd import given, parsers, then

from tests.e2e.harness import E2EHarness


@given(parsers.parse('the preview service will fail with "{message}"'))
def preview_service_failure(arranger_app: E2EHarness, message: str) -> None:
    error = RuntimeError(message)
    arranger_app.set_preview_outcomes([error, error])


@then("the last preview attempt failed")
def last_preview_failed(arranger_app: E2EHarness) -> None:
    result = arranger_app.last_preview_result
    assert result is not None and result.is_err(), "Expected the preview result to be an error"

