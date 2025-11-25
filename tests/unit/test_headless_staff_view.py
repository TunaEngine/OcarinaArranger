from ocarina_gui.headless import HeadlessStaffView
from ocarina_tools import NoteEvent


def test_headless_staff_only_layout_wraps_and_scrolls_vertically() -> None:
    staff = HeadlessStaffView()

    staff.set_layout_mode("wrapped")

    assert getattr(staff, "_layout_mode", None) == "wrapped"
    assert staff.vbar.winfo_ismapped()
    assert not staff.hbar.winfo_ismapped()


def test_headless_staff_cursor_callback_emits_tick() -> None:
    staff = HeadlessStaffView()
    received: list[int] = []

    staff.set_cursor_callback(received.append)
    staff.set_cursor(480)

    assert received and received[-1] == 480


def test_headless_staff_expands_time_zoom_for_close_grace_notes() -> None:
    staff = HeadlessStaffView()
    staff.px_per_tick = 0.1

    events = (
        NoteEvent(0, 24, 60, 0, is_grace=True, grace_type="acciaccatura"),
        NoteEvent(6, 24, 62, 0, is_grace=True, grace_type="acciaccatura"),
    )

    staff.render(events, pulses_per_quarter=480, beats=4, beat_type=4)

    assert staff.px_per_tick == 0.1
