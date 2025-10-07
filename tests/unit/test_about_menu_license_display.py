from ui.main_window.menus.about import _APP_LICENSE_PREAMBLE, _compose_license_display


def test_compose_license_display_returns_preamble_when_third_party_text_missing():
    assert _compose_license_display("") == _APP_LICENSE_PREAMBLE


def test_compose_license_display_prefixes_preamble_to_third_party_text():
    third_party = "Package: example\nLicense text"
    result = _compose_license_display(third_party)

    assert result.startswith(_APP_LICENSE_PREAMBLE + "\n\n")
    assert result.endswith(third_party)
