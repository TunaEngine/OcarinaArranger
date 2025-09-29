from ocarina_gui.headless import HeadlessStaffView


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
