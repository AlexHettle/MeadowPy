"""Escape-sequence parsing and cell-grid behavior of the terminal emulator.

Output is fed straight into Terminal._process(), so no subprocess, PTY or
event loop is involved: every test checks what ends up on the screen grid,
in the cursor/mode state, or in the bytes the terminal answers with.
"""

import base64

import pytest
from PyQt6.QtWidgets import QApplication

import meadowpy.pyqtterm as pyqtterm_module
from meadowpy.pyqtterm import (
    _TerminalRow,
    _ansi_256_hex,
    _sgr_apply,
    _sgr_colour_hex,
    _sgr_new_state,
    _term_cell_style,
    _term_char_width,
    _term_erase_style,
    _term_sgr_resolve,
)
from tests.terminal_helpers import cursor, make_terminal, screen


@pytest.fixture
def term(qapp):
    terminal = make_terminal()
    yield terminal
    terminal.stop()


@pytest.fixture
def small(qapp):
    terminal = make_terminal(cols=5, rows=3)
    yield terminal
    terminal.stop()


# ---------------------------------------------------------------------------
# Color and style helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "expected"),
    [
        (0, "#000000"),
        (9, "#ff0000"),
        (15, "#ffffff"),
        (16, "#000000"),
        (21, "#0000ff"),
        (196, "#ff0000"),
        (231, "#ffffff"),
        (232, "#080808"),
        (255, "#eeeeee"),
    ],
)
def test_ansi_256_palette_covers_named_cube_and_gray_ramp(index, expected):
    assert _ansi_256_hex(index) == expected


def test_sgr_colour_hex_accepts_none_indexes_and_truecolor_tuples():
    assert _sgr_colour_hex(None) is None
    assert _sgr_colour_hex(2) == "#00cd00"
    assert _sgr_colour_hex((1, 2, 255)) == "#0102ff"


@pytest.mark.parametrize(
    ("params", "key", "value"),
    [
        ([1], "bold", True),
        ([3], "italic", True),
        ([4], "underline", True),
        ([5], "blink", True),
        ([6], "blink", True),
        ([7], "reverse", True),
        ([8], "conceal", True),
        ([9], "strike", True),
        ([31], "fg", 1),
        ([97], "fg", 15),
        ([42], "bg", 2),
        ([107], "bg", 15),
        ([38, 5, 200], "fg", 200),
        ([48, 5, 17], "bg", 17),
        ([38, 2, 10, 20, 30], "fg", (10, 20, 30)),
        ([48, 2, 40, 50, 60], "bg", (40, 50, 60)),
    ],
)
def test_sgr_apply_sets_attributes_and_colors(params, key, value):
    state = _sgr_new_state()

    _sgr_apply(state, params)

    assert state[key] == value


@pytest.mark.parametrize(
    ("setter", "clearer", "key"),
    [
        (1, 22, "bold"),
        (3, 23, "italic"),
        (4, 24, "underline"),
        (5, 25, "blink"),
        (7, 27, "reverse"),
        (8, 28, "conceal"),
        (9, 29, "strike"),
        (31, 39, "fg"),
        (41, 49, "bg"),
    ],
)
def test_sgr_apply_clears_each_attribute_individually(setter, clearer, key):
    state = _sgr_new_state()
    _sgr_apply(state, [setter])
    assert state[key]

    _sgr_apply(state, [clearer])

    assert state[key] in (False, None)


def test_sgr_apply_zero_or_empty_resets_everything():
    state = _sgr_new_state()
    _sgr_apply(state, [1, 3, 4, 7, 31, 42])

    _sgr_apply(state, [])

    assert state == _sgr_new_state()


def test_sgr_apply_ignores_truncated_extended_colors():
    state = _sgr_new_state()

    _sgr_apply(state, [38, 5])
    _sgr_apply(state, [48, 2, 1, 2])

    assert state["fg"] is None
    assert state["bg"] is None


@pytest.mark.parametrize(
    ("character", "width"),
    [("a", 1), ("é", 1), ("́", 0), ("‍", 0), ("日", 2), ("Ａ", 2)],
)
def test_term_char_width(character, width):
    assert _term_char_width(character) == width


def test_sgr_resolve_applies_bold_brightening_reverse_and_conceal():
    state = _sgr_new_state()
    _sgr_apply(state, [1, 31])
    assert _term_sgr_resolve(state, "@fg", "@bg") == ("#ff0000", "@bg")

    state = _sgr_new_state()
    _sgr_apply(state, [7])
    assert _term_sgr_resolve(state, "@fg", "@bg") == ("@bg", "@fg")

    state = _sgr_new_state()
    _sgr_apply(state, [7, 31, 42])
    assert _term_sgr_resolve(state, "@fg", "@bg") == ("#00cd00", "#cd0000")

    state = _sgr_new_state()
    _sgr_apply(state, [8, 44])
    fg, bg = _term_sgr_resolve(state, "@fg", "@bg")
    assert fg == bg == "#0000ee"


def test_cell_and_erase_styles_keep_only_the_background_for_erasing():
    state = _sgr_new_state()
    _sgr_apply(state, [1, 3, 4, 9, 5, 32, 45])

    style = _term_cell_style(state)

    assert style == ("#00ff00", "#cd00cd", True, True, True, True, True)
    assert _term_erase_style(style) == (
        "@fg",
        "#cd00cd",
        False,
        False,
        False,
        False,
        False,
    )
    assert _term_erase_style(_term_cell_style(_sgr_new_state())) == (
        _term_cell_style(_sgr_new_state())
    )


def test_terminal_row_starts_blank_and_unwrapped():
    row = _TerminalRow(3)

    assert row.chars == [" ", " ", " "]
    assert len(row.styles) == 3
    assert row.wrapped is False


# ---------------------------------------------------------------------------
# Printing, control characters and wrapping
# ---------------------------------------------------------------------------


def test_plain_text_is_written_at_the_cursor(term):
    term._process("hello")

    assert screen(term)[0] == "hello"
    assert cursor(term) == (0, 5)


def test_carriage_return_and_newline_move_the_cursor(term):
    term._process("ab\r\ncd\rX")

    assert screen(term)[:2] == ["ab", "Xd"]


def test_backspace_moves_left_without_erasing(term):
    term._process("abc\x08\x08X")

    assert screen(term)[0] == "aXc"


def test_tab_moves_to_next_default_stop(term):
    term._process("a\tb")

    assert term._screen_row(0).chars[8] == "b"


def test_tab_past_last_stop_stays_in_last_column(term):
    term._process("\t\t\t\tx")

    assert term._screen_row(0).chars[term._cols - 1] == "x"


def test_text_wraps_and_marks_the_row_as_wrapped(small):
    small._process("abcdefg")

    assert screen(small) == ["abcde", "fg", ""]
    assert small._screen_row(0).wrapped is True
    assert small._screen_row(1).wrapped is False


def test_newline_clears_the_wrapped_flag(small):
    small._process("abcdefg\x1b[1;1H\n")

    assert small._screen_row(0).wrapped is False


def test_autowrap_off_overwrites_the_last_column(small):
    small._process("\x1b[?7labcdefg")

    assert screen(small)[0] == "abcdg"
    small._process("\x1b[?7h")
    assert small._autowrap is True


def test_scrolling_pushes_lines_into_scrollback(small):
    small._process("1\r\n2\r\n3\r\n4")

    assert screen(small) == ["2", "3", "4"]
    assert len(small._rows) == 4
    assert small._rows[0].chars[0] == "1"


def test_form_feed_and_vertical_tab_act_as_newline(small):
    small._process("a\x0bb\x0cc")

    assert screen(small) == ["a", " b", "  c"]


def test_other_control_characters_are_ignored(term):
    term._process("a\x00\x01\x07b\x7f")

    assert screen(term)[0] == "ab"


def test_wide_characters_take_two_cells(term):
    term._process("日本")

    assert term._screen_row(0).chars[:4] == ["日", "", "本", ""]
    assert cursor(term) == (0, 4)


def test_overwriting_half_of_a_wide_character_blanks_the_other_half(term):
    term._process("日\x1b[1;2Hx")

    assert term._screen_row(0).chars[:2] == [" ", "x"]


def test_combining_marks_attach_to_the_previous_cell(term):
    term._process("éx")

    assert term._screen_row(0).chars[:2] == ["é", "x"]
    assert cursor(term) == (0, 2)


def test_combining_mark_at_line_start_is_dropped(term):
    term._process("́a")

    assert screen(term)[0] == "a"


def test_wide_character_that_does_not_fit_wraps(small):
    small._process("abcd日")

    assert screen(small) == ["abcd", "日", ""]
    assert small._screen_row(0).wrapped is True


def test_wide_character_without_autowrap_is_placed_in_the_last_two_columns(small):
    small._process("\x1b[?7labcd日")

    assert small._screen_row(0).chars == ["a", "b", "c", "日", ""]


def test_non_ascii_run_overwrites_wide_character_halves(term):
    term._process("日日\x1b[1;2Hé")

    assert term._screen_row(0).chars[:4] == [" ", "é", "日", ""]


# ---------------------------------------------------------------------------
# Cursor movement and addressing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sequence", "expected"),
    [
        ("\x1b[3;4H", (2, 3)),
        ("\x1b[3;4f", (2, 3)),
        ("\x1b[H", (0, 0)),
        ("\x1b[99;99H", (4, 19)),
        ("\x1b[3;4H\x1b[2A", (0, 3)),
        ("\x1b[3;4H\x1b[A", (1, 3)),
        ("\x1b[2;4H\x1b[2B", (3, 3)),
        ("\x1b[9B", (4, 0)),
        ("\x1b[3C", (0, 3)),
        ("\x1b[99C", (0, 19)),
        ("\x1b[1;6H\x1b[2D", (0, 3)),
        ("\x1b[1;2H\x1b[9D", (0, 0)),
        ("\x1b[2;4H\x1b[2E", (3, 0)),
        ("\x1b[4;4H\x1b[2F", (1, 0)),
        ("\x1b[7G", (0, 6)),
        ("\x1b[99G", (0, 19)),
        ("\x1b[4d", (3, 0)),
    ],
)
def test_cursor_addressing_sequences(term, sequence, expected):
    term._process(sequence)

    assert cursor(term) == expected


def test_cursor_up_stops_at_the_top_of_the_scroll_region(term):
    term._process("\x1b[2;4r\x1b[3;1H\x1b[9A")

    assert cursor(term) == (1, 0)


def test_cursor_down_stops_at_the_bottom_of_the_scroll_region(term):
    term._process("\x1b[2;4r\x1b[3;1H\x1b[9B")

    assert cursor(term) == (3, 0)


def test_cursor_up_from_below_the_scroll_region_stops_at_its_top(term):
    term._process("\x1b[2;3r\x1b[5;1H\x1b[9A")

    assert cursor(term) == (1, 0)


def test_cursor_above_the_scroll_region_moves_freely(term):
    term._process("\x1b[3;4r\x1b[2;1H\x1b[9A")
    assert cursor(term) == (0, 0)

    term._process("\x1b[2;1H\x1b[9B")
    assert cursor(term) == (3, 0)


def test_origin_mode_addresses_rows_relative_to_the_scroll_region(term):
    term._process("\x1b[2;4r")
    assert cursor(term) == (0, 0)

    term._process("\x1b[?6h")
    assert cursor(term) == (1, 0)
    term._process("\x1b[1;1H")
    assert cursor(term) == (1, 0)
    term._process("\x1b[9;1H")
    assert cursor(term) == (3, 0)

    term._process("\x1b[?6l")
    assert cursor(term) == (0, 0)


def test_save_and_restore_cursor_with_escape_and_csi(term):
    term._process("\x1b[2;3H\x1b7\x1b[1;1H\x1b8")
    assert cursor(term) == (1, 2)

    term._process("\x1b[4;5H\x1b[s\x1b[1;1H\x1b[u")
    assert cursor(term) == (3, 4)


def test_restore_cursor_also_restores_the_text_style(term):
    term._process("\x1b[31m\x1b7\x1b[0m\x1b8")

    assert term._sgr_state["fg"] == 1


def test_restore_cursor_without_a_save_is_a_no_op(term):
    term._process("\x1b[2;3H\x1b8\x1b[u")

    assert cursor(term) == (1, 2)


def test_restore_cursor_ignores_a_save_made_on_the_other_screen(term):
    term._process("\x1b[2;3H\x1b7\x1b[?1049h\x1b[1;1H\x1b8")

    assert cursor(term) == (0, 0)


def test_index_reverse_index_and_next_line(small):
    small._process("a\r\nb\r\nc")

    small._process("\x1bD")
    assert screen(small) == ["b", "c", ""]

    small._process("\x1b[1;1H\x1bM")
    assert screen(small) == ["", "b", "c"]

    small._process("\x1b[2;4H\x1bE")
    assert cursor(small) == (2, 0)


def test_reverse_index_moves_up_when_not_at_the_region_top(small):
    small._process("\x1b[3;3H\x1bM")

    assert cursor(small) == (1, 2)


# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------


def test_set_clear_and_reset_tab_stops(term):
    term._process("\x1b[1;4H\x1bH\r\t")
    assert cursor(term) == (0, 3)

    term._process("\x1b[g\r\t")
    assert cursor(term) == (0, 8)

    term._process("\x1b[3g\r\t")
    assert cursor(term) == (0, 19)


def test_tab_stops_are_reset_by_a_full_reset(term):
    term._process("\x1b[3g\x1bc\r\t")

    assert cursor(term) == (0, 8)


# ---------------------------------------------------------------------------
# Erasing, inserting and deleting
# ---------------------------------------------------------------------------


def test_erase_in_line_modes(term):
    term._process("abcdef\x1b[1;4H\x1b[K")
    assert screen(term)[0] == "abc"

    term._process("\x1b[1;1Habcdef\x1b[1;4H\x1b[1K")
    assert screen(term)[0] == "    ef"

    term._process("\x1b[2K")
    assert screen(term)[0] == ""


def test_erase_in_display_below_and_above(term):
    term._process("aa\r\nbb\r\ncc\r\ndd\r\nee\x1b[3;2H")

    term._process("\x1b[J")
    assert screen(term) == ["aa", "bb", "c", "", ""]

    term._process("\x1b[1J")
    assert screen(term) == ["", "", "", "", ""]


def test_erase_in_display_one_clears_up_to_the_cursor(term):
    term._process("aa\r\nbb\r\ncc\x1b[2;2H\x1b[1J")

    assert screen(term)[:3] == ["", "", "cc"]


def test_erase_in_display_two_moves_the_screen_into_scrollback(small):
    small._process("a\r\nb\x1b[2J")

    assert screen(small) == ["", "", ""]
    assert len(small._rows) == 5
    assert small._rows[0].chars[0] == "a"


def test_erase_in_display_three_drops_the_scrollback(small):
    small._process("1\r\n2\r\n3\r\n4")
    assert len(small._rows) == 4

    small._process("\x1b[3J")

    assert len(small._rows) == 3
    assert screen(small) == ["2", "3", "4"]


def test_erase_in_display_three_is_ignored_on_the_alternate_screen(small):
    small._process("\x1b[?1049h")
    before = len(small._rows)

    small._process("x\x1b[3J")

    assert len(small._rows) == before
    assert screen(small)[0] == "x"


def test_erased_cells_take_the_current_background(term):
    term._process("\x1b[42m\x1b[2K")

    assert term._screen_row(0).styles[0][1] == "#00cd00"
    assert term._screen_row(0).styles[19][1] == "#00cd00"


def test_insert_and_delete_characters(term):
    term._process("abcdef\x1b[1;3H\x1b[2@")
    assert screen(term)[0] == "ab  cdef"

    term._process("\x1b[2P")
    assert screen(term)[0] == "abcdef"


def test_insert_characters_drops_what_falls_off_the_right_edge(small):
    small._process("abcde\x1b[1;2H\x1b[2@")

    assert screen(small)[0] == "a  bc"


def test_delete_characters_that_split_a_wide_character_blank_the_orphan(term):
    term._process("日x\x1b[1;1H\x1b[P")

    assert term._screen_row(0).chars[0] == " "


def test_insert_characters_that_split_a_wide_character_blank_the_orphan(term):
    term._process("日x\x1b[1;2H\x1b[@")

    assert term._screen_row(0).chars[0] == " "


def test_erase_characters(term):
    term._process("abcdef\x1b[1;2H\x1b[3X")

    assert screen(term)[0] == "a   ef"


def test_insert_and_delete_lines(small):
    small._process("a\r\nb\r\nc\x1b[2;1H")

    small._process("\x1b[L")
    assert screen(small) == ["a", "", "b"]

    small._process("\x1b[M")
    assert screen(small) == ["a", "b", ""]


def test_insert_and_delete_lines_outside_the_region_do_nothing(term):
    term._process("a\r\nb\r\nc\r\nd\r\ne\x1b[2;3r\x1b[5;1H\x1b[L\x1b[M")

    assert screen(term) == ["a", "b", "c", "d", "e"]


def test_scroll_up_and_down_commands(small):
    small._process("a\r\nb\r\nc")

    small._process("\x1b[S")
    assert screen(small) == ["b", "c", ""]

    small._process("\x1b[T")
    assert screen(small) == ["", "b", "c"]


def test_scroll_region_scrolls_without_creating_scrollback(term):
    term._process("a\r\nb\r\nc\r\nd\r\ne\x1b[2;4r\x1b[4;1H\n")

    assert screen(term) == ["a", "c", "d", "", "e"]
    assert len(term._rows) == 5


def test_scroll_region_defaults_and_clamps(term):
    term._process("\x1b[r")
    assert (term._scroll_top, term._scroll_bot) == (0, 4)

    term._process("\x1b[3;99r")
    assert (term._scroll_top, term._scroll_bot) == (2, 4)

    term._process("\x1b[4;2r")
    assert (term._scroll_top, term._scroll_bot) == (3, 3)


def test_repeat_previous_character(term):
    term._process("x\x1b[3b")
    assert screen(term)[0] == "xxxx"

    fresh = make_terminal()
    fresh._process("\x1b[3b")
    assert screen(fresh)[0] == ""
    fresh.stop()


def test_screen_alignment_pattern_fills_the_screen(term):
    term._process("hello\x1b#8")

    assert screen(term) == ["E" * 20] * 5
    assert cursor(term) == (0, 0)


def test_designating_a_character_set_is_swallowed(term):
    term._process("\x1b(Bxy\x1b)0z")

    assert screen(term)[0] == "xyz"


def test_full_reset_clears_the_screen_and_modes(term):
    term._process("junk\x1b[?7l\x1b[?1h\x1b[31m\x1bc")

    assert screen(term) == [""] * 5
    assert term._autowrap is True
    assert term._app_cursor is False
    assert term._sgr_state == _sgr_new_state()
    assert cursor(term) == (0, 0)


def test_unknown_escape_sequences_are_skipped(term):
    term._process("\x1bZab\x1b\x1b[1;2Hc")

    assert screen(term)[0] == "ac"


# ---------------------------------------------------------------------------
# Split and malformed sequences
# ---------------------------------------------------------------------------


def test_escape_sequence_split_between_chunks_is_completed(term):
    term._process("\x1b[3")
    assert term._pending_esc == "\x1b[3"

    term._process(";4H")

    assert cursor(term) == (2, 3)
    assert term._pending_esc == ""


def test_lone_escape_at_the_end_waits_for_more_output(term):
    term._process("a\x1b")
    assert term._pending_esc == "\x1b"

    term._process("[2;2H")

    assert cursor(term) == (1, 1)


def test_character_set_designation_split_between_chunks(term):
    term._process("\x1b(")
    assert term._pending_esc == "\x1b("

    term._process("Bz")

    assert screen(term)[0] == "z"


def test_control_character_inside_a_csi_sequence_is_executed_first(term):
    term._process("\x1b[2\nC")

    assert cursor(term) == (1, 2)


def test_cancel_inside_a_csi_sequence_aborts_it(term):
    term._process("\x1b[1\x18ab")
    assert screen(term)[0] == "ab"

    term._process("\x1b[1\x1aXY")
    assert screen(term)[0] == "abXY"


def test_escape_inside_a_csi_sequence_starts_a_new_one(term):
    term._process("\x1b[1\x1b[2;3H")

    assert cursor(term) == (1, 2)


def test_unrecognizable_csi_sequence_is_dropped(term):
    term._process("\x1b[1ÿz")

    assert screen(term)[0] == "1ÿz"


def test_csi_with_embedded_control_but_no_final_byte_waits(term):
    term._process("\x1b[1\n")

    assert term._pending_esc == "\x1b[1\n"


def test_csi_with_embedded_control_that_never_ends_is_dropped(monkeypatch, term):
    monkeypatch.setattr(pyqtterm_module, "_PTY_MAX_PENDING_ESC", 3)

    term._process("\x1b[1\nab")

    assert term._pending_esc == ""


def test_csi_without_embedded_controls_that_cannot_parse_is_dropped(term):
    term._process("\x1b[ÿa")

    assert screen(term)[0] == "ÿa"


# ---------------------------------------------------------------------------
# SGR through the parser
# ---------------------------------------------------------------------------


def test_sgr_sequence_styles_following_text(term):
    term._process("\x1b[31;1mX\x1b[0mY")

    styled = term._screen_row(0).styles[0]
    plain = term._screen_row(0).styles[1]
    assert styled[0] == "#ff0000"
    assert styled[2] is True
    assert plain == ("@fg", "@bg", False, False, False, False, False)


def test_truecolor_and_256_color_sgr(term):
    term._process("\x1b[38;2;1;2;3;48;5;21mX")

    style = term._screen_row(0).styles[0]
    assert style[0] == "#010203"
    assert style[1] == "#0000ff"


def test_reverse_video_swaps_the_cell_colors(term):
    term._process("\x1b[7mX")

    assert term._screen_row(0).styles[0][:2] == ("@bg", "@fg")


def test_style_flags_end_up_in_the_cell_style(term):
    term._process("\x1b[3;4;9mX")

    style = term._screen_row(0).styles[0]
    assert style[3:6] == (True, True, True)


def test_blinking_text_starts_the_blink_timer(term):
    term._process("\x1b[5mX")

    assert term._blink_timer.isActive()


def test_nocolor_terminal_ignores_sgr(qapp):
    terminal = make_terminal(nocolor=True)
    try:
        terminal._process("\x1b[31;1mX")

        assert terminal._screen_row(0).styles[0] == ("@fg", "@bg", False, False, False, False, False)
    finally:
        terminal.stop()


def test_nocolor_terminal_keeps_its_style_across_the_alternate_screen(qapp):
    terminal = make_terminal(nocolor=True)
    try:
        terminal._process("\x1b[?1049hX\x1b[?1049l")

        assert terminal._sgr_state == _sgr_new_state()
    finally:
        terminal.stop()


# ---------------------------------------------------------------------------
# Queries the terminal answers
# ---------------------------------------------------------------------------


def test_device_attributes_replies(term):
    term._process("\x1b[c")
    term._process("\x1b[>c")

    assert term.written == [b"\x1b[?1;2c", b"\x1b[>1;10;0c"]


def test_device_status_reports(term):
    term._process("\x1b[3;5H\x1b[6n\x1b[5n")

    assert term.written == [b"\x1b[3;5R", b"\x1b[0n"]


def test_xterm_modify_other_keys_query_and_set(term):
    term._process("\x1b[>4;2m")
    assert term._modify_other_keys == 2

    term._process("\x1b[?4m\x1b[?1m")
    assert term.written == [b"\x1b[>4;2m", b"\x1b[>1;0m"]

    term._process("\x1b[>4m")
    assert term._modify_other_keys == 0

    term._process("\x1b[>1;5m")
    assert term._modify_other_keys == 0


@pytest.mark.parametrize(
    ("code", "shape", "blinking"),
    [
        (0, "block", True),
        (1, "block", True),
        (2, "block", False),
        (3, "underline", True),
        (4, "underline", False),
        (5, "bar", True),
        (6, "bar", False),
    ],
)
def test_cursor_style_sequences(term, code, shape, blinking):
    term._process(f"\x1b[{code} q")

    assert term._cursor_shape == shape
    assert term._cursor_blink_enabled is blinking


def test_cursor_style_with_an_unknown_code_is_ignored(term):
    term._process("\x1b[5 q\x1b[9 q")

    assert term._cursor_shape == "bar"


# ---------------------------------------------------------------------------
# OSC
# ---------------------------------------------------------------------------


def osc52(text):
    return "\x1b]52;c;" + base64.b64encode(text.encode()).decode() + "\x07"


def test_osc_52_sets_the_clipboard(term):
    term._process(osc52("copied text"))

    assert QApplication.clipboard().text() == "copied text"


def test_osc_52_query_and_bad_data_leave_the_clipboard_alone(term):
    QApplication.clipboard().setText("keep")

    term._process("\x1b]52;c;?\x07")
    term._process("\x1b]52;c;\x07")
    term._process("\x1b]52;c;a\x07")
    term._process("\x1b]52;c\x07")

    assert QApplication.clipboard().text() == "keep"


@pytest.mark.parametrize("which", ["10", "11"])
def test_osc_color_queries_reply_with_the_default_colors(term, which):
    term._process(f"\x1b]{which};?\x07")

    (reply,) = term.written
    assert reply.startswith(f"\x1b]{which};rgb:".encode())
    assert reply.endswith(b"\x1b\\")


def test_osc_12_sets_queries_and_resets_the_cursor_color(term):
    term._process("\x1b]12;#ff0000\x07")
    assert term._cursor_color.name() == "#ff0000"
    assert term._cursor_color_custom is True

    term._process("\x1b]12;?\x07")
    assert term.written[-1].startswith(b"\x1b]12;rgb:ffff/0000/0000")

    term._process("\x1b]12;rgb:00/ff/00\x07")
    assert term._cursor_color.name() == "#00ff00"

    term._process("\x1b]112\x07")
    assert term._cursor_color_custom is False
    assert term._cursor_color == term._default_fg


def test_osc_12_ignores_colors_it_cannot_parse(term):
    term._process("\x1b]12;#00ff00\x07")

    term._process("\x1b]12;rgb:zz/00/00\x07")
    term._process("\x1b]12;rgb:00/00\x07")
    term._process("\x1b]12;not-a-color\x07")

    assert term._cursor_color.name() == "#00ff00"


def test_osc_112_with_arguments_resets_the_cursor_color(term):
    term._process("\x1b]12;#ff0000\x07\x1b]112;\x07")

    assert term._cursor_color_custom is False


def test_nocolor_terminal_ignores_cursor_color_requests(qapp):
    terminal = make_terminal(nocolor=True)
    try:
        before = terminal._cursor_color.name()

        terminal._process("\x1b]12;#ff0000\x07")

        assert terminal._cursor_color.name() == before
    finally:
        terminal.stop()


def test_osc_with_either_terminator_is_swallowed(term):
    term._process("\x1b]0;title\x07a\x1b]2;other\x1b\\b")

    assert screen(term)[0] == "ab"


def test_osc_split_between_chunks_is_completed(term):
    term._process("\x1b]0;ti")
    term._process("tle\x07ok")

    assert screen(term)[0] == "ok"


def test_oversized_osc_is_skipped_until_its_terminator(monkeypatch, term):
    monkeypatch.setattr(pyqtterm_module, "_PTY_MAX_PENDING_ESC", 10)

    term._process("\x1b]0;" + "x" * 30)
    assert term._osc_skipping is True

    term._process("more\x07after")

    assert term._osc_skipping is False
    assert screen(term)[0] == "after"


def test_oversized_osc_waits_for_a_terminator_split_over_chunks(monkeypatch, term):
    monkeypatch.setattr(pyqtterm_module, "_PTY_MAX_PENDING_ESC", 10)
    term._process("\x1b]0;" + "x" * 30)

    term._process("still going\x1b")
    assert term._pending_esc == "\x1b"

    term._process("\\done")

    assert screen(term)[0] == "done"


def test_oversized_osc_keeps_skipping_when_chunks_have_no_terminator(monkeypatch, term):
    monkeypatch.setattr(pyqtterm_module, "_PTY_MAX_PENDING_ESC", 10)
    term._process("\x1b]0;" + "x" * 30)

    term._process("no end here")

    assert term._osc_skipping is True
    assert term._pending_esc == ""


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def test_alternate_screen_saves_and_restores_the_main_screen(small):
    small._process("main\x1b[2;3r\x1b[?1049h")

    assert small._alt_mode is True
    assert screen(small) == ["", "", ""]
    assert (small._scroll_top, small._scroll_bot) == (0, 2)

    small._process("ALT")
    assert screen(small)[0] == "ALT"

    small._process("\x1b[?1049l")
    assert small._alt_mode is False
    assert screen(small)[0] == "main"
    assert (small._scroll_top, small._scroll_bot) == (1, 2)


@pytest.mark.parametrize("code", [47, 1047, 1049])
def test_every_alternate_screen_mode_number_works(small, code):
    small._process(f"\x1b[?{code}hX")
    assert small._alt_mode is True

    small._process(f"\x1b[?{code}l")
    assert small._alt_mode is False


def test_entering_the_alternate_screen_twice_and_leaving_without_entering(small):
    small._process("\x1b[?1049l")
    assert small._alt_mode is False

    small._process("a\x1b[?1049hb\x1b[?1049h")
    assert screen(small)[0] == "b"

    small._process("\x1b[?1049l")
    assert screen(small)[0] == "a"


def test_alternate_screen_scrolling_never_creates_scrollback(small):
    small._process("\x1b[?1049h1\r\n2\r\n3\r\n4")

    assert len(small._rows) == 3
    assert screen(small) == ["2", "3", "4"]


def test_alternate_screen_restores_the_text_style(small):
    small._process("\x1b[31m\x1b[?1049h")
    assert small._sgr_state["fg"] is None

    small._process("\x1b[?1049l")
    assert small._sgr_state["fg"] == 1


def test_column_mode_switch_clears_the_screen_and_homes_the_cursor(small):
    small._process("abc\x1b[2;2H\x1b[?3h")

    assert screen(small) == ["", "", ""]
    assert cursor(small) == (0, 0)


def test_simple_private_modes_toggle_their_flags(term):
    flags = {
        2004: "_bracketed_paste",
        1004: "_focus_reporting",
        7: "_autowrap",
        1: "_app_cursor",
        1007: "_alternate_scroll",
        1006: "_mouse_sgr",
    }
    for code, attribute in flags.items():
        term._process(f"\x1b[?{code}h")
        on = getattr(term, attribute)
        term._process(f"\x1b[?{code}l")
        assert getattr(term, attribute) is not on


def test_several_private_modes_in_one_sequence(term):
    term._process("\x1b[?2004;1004h")

    assert term._bracketed_paste is True
    assert term._focus_reporting is True


@pytest.mark.parametrize("code", [1000, 1002, 1003])
def test_mouse_reporting_modes(term, code):
    term._process(f"\x1b[?{code}h")
    assert term._mouse_mode == code

    term._process(f"\x1b[?{code}l")
    assert term._mouse_mode == 0


def test_cursor_visibility_and_blink_modes(term):
    term._process("\x1b[?25l")
    assert term._cursor_dectcem_visible is False
    term._process("\x1b[?25h")
    assert term._cursor_dectcem_visible is True

    term._process("\x1b[?12l")
    assert term._cursor_blink_enabled is False
    term._process("\x1b[?12h")
    assert term._cursor_blink_enabled is True


def test_reverse_screen_mode_swaps_the_default_paint_colors(term):
    foreground, background = term._paint_fg, term._paint_bg

    term._process("\x1b[?5h")
    assert (term._paint_fg, term._paint_bg) == (background, foreground)

    term._process("\x1b[?5h")
    assert (term._paint_fg, term._paint_bg) == (background, foreground)

    term._process("\x1b[?5l")
    assert (term._paint_fg, term._paint_bg) == (foreground, background)


def test_unknown_private_modes_and_sequences_are_ignored(term):
    term._process("a\x1b[?9999h\x1b[?9999l\x1b[99zb\x1b[ !pc")

    assert screen(term)[0] == "abc"
