from __future__ import annotations

from tests.helpers import require_ttkbootstrap

require_ttkbootstrap()

from pathlib import Path
from pytest_bdd import given, then, when, parsers

from ocarina_gui import themes
from ocarina_gui.pdf_export.types import PdfExportOptions

from tests.e2e.harness import E2EHarness


@given("the arranger app is running", target_fixture="arranger_app")
def arranger_app(e2e_app: E2EHarness) -> E2EHarness:
    e2e_app.ensure_preview_successes(4)
    return e2e_app


@given("the arranger app uses the light theme")
def ensure_light_theme(arranger_app: E2EHarness) -> None:
    themes.set_active_theme("light")
    arranger_app.window.update_idletasks()


@given(parsers.parse('the next file open selection is "{filename}"'))
def queue_file_open(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("<score/>", encoding="utf-8")
    arranger_app.queue_open_path(str(path))


@given("the next file open selection is cancelled")
def cancel_file_open(arranger_app: E2EHarness) -> None:
    arranger_app.queue_open_path(None)


@given(parsers.parse('the next save destination is "{filename}"'))
def queue_save_destination(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    arranger_app.queue_save_path(str(path))


@given("the next save destination is cancelled")
def cancel_save_destination(arranger_app: E2EHarness) -> None:
    arranger_app.queue_save_path(None)


@given(parsers.parse('the next project save destination is "{filename}"'))
@when(parsers.parse('the next project save destination is "{filename}"'))
def queue_project_save(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    arranger_app.queue_save_project_path(str(path))


@given(parsers.parse('the next project open selection is "{filename}"'))
@when(parsers.parse('the next project open selection is "{filename}"'))
def queue_project_open(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    path = tmp_path / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    arranger_app.queue_open_project_path(str(path))


@given("the next project open selection is cancelled")
def cancel_project_open(arranger_app: E2EHarness) -> None:
    arranger_app.queue_open_project_path(None)


@given("the PDF export options are customised by the user")
def customise_pdf_options(arranger_app: E2EHarness) -> None:
    options = PdfExportOptions(
        page_size="letter",
        orientation="landscape",
        columns=1,
        include_piano_roll=False,
        include_staff=True,
        include_text=False,
        include_fingerings=True,
    )
    arranger_app.set_pdf_options(options)


@when("the user chooses a score")
def choose_score(arranger_app: E2EHarness) -> None:
    arranger_app.window.browse()


@when("the user renders previews")
def render_previews(arranger_app: E2EHarness) -> None:
    arranger_app.last_preview_result = arranger_app.window.render_previews()


@when("the user renders previews successfully")
def render_previews_success(arranger_app: E2EHarness) -> None:
    result = arranger_app.window.render_previews()
    arranger_app.last_preview_result = result
    assert result.is_ok(), "Expected preview rendering to succeed"


@when("the user converts the score")
def convert_score(arranger_app: E2EHarness) -> None:
    result = arranger_app.window.convert()
    arranger_app.last_conversion_result = result


@then(parsers.parse('the status bar shows "{message}"'))
def status_bar_message(arranger_app: E2EHarness, message: str) -> None:
    assert arranger_app.window.status.get() == message


@then(parsers.parse('the app recorded a preview request for "{filename}"'))
def preview_request_recorded(arranger_app: E2EHarness, tmp_path: Path, filename: str) -> None:
    expected_path = str(tmp_path / filename)
    assert arranger_app.score_service.preview_calls, "No preview calls were recorded"
    last_call = arranger_app.score_service.preview_calls[-1]
    assert last_call.path == expected_path


@then("no preview requests were recorded")
def no_preview_requests(arranger_app: E2EHarness) -> None:
    assert not arranger_app.score_service.preview_calls


@then("the preview service was called once")
def preview_called_once(arranger_app: E2EHarness) -> None:
    assert len(arranger_app.score_service.preview_calls) == 1


@then(parsers.parse("the preview service recorded {count:d} calls"))
def preview_call_count(arranger_app: E2EHarness, count: int) -> None:
    assert len(arranger_app.score_service.preview_calls) == count


@then(parsers.parse('an error dialog was shown with title "{title}"'))
def error_dialog_shown(arranger_app: E2EHarness, title: str) -> None:
    assert any(args[0][0] == title for args in arranger_app.messagebox.showerror_calls), (
        f"Expected an error dialog titled {title!r}"
    )


@then(parsers.parse('an info dialog was shown with title "{title}"'))
def info_dialog_shown(arranger_app: E2EHarness, title: str) -> None:
    assert any(args[0][0] == title for args in arranger_app.messagebox.showinfo_calls), (
        f"Expected an info dialog titled {title!r}"
    )


@then(parsers.parse('the error message contains "{expected}"'))
def error_message_contains(arranger_app: E2EHarness, expected: str) -> None:
    for positional, keyword in arranger_app.messagebox.showerror_calls:
        if len(positional) > 1 and expected in str(positional[1]):
            return
        message = keyword.get("message")
        if message is not None and expected in str(message):
            return
    raise AssertionError(f"Expected an error message containing {expected!r}")


@then("the conversion completes successfully")
def conversion_completed(arranger_app: E2EHarness) -> None:
    convert_calls = arranger_app.score_service.convert_calls
    assert convert_calls, "Conversion command was not invoked"
    assert arranger_app.messagebox.showinfo_calls, "Success dialog was not shown"
    assert arranger_app.opened_paths, "Export folder was not opened for the user"


@then(parsers.parse('the conversion request used "{input_filename}" and "{output_filename}"'))
def conversion_request_targets(
    arranger_app: E2EHarness,
    tmp_path: Path,
    input_filename: str,
    output_filename: str,
) -> None:
    expected_input = str(tmp_path / input_filename)
    expected_output = str(tmp_path / output_filename)
    call = arranger_app.score_service.convert_calls[-1]
    assert call.input_path == expected_input
    assert call.output_path == expected_output
    assert call.pdf_options == arranger_app.pdf_options


@then("no conversion calls were recorded")
def no_conversion_calls(arranger_app: E2EHarness) -> None:
    assert not arranger_app.score_service.convert_calls


@then("no info dialogs were shown")
def no_info_dialogs(arranger_app: E2EHarness) -> None:
    assert not arranger_app.messagebox.showinfo_calls


@then("no error dialogs were shown")
def no_error_dialogs(arranger_app: E2EHarness) -> None:
    assert not arranger_app.messagebox.showerror_calls
