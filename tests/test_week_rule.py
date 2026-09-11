from datetime import date, timedelta

from zelploie.models import SemaineVariante
from zelploie.week_rule import resolve_week_variant


def test_reference_week_is_a():
    assert resolve_week_variant(date(2026, 9, 7)) == SemaineVariante.A


def test_reference_week_every_day_is_a():
    for i in range(7):
        d = date(2026, 9, 7) + timedelta(days=i)
        assert resolve_week_variant(d) == SemaineVariante.A, d


def test_following_week_is_b():
    for i in range(7):
        d = date(2026, 9, 14) + timedelta(days=i)
        assert resolve_week_variant(d) == SemaineVariante.B, d


def test_alternates_over_several_weeks():
    expected = [SemaineVariante.A, SemaineVariante.B, SemaineVariante.A, SemaineVariante.B, SemaineVariante.A]
    for i, exp in enumerate(expected):
        d = date(2026, 9, 7) + timedelta(weeks=i)
        assert resolve_week_variant(d) == exp, d


def test_week_before_reference_is_b():
    # La semaine ISO 36 (31 aout - 6 sept 2026) precede la reference (semaine A).
    assert resolve_week_variant(date(2026, 8, 31)) == SemaineVariante.B
    assert resolve_week_variant(date(2026, 9, 6)) == SemaineVariante.B


def test_two_weeks_before_reference_is_a():
    assert resolve_week_variant(date(2026, 8, 24)) == SemaineVariante.A
