# JEP end-to-end demo

A signed J/D/T/V flow using `jep-sdk-py` and a local JEP-Core-0.6 API. The demo requests invoice evidence, declares delegation, terminates that declaration and records a verification statement. It does not call a real invoice service or grant tool authority.

## Start a local API (terminal 1)

Python 3.10 or newer is required. From the parent directory of this clone:

```bash
git clone https://github.com/hjs-spec/jep-api.git
cd jep-api
git checkout v0.7.3
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export JEP_STATE_DIR="$PWD/.local-state"
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

This starts a loopback development service and preserves its local verification keys across restarts. Keep that state directory to replay prior archives. This is not a live deployment; no public service or database is required. API software version 0.7.3 implements protocol profile `jep-core-0.6`, wire `jep: "1"`.

The SDK defaults to `http://127.0.0.1:8000`. Set `JEP_API_URL` to another explicitly trusted API, and `JEP_API_KEY` if it requires a signing token. Archival verification relies on that API's trusted key store.

## Install and run (terminal 2)

```bash
git clone https://github.com/hjs-spec/jep-e2e-demo.git
cd jep-e2e-demo
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
jep-e2e demo --archive archives/first.jsonl
jep-e2e replay archives/first.jsonl
```

`python demo.py` also runs the real flow and chooses a unique archive name. Explicit output paths must not already exist, so existing evidence is never overwritten.

The JSONL envelope contains `format`, `sequence`, `event`, `event_hash` and `previous_event_hash`. Only `event` is the signed Core object. The other fields describe this application's archive; they are not required JEP fields, HJS receipts or JAC declarations. Signed `ref` values link the four demo events. Replay verifies every signature through the API, hashes, sequence, references and expected J/D/T/V order. The `V` statement follows an actual verification of its predecessor.

Success means Core Level 1 plus local demo ordering checks. It does not prove identity binding, real delegation authority, policy approval, HJS/JAC conformance, external outcomes or completeness against an independently trusted archive anchor.

## Historical mock and migration

The old unsigned archive is preserved byte-for-byte at `legacy/archive.jsonl`. Inspect it explicitly:

```bash
jep-e2e --legacy-mock replay legacy/archive.jsonl
```

That mode checks the old mock's hash consistency only. It does not provide cryptographic authentication. The default replay rejects old archives rather than silently upgrading their meaning.

Version 0.2.0 renames this package's command from `jep` to `jep-e2e`. `jep` belongs to [jep-cli](https://github.com/hjs-spec/cli). If the old packages shared an environment, upgrade the old demo first, then repair CLI ownership:

```bash
python -m pip install --upgrade .
python -m pip install --force-reinstall 'jep-cli==0.6.1'
```

GitHub releases supply wheels/source archives; installation from this repository also works. This change does not configure a new PyPI publisher.

## Test

```bash
python -m pip install -e '.[test]' -r ../jep-api/requirements.txt
JEP_API_SOURCE=../jep-api python -m pytest -q
```

Tests use an isolated loopback API and temporary signing state. CI also checks installation alongside the standalone CLI.
