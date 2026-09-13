"""Signed J/D/T/V example using the installed SDK and a local Core 0.6 API."""

from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
from uuid import uuid4
from jep import JEPClient

FORMAT = "jep-e2e-core-0.6"


def client():
    return JEPClient(
        base_url=os.environ.get("JEP_API_URL", "http://127.0.0.1:8000"),
        api_key=os.environ.get("JEP_API_KEY", ""),
    )


def verified_hash(api, event):
    result = api.verify_event({"event": event, "mode": "archival"})
    if (
        not result.valid
        or result.profile != "jep-core-0.6"
        or result.level < 1
        or not result.event_hash
    ):
        raise ValueError(f"Core verification failed: {result.errors}")
    return result.event_hash


def build_archive():
    api = client()
    records = []
    previous = None
    steps = [
        ("J", {"claim": "request invoice evidence", "subject": "INV-042"}),
        (
            "D",
            {
                "claim": "delegate",
                "delegatee": "did:example:invoice-tool",
                "scope": ["read"],
            },
        ),
        ("T", {"claim": "terminate", "termination_scope": "delegation"}),
        ("V", {"verification_scope": ["syntax", "cryptographic"]}),
    ]
    for sequence, (verb, what) in enumerate(steps, 1):
        if verb == "T":
            what["target"] = previous
        # Every predecessor is actually verified before the next statement is signed.
        if records:
            verified_hash(api, records[-1]["event"])
        response = api.create_event(
            {
                "verb": verb,
                "who": "did:example:e2e-agent",
                "what": what,
                "aud": "jep-e2e-demo",
                "ref": previous,
            }
        )
        event = response.event.to_dict()
        digest = verified_hash(api, event)
        if digest != response.event_hash:
            raise ValueError("Creation and verification hashes differ")
        records.append(
            {
                "format": FORMAT,
                "sequence": sequence,
                "event": event,
                "event_hash": digest,
                "previous_event_hash": previous,
            }
        )
        previous = digest
    return records


def write_archive(records, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate archive member: {key}")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError(f"Non-finite archive value: {value}")


def read_archive(path):
    with Path(path).open(encoding="utf-8") as handle:
        return [
            json.loads(
                line, object_pairs_hook=strict_object, parse_constant=reject_constant
            )
            for line in handle
        ]


def verify_archive(records):
    if len(records) != 4:
        raise ValueError("This demo requires exactly four J/D/T/V records")
    api = client()
    previous = None
    for sequence, (record, verb) in enumerate(zip(records, "JDTV"), 1):
        if not isinstance(record, dict) or record.get("format") != FORMAT:
            raise ValueError(
                "Unsupported archive; historical mocks require --legacy-mock"
            )
        if type(record.get("sequence")) is not int or record["sequence"] != sequence:
            raise ValueError("Archive sequence mismatch")
        event = record.get("event")
        if not isinstance(event, dict) or event.get("verb") != verb:
            raise ValueError("Demo verb order mismatch")
        if (
            event.get("ref") != previous
            or record.get("previous_event_hash") != previous
        ):
            raise ValueError("Archive reference mismatch")
        digest = verified_hash(api, event)
        if record.get("event_hash") != digest:
            raise ValueError("Archive event hash mismatch")
        if verb == "T" and event.get("what", {}).get("target") != previous:
            raise ValueError("Termination target mismatch")
        previous = digest
    return {
        "ok": True,
        "events": 4,
        "profile": "jep-core-0.6",
        "level": 1,
        "checks": ["syntax", "cryptographic", "local-demo-order"],
        "last_event_hash": previous,
    }


def run_demo(archive_path=None):
    path = (
        Path(archive_path)
        if archive_path
        else Path("archives") / f"demo-{uuid4()}.jsonl"
    )
    records = build_archive()
    write_archive(records, path)
    report = verify_archive(read_archive(path))
    print(f"Signed J/D/T/V archive: {path}")
    print(json.dumps(report, indent=2))
    print(
        "Level 1 plus local demo order checks; no identity, authority, HJS/JAC or log completeness claim."
    )
    return True


def cli(argv=None):
    parser = argparse.ArgumentParser(prog="jep-e2e", description=__doc__)
    parser.add_argument(
        "--legacy-mock",
        action="store_true",
        help="explicitly replay historical mock data",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="create and verify real signed J/D/T/V events")
    demo.add_argument("--archive", type=Path)
    replay = sub.add_parser("replay", help="verify an existing archive")
    replay.add_argument("archive", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.legacy_mock:
            import legacy_demo

            if args.command == "demo":
                parser.error(
                    "Historical mock mode is replay-only; use the checked-in legacy/archive.jsonl"
                )
            return (
                0
                if legacy_demo.print_replay_report(
                    args.archive, legacy_demo.read_archive(args.archive)
                )
                else 1
            )
        if args.command == "demo":
            run_demo(args.archive)
        else:
            print(json.dumps(verify_archive(read_archive(args.archive)), indent=2))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Verification failed: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(cli())
