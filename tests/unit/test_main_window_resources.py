from ui.main_window.initialisation import _get_main_window_resource


def test_get_main_window_resource_returns_traversable_for_icon() -> None:
    resource = _get_main_window_resource("app_icon.png")

    assert resource is not None
    assert resource.name == "app_icon.png"
    assert resource.is_file()


def test_get_main_window_resource_returns_none_for_missing_file() -> None:
    missing = _get_main_window_resource("does_not_exist.png")

    assert missing is None
