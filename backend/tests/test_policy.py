from datetime import UTC, datetime, time, timedelta

from gatelock.services.access import Debouncer
from gatelock.services.policy import in_window


def test_window_same_day():
    assert in_window(time(8), time(8), time(18))
    assert in_window(time(17, 59), time(8), time(18))
    assert not in_window(time(18), time(8), time(18))
    assert not in_window(time(7, 59), time(8), time(18))


def test_window_all_day_and_overnight():
    assert in_window(time(3), time(0), time(0))
    assert in_window(time(23), time(22), time(6))
    assert in_window(time(5), time(22), time(6))
    assert not in_window(time(12), time(22), time(6))


def test_debouncer_drops_repeats_within_window():
    d = Debouncer(5)
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    assert d.accept("express", "AA", t0)
    assert not d.accept("express", "AA", t0 + timedelta(seconds=2))
    assert d.accept("north", "AA", t0 + timedelta(seconds=2))  # other gate
    assert d.accept("express", "AA", t0 + timedelta(seconds=10))
