"""A confirmed raw caveat that cannot apply to its evidence hands the case back for another choice.

A person confirmed `retain_isolated_raw_move_with_caveat` on a market-wide adjusted-close mismatch
(85 listings, `data.adjusted_close_mismatch`). The executor refuses a raw caveat for anything but
an isolated, verified raw move, and it raised: the case kept the receipt with no effect, every
rerun of the data update refused it again, and a person's next choice (a full-history retry) was
refused as `feature_input.resolution_conflict:receipt`. The refusal is now the decision's
effect, as a blocked quarantine's is, and the next choice archives it.
"""

from __future__ import annotations

from dataclasses import replace

from pydantic import TypeAdapter

from alphalattice.foundation.feature_engine.inputs.gateway import (
    FeatureInputExecutionStatus,
    FeatureInputGateway,
    FeatureInputGovernanceService,
    FeatureInputRemediationExecutor,
)
from alphalattice.foundation.feature_engine.storage.repositories import PanelStateRepository
from alphalattice.foundation.market_data_ops.storage.duckdb import MarketDataRepository
from tests.feature_input_gateway.gateway_support import (
    NOW,
    _evidence,
    _manifest,
    _panel_impact,
    _sectors,
    _temporal,
    mark_building,
)


def test_a_refused_raw_caveat_is_recorded_and_the_next_choice_archives_it(tmp_path) -> None:
    from alphalattice.control.product_host.composition.application_session import (
        WorkspaceApplicationSession,
    )
    from alphalattice.control.product_host.data_preparation.remediation import (
        WorkspaceDataIssueApplication,
    )

    manifest = replace(
        _manifest(40),
        profile=replace(_manifest(40).profile, market_profile_id="us-current-index-research"),
    )
    evidence = _evidence(
        manifest, failed={0}, failure_code="data.unexplained_raw_move", extreme=True
    )
    with WorkspaceApplicationSession.acquire(tmp_path / "workspace") as session:
        market = MarketDataRepository(session.workspace)
        panel = PanelStateRepository(market.database, market_data=market)
        service = FeatureInputGovernanceService(
            market, panel, session.mutation_gate, FeatureInputGateway()
        )
        sectors = _sectors(manifest)
        (case,) = service.assess_and_record(
            candidate_manifest=manifest,
            evidence=evidence,
            sector_by_listing_id=sectors,
            temporal_boundary=_temporal(),
            panel_impact=_panel_impact(manifest, sectors),
            observed_at=NOW,
        ).agent_cases
        mark_building(market, manifest, NOW)
        application = WorkspaceDataIssueApplication(session, lambda: NOW)
        caveat = next(
            option
            for option in case.options
            if option.option_id == "retain_isolated_raw_move_with_caveat"
        )
        confirmation = application.confirm(
            case_token=case.case_token,
            evidence_hash=case.evidence_hash,
            option_id=caveat.option_id,
            option_hash=caveat.option_hash,
            caller="HUMAN",
        )
        # The evidence the caveat meets is not an isolated raw move: an adjusted-close mismatch.
        mismatch = {
            item.listing_id: replace(item, reason_codes=("ADJUSTED_CLOSE_DIAGNOSTIC_MISMATCH",))
            for item in case.evidence
        }

        effect = FeatureInputRemediationExecutor(service.gateway).execute(
            case=case,
            option=caveat,
            evidence_by_listing_id=mismatch,
            observed_at=NOW,
            proposal_hash=confirmation["receipt_hash"],
            human_confirmed=True,
        )

        assert effect.status is FeatureInputExecutionStatus.DEFERRED
        assert effect.failure_reasons == ("RAW_CAVEAT_REQUIRES_ISOLATED_VERIFIED_MOVE",)
        assert effect.retained_evidence == ()
        panel.record_feature_input_effect(
            case.case_token, TypeAdapter(type(effect)).dump_python(effect, mode="json")
        )

        retry = next(option for option in case.options if option.option_id != caveat.option_id)
        panel.record_feature_input_resolution(
            case.case_token,
            {
                **panel.feature_input_resolution(case.case_token)["receipt"],
                "retry": retry.option_id,
            },
        )
        resolution = panel.feature_input_resolution(case.case_token)
        assert [prior["effect"]["failure_reasons"] for prior in resolution["prior_decisions"]] == [
            ["RAW_CAVEAT_REQUIRES_ISOLATED_VERIFIED_MOVE"]
        ]
        assert "effect" not in resolution
