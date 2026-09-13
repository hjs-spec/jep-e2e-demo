from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import pytest
from jep_core import build_archive, write_archive, read_archive, verify_archive, cli

ROOT = Path(__file__).resolve().parents[1]


def test_real_four_verbs(tmp_path):
    records = build_archive()
    assert [r["event"]["verb"] for r in records] == list("JDTV")
    assert all(r["event"]["jep"] == "1" and r["event"]["sig"] for r in records)
    path = tmp_path / "archive.jsonl"
    write_archive(records, path)
    assert read_archive(path) == records
    assert verify_archive(records)["level"] == 1
    assert verify_archive(records)["ok"]
    with pytest.raises(FileExistsError):
        write_archive(records, path)


@pytest.mark.parametrize(
    "change",
    ["payload", "signature", "hash", "previous", "sequence", "truncate", "reorder"],
)
def test_tamper_rejected(change):
    records = deepcopy(build_archive())
    if change == "payload":
        records[0]["event"]["what"]["claim"] = "tampered"
    elif change == "signature":
        records[0]["event"]["sig"] = "invalid"
    elif change == "hash":
        records[0]["event_hash"] = "sha256:" + "0" * 64
    elif change == "previous":
        records[1]["previous_event_hash"] = None
    elif change == "sequence":
        records[0]["sequence"] = True
    elif change == "truncate":
        records.pop()
    else:
        records.reverse()
    with pytest.raises(ValueError):
        verify_archive(records)


@pytest.mark.parametrize("content", ['{"a":1,"a":2}\n', '{"value":NaN}\n'])
def test_strict_archive_json(tmp_path, content):
    path = tmp_path / "bad.jsonl"
    path.write_text(content)
    with pytest.raises(ValueError):
        read_archive(path)


def test_legacy_requires_explicit_mode():
    path = ROOT / "legacy/archive.jsonl"
    with pytest.raises(ValueError, match="historical mocks"):
        verify_archive(read_archive(path))
    assert cli(["--legacy-mock", "replay", str(path)]) == 0


def test_installed_command_flow(tmp_path):
    path = tmp_path / "cli.jsonl"
    for args in [["demo", "--archive", str(path)], ["replay", str(path)]]:
        result = subprocess.run(
            [sys.executable, "-m", "jep_core", *args],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stdout + result.stderr
