from __future__ import annotations

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from pytest_bdd import given, parsers, then, when

from services.update.models import ReleaseInfo, UpdateError

from tests.e2e.harness import E2EHarness
from tests.e2e.support.menu import invoke_menu_path


@given(parsers.parse('an update is available with version "{version}"'))
def queue_update(arranger_app: E2EHarness, version: str) -> None:
    service = arranger_app.update_service()
    release = ReleaseInfo(version=version, asset_name=f"ocarina-{version}.zip", download_url="https://example.com")
    service.queue_available_release(release)
    service.queue_install_success()


@given(parsers.parse('the update check will fail with "{message}"'))
def queue_update_failure(arranger_app: E2EHarness, message: str) -> None:
    service = arranger_app.update_service()
    service.queue_check_error(UpdateError(message))


@given('the user declines the update prompt')
def decline_update(arranger_app: E2EHarness) -> None:
    arranger_app.messagebox.queue_yesno_response(False)


@given(parsers.parse('a prior update failure notice reports "{reason}" with advice "{advice}"'))
def queue_failure_notice(arranger_app: E2EHarness, reason: str, advice: str) -> None:
    arranger_app.queue_update_failure_notice(reason, advice)
    arranger_app.window._notify_update_failure_if_present()


@when('the user runs a manual update check')
def run_manual_update(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Tools", "Check for Updates...")


@when('automatic updates are toggled on')
def enable_automatic_updates(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Tools", "Enable Automatic Updates")


@when('the user opens the feedback form')
def open_feedback(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Help", "Send Feedback...")


@when('the user opens the Discord community link')
def open_discord(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Help", "Community (Discord)")


@given(parsers.parse('an update channel "{channel}" service is registered'))
def register_update_channel(arranger_app: E2EHarness, channel: str) -> None:
    service = arranger_app.update_service(channel)
    arranger_app.update_builder.register(channel, service)


@when(parsers.parse('the user selects the "{label}" update channel'))
def select_update_channel(arranger_app: E2EHarness, label: str) -> None:
    invoke_menu_path(arranger_app.window, "Tools", label)


@then(parsers.parse('the update channel preference is "{channel}"'))
def assert_update_channel(arranger_app: E2EHarness, channel: str) -> None:
    assert arranger_app.window.update_channel == channel
    assert arranger_app.preferences.update_channel == channel
    assert arranger_app.saved_preferences, "No preferences were saved"
    assert arranger_app.saved_preferences[-1].update_channel == channel


@when('the user opens the instrument layout editor')
def open_instrument_layout(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Tools", "Instrument Layout Editor...")


@then('no instrument layout editor window was created')
def no_layout_editor(arranger_app: E2EHarness) -> None:
    assert getattr(arranger_app.window, "_layout_editor_window", None) is None


@when('the user opens the report a problem form')
def open_report_problem(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Help", "Report a Problem...")


@when('the user opens the suggest a feature form')
def open_suggest_feature(arranger_app: E2EHarness) -> None:
    invoke_menu_path(arranger_app.window, "Help", "Suggest a Feature...")


@then(parsers.parse('the support form router is "{router}"'))
def assert_support_router(arranger_app: E2EHarness, router: str) -> None:
    assert arranger_app.web_open_calls, "No support form URLs were opened"
    last_url = arranger_app.web_open_calls[-1]
    encoded = router.replace(" ", "+")
    assert f"entry.1276457049={encoded}" in last_url


@then("the update installer was launched")
def update_installer_launched(arranger_app: E2EHarness) -> None:
    service = arranger_app.update_service()
    assert service.download_calls, "Expected the update installer to be downloaded"


@then("no update was downloaded")
def no_update_downloaded(arranger_app: E2EHarness) -> None:
    service = arranger_app.update_service()
    assert not service.download_calls


@then("the user was prompted to install the update")
def user_prompted_for_update(arranger_app: E2EHarness) -> None:
    assert arranger_app.messagebox.askyesno_calls, "Expected an update confirmation prompt"


@then(parsers.parse('the auto update preference is {enabled}'))
def assert_auto_update_preference(arranger_app: E2EHarness, enabled: str) -> None:
    expected = enabled.lower() in {"true", "yes", "on", "1"}
    assert arranger_app.preferences.auto_update_enabled == expected


@then(parsers.parse('a browser tab opened for "{fragment}"'))
def assert_browser_open(arranger_app: E2EHarness, fragment: str) -> None:
    assert any(fragment in url for url in arranger_app.web_open_calls), f"No URL containing {fragment!r} opened"

