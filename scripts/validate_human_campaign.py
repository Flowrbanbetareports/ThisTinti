#!/usr/bin/env python3
"""Fail-closed structural validator for the final #32/#94 human campaign.

This checks internal consistency only. It cannot authenticate participants,
observers, assistive-technology use, independence, comprehension, or any other
human fact and therefore never creates qualification evidence by itself.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
PLACEHOLDER = re.compile(r"^<.*>$")
ALLOWED_STATUS = {"PREPARATION_ONLY", "FINAL_EVIDENCE_RECORDED"}
ALLOWED_RESULT = {"NOT_RUN", "PASS", "FAIL", "BLOCKED"}
SERIOUS = {"CRITICAL", "HIGH", "SERIOUS"}


class CampaignError(ValueError):
    pass


def _obj(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CampaignError(f"{path}: expected object")
    return value


def _text(value: Any, path: str, *, placeholder: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise CampaignError(f"{path}: expected non-empty string")
    if not placeholder and PLACEHOLDER.fullmatch(value):
        raise CampaignError(f"{path}: unresolved placeholder")
    return value


def _hash(value: Any, path: str, pattern: re.Pattern[str], *, placeholder: bool) -> None:
    text = _text(value, path, placeholder=placeholder)
    if placeholder and PLACEHOLDER.fullmatch(text):
        return
    if not pattern.fullmatch(text):
        raise CampaignError(f"{path}: invalid hash")


def validate(data: dict[str, Any], *, final: bool = False) -> str:
    if data.get("schema") != "qualified-human-campaign.v1":
        raise CampaignError("schema: unsupported")
    if data.get("qualification_claim") != "ThisTinti 1.0 Qualified — Procurement v1 — profile P1 — protocol E1":
        raise CampaignError("qualification_claim: unexpected")
    status = data.get("status")
    if status not in ALLOWED_STATUS:
        raise CampaignError("status: invalid")
    if final and status != "FINAL_EVIDENCE_RECORDED":
        raise CampaignError("status: final validation requires FINAL_EVIDENCE_RECORDED")
    if not final and status != "PREPARATION_ONLY":
        raise CampaignError("status: evidence state requires --final")

    candidate = _obj(data.get("candidate"), "candidate")
    _hash(candidate.get("source_sha"), "candidate.source_sha", SHA40, placeholder=not final)
    _hash(candidate.get("artifact_sha256"), "candidate.artifact_sha256", SHA256, placeholder=not final)
    _text(candidate.get("artifact_id"), "candidate.artifact_id", placeholder=not final)
    if candidate.get("release_version") != "1.0.0":
        raise CampaignError("candidate.release_version: expected 1.0.0")
    if candidate.get("release_tag") != "v1.0.0":
        raise CampaignError("candidate.release_tag: expected v1.0.0")

    campaign = _obj(data.get("campaign"), "campaign")
    _text(campaign.get("protocol_ref"), "campaign.protocol_ref", placeholder=not final)
    _hash(campaign.get("protocol_sha256"), "campaign.protocol_sha256", SHA256, placeholder=not final)
    sessions = campaign.get("sessions")
    if not isinstance(sessions, list):
        raise CampaignError("campaign.sessions: expected array")
    if final and not sessions:
        raise CampaignError("campaign.sessions: final evidence requires sessions")

    source_sha = candidate.get("source_sha")
    artifact_hash = candidate.get("artifact_sha256")
    seen_ids: set[str] = set()
    untrained_total = 0
    untrained_success = 0
    human_keyboard_pass = False
    human_at_pass = False
    hands_on_pass = False

    for i, raw in enumerate(sessions):
        session = _obj(raw, f"campaign.sessions[{i}]")
        sid = _text(session.get("session_id"), f"campaign.sessions[{i}].session_id")
        if sid in seen_ids:
            raise CampaignError(f"campaign.sessions[{i}].session_id: duplicate")
        seen_ids.add(sid)
        if session.get("candidate_source_sha") != source_sha:
            raise CampaignError(f"campaign.sessions[{i}].candidate_source_sha: mixed candidate")
        if session.get("artifact_sha256") != artifact_hash:
            raise CampaignError(f"campaign.sessions[{i}].artifact_sha256: mixed artifact")
        if session.get("execution_kind") != "HUMAN_OBSERVED":
            raise CampaignError(f"campaign.sessions[{i}].execution_kind: automated/simulated evidence forbidden")
        _text(session.get("participant_id"), f"campaign.sessions[{i}].participant_id")
        _text(session.get("observer_id"), f"campaign.sessions[{i}].observer_id")
        if session.get("blind_or_holdout_content_used") is not False:
            raise CampaignError(f"campaign.sessions[{i}].blind_or_holdout_content_used: must be false")
        if session.get("prior_this_tinti_experience") not in {"NONE", "LIMITED", "EXPERIENCED"}:
            raise CampaignError(f"campaign.sessions[{i}].prior_this_tinti_experience: invalid")

        mapping32 = _obj(session.get("issue_32"), f"campaign.sessions[{i}].issue_32")
        if mapping32.get("applicable"):
            if session.get("prior_this_tinti_experience") != "NONE":
                raise CampaignError(f"campaign.sessions[{i}].issue_32: trained participant cannot count")
            untrained_total += 1
            success = (
                mapping32.get("explained_product_correctly") is True
                and mapping32.get("reached_first_evidence_backed_item") is True
                and mapping32.get("blocking_assistance") is False
                and mapping32.get("within_protocol_target") is True
            )
            if success:
                untrained_success += 1

        mapping94 = _obj(session.get("issue_94"), f"campaign.sessions[{i}].issue_94")
        if mapping94.get("keyboard_only_human_pass") is True:
            human_keyboard_pass = True
        if mapping94.get("assistive_technology_human_pass") is True:
            tech = mapping94.get("assistive_technology")
            if not isinstance(tech, str) or not tech.strip():
                raise CampaignError(f"campaign.sessions[{i}].issue_94.assistive_technology: required")
            human_at_pass = True
        if mapping94.get("hands_on_path_human_pass") is True:
            hands_on_pass = True

    issue32 = _obj(data.get("issue_32"), "issue_32")
    if issue32.get("required_untrained_sessions") != 10 or issue32.get("minimum_successes") != 8:
        raise CampaignError("issue_32: target must remain 8/10")
    result32 = issue32.get("result")
    if result32 not in ALLOWED_RESULT:
        raise CampaignError("issue_32.result: invalid")
    if final and result32 == "PASS" and (untrained_total < 10 or untrained_success < 8):
        raise CampaignError("issue_32.result: PASS requires >=10 untrained sessions and >=8 successes")

    issue94 = _obj(data.get("issue_94"), "issue_94")
    for field in ("keyboard_only_human_review", "assistive_technology_human_review", "hands_on_path_review", "result"):
        if issue94.get(field) not in ALLOWED_RESULT:
            raise CampaignError(f"issue_94.{field}: invalid")
    if final and issue94.get("keyboard_only_human_review") == "PASS" and not human_keyboard_pass:
        raise CampaignError("issue_94.keyboard_only_human_review: no supporting human session")
    if final and issue94.get("assistive_technology_human_review") == "PASS" and not human_at_pass:
        raise CampaignError("issue_94.assistive_technology_human_review: no supporting AT session")
    if final and issue94.get("hands_on_path_review") == "PASS" and not hands_on_pass:
        raise CampaignError("issue_94.hands_on_path_review: no supporting human session")
    if final and issue94.get("result") == "PASS" and not (human_keyboard_pass and human_at_pass and hands_on_pass):
        raise CampaignError("issue_94.result: PASS requires keyboard, AT and hands-on human evidence")

    findings = data.get("findings")
    if not isinstance(findings, list):
        raise CampaignError("findings: expected array")
    for i, raw in enumerate(findings):
        finding = _obj(raw, f"findings[{i}]")
        severity = finding.get("severity")
        status_f = finding.get("status")
        if severity in SERIOUS and status_f not in {"RETESTED_PASS", "CLOSED_RETESTED"}:
            raise CampaignError(f"findings[{i}]: serious finding not closed and retested")

    if data.get("qualification_decision") != "NOT_A_PASS":
        raise CampaignError("qualification_decision: validator cannot create qualification PASS")
    return "VALID_STRUCTURE_NOT_QUALIFICATION_PASS"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--final", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise CampaignError("root: expected object")
    print(validate(data, final=args.final))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
