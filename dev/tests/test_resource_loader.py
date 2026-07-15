from pathlib import Path

from meadowpy.resources import resource_icons, resource_loader
from meadowpy.resources.theme_colors import resolve_accent_shades


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


def test_custom_accent_shades_and_default_fallbacks():
    shades = resolve_accent_shades("custom", True, "#336699")

    assert shades == {
        "ACCENT": "#336699",
        "ACCENT_HOVER": "#24476B",
        "ACCENT_TINT": "#B9CCDF",
        "ACCENT_BRIGHT": "#5E94C9",
        "ACCENT_HOVER_BRIGHT": "#3D7AB8",
    }
    assert (
        resource_loader.current_accent_hex("custom", custom_base="light")
        == "#2E7D32"
    )
    assert (
        resource_loader.current_accent_hex("custom", custom_base="dark")
        == "#2F7A44"
    )
    assert resource_loader.run_button_accent_hex("custom") == "#4CAF50"


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
    assert "#kwHelpTitle {\n    color: #123456;" in stylesheet


def test_preferences_inputs_use_accent_selection_color():
    stylesheet = resource_loader.get_stylesheet(
        "custom",
        custom_base="dark",
        custom_accent="#123456",
    )

    assert (
        "QSpinBox, QComboBox, QFontComboBox {\n"
        "    border: 1px solid #555555;"
    ) in stylesheet
    assert "selection-background-color: #123456;" in stylesheet


def test_output_ai_analysis_button_uses_theme_accent():
    stylesheet = resource_loader.get_stylesheet(
        "custom",
        custom_base="dark",
        custom_accent="#123456",
    )
    hover = resource_loader.darken_color("#123456", 0.12)

    assert "#outputFixAIBtn {\n    background: #123456;" in stylesheet
    assert f"#outputFixAIBtn:hover {{\n    background: {hover};" in stylesheet
    assert "#outputFixAIBtn {\n    background: #2F5C88;" not in stylesheet
    assert "#outputFixAIBtn:hover {\n    background: #3A6FA0;" not in stylesheet


def test_keyword_help_title_uses_theme_accent_text_color():
    light_stylesheet = resource_loader.get_stylesheet("default_light")
    dark_stylesheet = resource_loader.get_stylesheet("default_dark")
    high_contrast_stylesheet = resource_loader.get_stylesheet("default_high_contrast")

    assert "#kwHelpTitle {\n    color: #2E7D32;" in light_stylesheet
    assert "#kwHelpTitle {\n    color: #4CAF50;" in dark_stylesheet
    assert "#kwHelpTitle {\n    color: #FFFFFF;" in high_contrast_stylesheet


def test_stylesheets_use_inset_square_popup_menu_geometry():
    light_stylesheet = resource_loader.get_stylesheet("default_light")
    dark_stylesheet = resource_loader.get_stylesheet("default_dark")
    high_contrast_stylesheet = resource_loader.get_stylesheet("default_high_contrast")

    for stylesheet in (light_stylesheet, dark_stylesheet):
        assert (
            "QMenu {\n"
            "    background:"
        ) in stylesheet
        menu_block_start = stylesheet.index("QMenu {\n")
        menu_block = stylesheet[menu_block_start:stylesheet.index("}", menu_block_start)]
        model_menu_block_start = stylesheet.index("#modelSelectorMenu {\n")
        model_menu_block = stylesheet[
            model_menu_block_start:stylesheet.index("}", model_menu_block_start)
        ]
        assert "border-radius: 0px;" in menu_block
        assert "border-radius: 0px;" in model_menu_block
        assert (
            "QMenu::item {\n"
            "    padding: 7px 42px 7px 14px;\n"
            "    margin: 1px 2px;\n"
            "    border-radius: 0px;"
        ) in stylesheet
        assert (
            "#modelSelectorMenu::item {\n"
            "    padding: 7px 42px 7px 14px;\n"
            "    margin: 1px 2px;\n"
            "    border-radius: 0px;"
        ) in stylesheet
        assert "QMenu::separator {\n    height: 1px;" in stylesheet
        assert "#modelSelectorMenu::separator {\n    height: 1px;" in stylesheet

    assert (
        "QMenu {\n"
        "    border: 2px solid #FFFFFF;\n"
        "    border-radius: 0px;\n"
        "    padding: 7px 6px;"
    ) in high_contrast_stylesheet
    assert (
        "QMenu::item {\n"
        "    color: #FFFFFF;\n"
        "    padding: 7px 42px 7px 14px;\n"
        "    margin: 1px 2px;\n"
        "    border-radius: 0px;"
    ) in high_contrast_stylesheet
    assert "QMenu::separator {\n    height: 2px;" in high_contrast_stylesheet


def test_get_stylesheet_applies_high_contrast_overrides():
    stylesheet = resource_loader.get_stylesheet("default_high_contrast")

    assert "High Contrast accessibility overrides" in stylesheet
    assert "#FFFFFF" in stylesheet


def test_lint_preferences_scroll_surface_is_styled_for_every_theme():
    light_stylesheet = resource_loader.get_stylesheet("default_light")
    dark_stylesheet = resource_loader.get_stylesheet("default_dark")
    high_contrast_stylesheet = resource_loader.get_stylesheet(
        "default_high_contrast"
    )

    for stylesheet in (
        light_stylesheet,
        dark_stylesheet,
        high_contrast_stylesheet,
    ):
        assert "QScrollArea#lintPreferencesScroll" in stylesheet
        assert "QWidget#lintPreferencesContent QGroupBox" in stylesheet
        assert "QWidget#lintPreferencesContent QGroupBox::title" in stylesheet

    high_contrast_override = high_contrast_stylesheet.rindex(
        "QScrollArea#lintPreferencesScroll"
    )
    assert "background: #000000;" in high_contrast_stylesheet[
        high_contrast_override:
    ]
    assert "border: 2px solid #FFFFFF;" in high_contrast_stylesheet[
        high_contrast_override:
    ]


def test_high_contrast_stylesheet_allows_missing_optional_overrides(monkeypatch, tmp_path):
    styles_dir = tmp_path / "styles"
    styles_dir.mkdir()
    (styles_dir / "meadowpy_dark.qss").write_text(
        "QWidget { background: #252526; color: {{ACCENT}}; "
        "image: url({{ICONS_DIR}}/run.svg); }",
        encoding="utf-8",
    )
    monkeypatch.setattr(resource_loader, "_RESOURCES_DIR", tmp_path)

    stylesheet = resource_loader.get_stylesheet("default_high_contrast")

    assert "QWidget" in stylesheet
    assert "{{" not in stylesheet
    assert "#000000" in stylesheet
    assert "#FFFFFF" in stylesheet
    assert "High Contrast accessibility overrides" not in stylesheet


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


def test_load_themed_icon_falls_back_when_high_contrast_rendering_fails(
    monkeypatch, qapp
):
    class UnreadablePath:
        def __init__(self, path):
            self.path = path

        def read_text(self, encoding):
            raise OSError("cannot recolor svg")

    monkeypatch.setattr(resource_icons, "Path", UnreadablePath)

    icon = resource_loader.load_themed_icon("run", theme_name="default_high_contrast")

    assert icon.isNull() is False


def test_load_tinted_icon_renders_existing_template(qapp):
    icon = resource_loader.load_tinted_icon("new_file_tinted", "#FF0000", size=20)

    assert icon.isNull() is False


def test_get_font_path_returns_empty_for_missing_font():
    assert resource_loader.get_font_path("missing-font.ttf") == ""


def test_get_icon_path_returns_empty_for_missing_icon():
    assert resource_loader.get_icon_path("missing-icon") == ""


def test_load_themed_icon_returns_empty_icon_for_missing_asset(qapp):
    icon = resource_loader.load_themed_icon("missing-icon")

    assert icon.isNull()
