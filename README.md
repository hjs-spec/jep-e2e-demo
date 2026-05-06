# JEP End-to-End Demo

A five-minute, dependency-light demo of a complete JEP accountability stack:

```text
Human
→ Agent
→ Tool
→ JEP Event
→ HJS Receipt
→ JAC Lineage
→ Archive
→ Replay
→ Verification
```

The demo is intentionally **not production security**. It uses a mock agent, a mock MCP-style tool, deterministic timestamps, and SHA-256 over canonical JSON so the chain is easy to inspect and replay.

## Quick start

Run the full demo with one command:

```bash
python demo.py
```

That command generates `archive.jsonl` and immediately replays it for verification.

To replay an existing archive:

```bash
./jep replay archive.jsonl
```

If the package is installed in editable mode, the command is also available as:

```bash
jep replay archive.jsonl
```

## Architecture flow

1. **Human** submits a request about invoice `INV-042`.
2. **Mock Agent** judges that structured invoice evidence is needed before answering.
3. **Mock MCP Tool** returns deterministic invoice validation evidence without calling any external system.
4. **JEP Events** capture the accountable decision path:
   - `Judgment`
   - `Delegation`
   - `Termination`
   - `Verification`
5. **HJS-style Receipt** binds each event to a deterministic `subject_hash` and mock signature.
6. **JAC-style Lineage** links each receipt-bearing event to the previous archive line hash.
7. **Archive** writes one JSON envelope per line to `archive.jsonl`.
8. **Replay** recomputes hashes from the archive.
9. **Verification** checks receipt integrity, lineage continuity, line hashes, and required event coverage.

## Generated artifacts

`python demo.py` creates:

| Artifact | Purpose |
| --- | --- |
| `archive.jsonl` | Append-friendly JSONL archive containing JEP events, HJS-style receipts, and JAC-style lineage links. |
| `jep_event` | The accountable event payload: type, actor, timestamp, judgment/delegation/termination/verification details. |
| `hjs_receipt` | A receipt with issuer, subject event ID, canonical JSON hash, and mock signature. |
| `jac_lineage` | A hash-chain link containing the previous line hash and current line hash. |
| Replay report | Human-readable verification output from `python demo.py` or `jep replay archive.jsonl`. |

A single archive line has this shape:

```json
{
  "sequence": 1,
  "jep_event": { "type": "Judgment", "event_id": "evt-001-judgment" },
  "hjs_receipt": { "receipt_type": "HJS-style-receipt", "subject_hash": "..." },
  "jac_lineage": { "lineage_type": "JAC-style-lineage-link", "previous_line_hash": "GENESIS", "line_hash": "..." }
}
```

## Replay output example

```text
Replay verification for archive.jsonl
Events replayed: 4
- PASS evt-001-judgment: Judgment receipt and lineage verified
- PASS evt-002-delegation: Delegation receipt and lineage verified
- PASS evt-003-termination: Termination receipt and lineage verified
- PASS evt-004-verification: Verification receipt and lineage verified
- PASS archive: required event types present
Verdict: PASS
```

## Why this is more than logging

Plain logs usually answer, "what text did the system print?" This demo shows a stronger accountability pattern:

- **Typed judgment events** explain why the agent made a decision.
- **Delegation events** identify the tool boundary and the exact mock tool input/output.
- **Receipts** bind event content to hashes, so replay can detect event mutation.
- **Lineage** chains each archive line to the previous one, so replay can detect reorder, deletion, or insertion.
- **Replay verification** recomputes the archive rather than trusting runtime output.
- **Termination and verification events** close the loop with final outcome and audit verdict.

This is still a toy implementation, but it demonstrates the core JEP stack as a verifiable chain instead of an unstructured stream of logs.

## Repository layout

```text
.
├── demo.py          # one-command full demo runner
├── jep              # executable wrapper for replay CLI
├── jep_core.py      # mock agent, mock tool, archive, replay, verification logic
├── pyproject.toml   # optional console-script entry point
└── README.md
```
