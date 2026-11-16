"""A rolling refresh re-sending a back-adjusted window asks for the full history at any precision.

A daily data update without a Goal reconciles the provider's adjusted closes at zero precision.
After a new dividend the provider re-sent every close before its ex-date scaled by one factor; the
rolling merge wrote the scaled window over the stored history it kept, a seam at the window's first
session, and 85 listings then failed the adjusted-close diagnostic on that one session
(`data.adjusted_close_mismatch`, AAPL's 2026-11-12 dividend: 0.999241 from 2026-09-14 on, 1.0
before). A positive precision already asked for the full history; zero now does too.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from alphalattice.foundation.market_data_ops.storage.action_audit import (
    ActionAuditScopeInsufficient,
    standing,
)

STORED_THROUGH = date(2026, 10, 27)
WINDOW_START = date(2026, 9, 14)
EX_DATE = date(2026, 11, 12)
FACTOR = 0.999241


def _sessions() -> list[date]:
    first = date(2026, 8, 3)
    days = (first + timedelta(days=offset) for offset in range(110))
    return [day for day in days if day.weekday() < 5 and day <= date(2026, 11, 13)]


RAW = {session: 300.0 + index * 0.5 for index, session in enumerate(_sessions())}
PRIOR = {session: close for session, close in RAW.items() if session <= STORED_THROUGH}


def _window(scale_before: date | None) -> dict[date, float]:
    return {
        session: close * FACTOR if scale_before and session < scale_before else close
        for session, close in RAW.items()
        if session >= WINDOW_START
    }


@pytest.mark.parametrize("tolerance", [0.0, 0.0005])
def test_a_rolling_back_adjusted_window_asks_for_the_full_history(tolerance: float) -> None:
    observed = _window(scale_before=EX_DATE)

    with pytest.raises(ActionAuditScopeInsufficient, match="reaches before the rolling scope"):
        standing(
            PRIOR,
            observed,
            set(observed) - set(PRIOR),
            tolerance,
            replaces=False,
            actions={EX_DATE},
        )


def test_a_rolling_window_whose_stored_closes_stand_writes_only_its_new_sessions() -> None:
    observed = _window(scale_before=None)
    added = set(observed) - set(PRIOR)

    written, series, _ = standing(PRIOR, observed, added, 0.0, replaces=False)

    assert set(written) >= added
    assert all(series[session] == RAW[session] for session in RAW)


def test_a_correction_inside_the_window_is_merged_without_a_full_refresh() -> None:
    corrected = date(2026, 10, 1)
    observed = _window(scale_before=None)
    observed[corrected] *= 1.01

    _, series, _ = standing(PRIOR, observed, set(observed) - set(PRIOR), 0.0, replaces=False)

    assert series[corrected] == observed[corrected]
    assert series[WINDOW_START - timedelta(days=3)] == PRIOR[WINDOW_START - timedelta(days=3)]


def test_a_full_refresh_replaces_the_back_adjusted_history_without_a_seam() -> None:
    observed = {
        session: close * FACTOR if session < EX_DATE else close for session, close in RAW.items()
    }

    _, series, _ = standing(PRIOR, observed, set(observed) - set(PRIOR), 0.0, replaces=True)

    ratios = {round(series[session] / RAW[session], 9) for session in RAW if session < EX_DATE}
    assert ratios == {round(FACTOR, 9)}
