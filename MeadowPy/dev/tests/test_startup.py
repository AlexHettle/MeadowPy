from meadowpy.core.startup import remaining_delay_ms


def test_remaining_delay_ms_returns_zero_when_minimum_met():
    assert remaining_delay_ms(10.0, 5.0, now=15.0) == 0


def test_remaining_delay_ms_uses_remaining_time_when_still_loading():
    assert remaining_delay_ms(10.0, 5.0, now=12.75) == 2250


def test_remaining_delay_ms_handles_clock_skew():
    assert remaining_delay_ms(10.0, 5.0, now=9.0) == 5000


def test_remaining_delay_ms_short_circuits_for_non_positive_minimum():
    assert remaining_delay_ms(10.0, 0.0, now=10.0) == 0
