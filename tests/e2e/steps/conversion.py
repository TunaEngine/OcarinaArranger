from __future__ import annotations

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from pytest_bdd import given, parsers, then

from tests.e2e.harness import E2EHarness


@given(parsers.parse('the conversion service will fail with "{message}"'))
def conversion_service_failure(arranger_app: E2EHarness, message: str) -> None:
    arranger_app.queue_conversion_error(RuntimeError(message))


@then("the last conversion attempt failed")
def last_conversion_failed(arranger_app: E2EHarness) -> None:
    result = arranger_app.last_conversion_result
    assert result is not None and result.is_err(), "Expected the conversion result to be an error"

