"""Tiny JEP end-to-end demo primitives.

This module intentionally uses only the Python standard library and mock
components so the accountability flow is easy to inspect in five minutes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

ARCHIVE_PATH = Path("archive.jsonl")
DEMO_RUN_ID = "jep-demo-run-001"
MOCK_HUMAN_PROMPT = "Summarize invoice INV-042 and decide whether to delegate validation."

Event = Dict[str, Any]
Envelope = Dict[str, Any]


def canonical_json(value: Any) -> str:
    """Return deterministic JSON for hashing and readable archives."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def utc_timestamp(step: int) -> str:
    """Use deterministic timestamps so replay output is stable."""
    return f"2026-01-01T00:00:0{step}Z"


def mock_mcp_tool(invoice_id: str) -> Dict[str, Any]:
    """A mock MCP tool: no network, no database, no external side effects."""
    return {
        "tool": "mock.mcp.invoice_validator",
        "input": {"invoice_id": invoice_id},
        "output": {
            "invoice_id": invoice_id,
            "vendor": "Example Supplies Co.",
            "amount_usd": 128.40,
            "policy_result": "approved",
            "evidence": "mock purchase-order match PO-777",
        },
    }


def mock_agent_session() -> List[Event]:
    """Create Judgment, Delegation, Termination, and Verification JEP events."""
    tool_call = mock_mcp_tool("INV-042")
    return [
        {
            "event_id": "evt-001-judgment",
            "type": "Judgment",
            "run_id": DEMO_RUN_ID,
            "timestamp": utc_timestamp(1),
            "actor": "mock-agent",
            "human_request": MOCK_HUMAN_PROMPT,
            "judgment": {
                "decision": "delegate_invoice_validation",
                "rationale": "The human request needs structured invoice evidence before a final answer.",
                "confidence": 0.82,
            },
        },
        {
            "event_id": "evt-002-delegation",
            "type": "Delegation",
            "run_id": DEMO_RUN_ID,
            "timestamp": utc_timestamp(2),
            "actor": "mock-agent",
            "delegate_to": tool_call["tool"],
            "tool_call": tool_call,
        },
        {
            "event_id": "evt-003-termination",
            "type": "Termination",
            "run_id": DEMO_RUN_ID,
            "timestamp": utc_timestamp(3),
            "actor": "mock-agent",
            "reason": "The mock tool returned enough evidence to answer the human request.",
            "final_answer": "Invoice INV-042 from Example Supplies Co. is approved for $128.40.",
        },
        {
            "event_id": "evt-004-verification",
            "type": "Verification",
            "run_id": DEMO_RUN_ID,
            "timestamp": utc_timestamp(4),
            "actor": "mock-verifier",
            "checks": {
                "receipt_hash_present": True,
                "lineage_prev_hash_valid": True,
                "required_event_types_present": True,
            },
            "verdict": "pass",
        },
    ]


def hjs_receipt(event: Event) -> Dict[str, Any]:
    """Build a compact HJS-style receipt for an event."""
    subject_hash = sha256_json(event)
    return {
        "receipt_type": "HJS-style-receipt",
        "issuer": "mock-hjs-notary",
        "issued_at": datetime(2026, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z"),
        "subject_event_id": event["event_id"],
        "subject_hash_alg": "sha256-canonical-json",
        "subject_hash": subject_hash,
        "signature": f"mock-signature:{subject_hash[:24]}",
    }


def jac_lineage(event: Event, receipt: Dict[str, Any], previous_line_hash: str) -> Dict[str, Any]:
    """Build one JAC-style lineage link over the event and its receipt."""
    link_material = {
        "event_hash": sha256_json(event),
        "receipt_hash": sha256_json(receipt),
        "previous_line_hash": previous_line_hash,
    }
    return {
        "lineage_type": "JAC-style-lineage-link",
        "event_id": event["event_id"],
        "previous_line_hash": previous_line_hash,
        "line_hash_alg": "sha256-canonical-json",
        "line_hash": sha256_json(link_material),
    }


def build_archive(events: Iterable[Event]) -> List[Envelope]:
    """Wrap JEP events with receipts and lineage links."""
    envelopes: List[Envelope] = []
    previous = "GENESIS"
    for sequence, event in enumerate(events, start=1):
        receipt = hjs_receipt(event)
        lineage = jac_lineage(event, receipt, previous)
        envelope = {
            "sequence": sequence,
            "jep_event": event,
            "hjs_receipt": receipt,
            "jac_lineage": lineage,
        }
        envelopes.append(envelope)
        previous = lineage["line_hash"]
    return envelopes


def write_archive(envelopes: Iterable[Envelope], archive_path: Path = ARCHIVE_PATH) -> None:
    with archive_path.open("w", encoding="utf-8") as handle:
        for envelope in envelopes:
            handle.write(json.dumps(envelope, sort_keys=True, ensure_ascii=False) + "\n")


def read_archive(archive_path: Path) -> List[Envelope]:
    with archive_path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def verify_archive(envelopes: List[Envelope]) -> Tuple[bool, List[str]]:
    """Replay archive lines and verify receipt hashes plus lineage continuity."""
    messages: List[str] = []
    required = {"Judgment", "Delegation", "Termination", "Verification"}
    seen = set()
    previous = "GENESIS"

    for envelope in envelopes:
        event = envelope["jep_event"]
        receipt = envelope["hjs_receipt"]
        lineage = envelope["jac_lineage"]
        seen.add(event["type"])

        event_hash = sha256_json(event)
        receipt_hash = sha256_json(receipt)
        expected_line_hash = sha256_json(
            {
                "event_hash": event_hash,
                "receipt_hash": receipt_hash,
                "previous_line_hash": previous,
            }
        )

        if receipt["subject_hash"] != event_hash:
            messages.append(f"FAIL {event['event_id']}: receipt subject hash mismatch")
        if lineage["previous_line_hash"] != previous:
            messages.append(f"FAIL {event['event_id']}: lineage previous hash mismatch")
        if lineage["line_hash"] != expected_line_hash:
            messages.append(f"FAIL {event['event_id']}: lineage line hash mismatch")

        if not messages or not messages[-1].startswith(f"FAIL {event['event_id']}"):
            messages.append(f"PASS {event['event_id']}: {event['type']} receipt and lineage verified")
        previous = lineage["line_hash"]

    missing = required - seen
    if missing:
        messages.append(f"FAIL archive: missing required event types {sorted(missing)}")
    else:
        messages.append("PASS archive: required event types present")

    return not any(message.startswith("FAIL") for message in messages), messages


def print_replay_report(archive_path: Path, envelopes: List[Envelope]) -> bool:
    ok, messages = verify_archive(envelopes)
    print("HISTORICAL MOCK: hash consistency only; no JEP-Core, HJS or JAC conformance.")
    print(f"Replay verification for {archive_path}")
    print(f"Events replayed: {len(envelopes)}")
    for message in messages:
        print(f"- {message}")
    print(f"Verdict: {'PASS' if ok else 'FAIL'}")
    return ok


def run_demo(archive_path: Path = ARCHIVE_PATH) -> bool:
    events = mock_agent_session()
    envelopes = build_archive(events)
    write_archive(envelopes, archive_path)

    print("Human → Agent → Tool → JEP Event → HJS Receipt → JAC Lineage → Archive")
    print(f"Generated {archive_path} with {len(envelopes)} JSONL records")
    print()
    return print_replay_report(archive_path, envelopes)


def cli(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jep-e2e --legacy-mock", description="Replay and verify a JEP demo archive")
    subparsers = parser.add_subparsers(dest="command", required=True)
    replay_parser = subparsers.add_parser("replay", help="replay and verify archive.jsonl")
    replay_parser.add_argument("archive", type=Path, help="path to archive.jsonl")
    args = parser.parse_args(argv)

    if args.command == "replay":
        envelopes = read_archive(args.archive)
        return 0 if print_replay_report(args.archive, envelopes) else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(cli())
