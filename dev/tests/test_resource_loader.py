from pathlib import Path

from meadowpy.resources import resource_loader


def test_get_icon_and_font_path_return_existing_assets():
    icon_path = resource_loader.get_icon_path("run")
    font_path = resource_loader.get_font_path("Inter-Regular.ttf")

    assert icon_path.endswith(".svg")
    assert Path(icon_path).is_file()
    assert Path(font_path).is_file()


def test_theme_helpers_and_accent_resolution():
    assert resource_loader.theme_is_dark("default_dark") is True
    assert resource_loader.theme_is_dark("custom", custom_base="light") is False
    assert resource_loader.theme_is_high_contrast("default_high_contrast") is True
    assert resource_loader.current_accent_hex("default_high_contrast") == "#FFFFFF"
    assert resource_loader.run_button_accent_hex("default_dark") == "#4CAF50"


def test_color_helpers_return_original_on_invalid_input():
    assert resource_loader.darken_color("invalid") == "invalid"
    assert resource_loader.lighten_color("invalid") == "invalid"


def test_get_stylesheet_replaces_placeholders_for_custom_theme():
    stylesheet = resource_loader.get_stylesheet(
        "custom",
        custom_base="light",
        custom_accent="#123456",
    )

    assert "{{ACCENT" not in stylesheet
    assert "{{ICONS_DIR}}" not in stylesheet
    assert "#123456" in stylesheet


def test_get_stylesheet_applies_high_contrast_overrides():
    stylesheet = resource_loader.get_stylesheet("default_high_contrast")

    assert "High Contrast accessibility overrides" in stylesheet
    assert "#FFFFFF" in stylesheet


def test_get_stylesheet_returns_empty_when_template_is_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(resource_loader, "_RESOURCES_DIR", tmp_path)

    assert resource_loader.get_stylesheet("default_light") == ""


def test_load_tinted_icon_returns_empty_icon_for_missing_asset(qapp):
    icon = resource_loader.load_tinted_icon("missing-icon", "#FFFFFF")

    assert icon.isNull()


def test_load_themed_icon_falls_back_to_plain_icon_for_standard_theme(qapp):
    icon = resource_loader.load_themed_icon("run", theme_name="default_dark")

    assert icon.isNull() is False


def test_load_themed_icon_renders_high_contrast_variant(qapp):
    icon = resource_loader.load_themed_icon("run", theme_name="default_high_contrast")

    assert icon.isNull() is False


def test_load_tinted_icon_renders_existing_template(qapp):
    icon = resource_loader.load_tinted_icon("new_file_tinted", "#FF0000", size=20)

    assert icon.isNull() is False


def test_get_font_path_returns_empty_for_missing_font():
    assert resource_loader.get_font_path("missing-font.ttf") == ""
