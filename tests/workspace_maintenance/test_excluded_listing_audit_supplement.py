"""A full-history audit admitted onto a cycle stops being owed once the cycle excludes its listing.

A daily data update stopped on a listing's full-history audit (FISV), the workspace rule admitted
the audit onto the same cycle, and the cycle's Sector partial exclusion then dropped that listing
from its working membership. On resume the cycle refused its own supplement as "a listing outside
the candidate manifest" with a ValueError, every time, so the update could never finish. The
request's own audits are still checked against the membership; the cycle's supplement for a
listing it excluded itself is left out.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from alphalattice.control.data_platform.maintenance.contracts import (
    MaintenanceTrigger,
    WorkspaceMaintenanceRequest,
)
from alphalattice.control.data_platform.maintenance.coordinator import (
    WorkspaceMaintenanceCoordinator,
)

NOW = datetime(2026, 11, 16, 2, 30, tzinfo=UTC)


def _request(*full_history: str) -> WorkspaceMaintenanceRequest:
    return WorkspaceMaintenanceRequest.create(
        market_profile_id="us-current-index-research",
        target_market_session=date(2026, 11, 13),
        knowledge_cutoff_at=NOW,
        trigger=MaintenanceTrigger.STARTUP,
        membership_revision="b" * 64,
        data_policy_hash="d" * 64,
        feature_policy_hash="e" * 64,
        full_history_listing_ids=full_history,
    )


def _coordinator(members: tuple[str, ...], supplement: tuple[str, ...]):  # type: ignore[no-untyped-def]
    coordinator = object.__new__(WorkspaceMaintenanceCoordinator)
    coordinator.manifest = SimpleNamespace(
        listings=tuple(SimpleNamespace(listing_id=listing) for listing in members)
    )
    coordinator.registry = SimpleNamespace(audit_supplement=lambda _cycle: supplement)
    coordinator._cycle_id = "cycle-1"
    return coordinator


def test_a_supplement_for_a_listing_the_cycle_excluded_is_no_longer_owed() -> None:
    coordinator = _coordinator(("listing-a", "listing-b"), supplement=("listing-fisv",))

    assert coordinator._granted_full_audits(_request()) == ()
    assert coordinator._authorized_full_audit_listing_ids(_request()) == ()


def test_a_supplement_for_a_listing_still_held_stays_owed() -> None:
    coordinator = _coordinator(("listing-a", "listing-fisv"), supplement=("listing-fisv",))

    assert coordinator._authorized_full_audit_listing_ids(_request()) == ("listing-fisv",)


def test_a_requested_audit_outside_the_membership_is_still_refused() -> None:
    coordinator = _coordinator(("listing-a",), supplement=())

    with pytest.raises(ValueError, match="outside the candidate manifest"):
        coordinator._authorized_full_audit_listing_ids(_request("listing-foreign"))
