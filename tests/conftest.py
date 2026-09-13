"""Exercise the SDK against the pinned reference API over loopback HTTP."""

import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import urllib.request
import pytest


@pytest.fixture(scope="session")
def api_server(tmp_path_factory):
    configured = os.environ.get("JEP_API_SOURCE")
    if not configured:
        pytest.fail(
            "Set JEP_API_SOURCE to a jep-api checkout; real API tests must not silently skip"
        )
    source = Path(configured).resolve()
    assert (source / "main.py").is_file(), source
    state = tmp_path_factory.mktemp("api")
    token = state / "token"
    token.write_text("local-integration-test-token")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    # Do not inherit production storage, external signing or credentials.
    env = {k: v for k, v in os.environ.items() if not k.startswith("JEP_")}
    env.update(JEP_STATE_DIR=str(state / "state"), JEP_SIGNING_TOKEN_FILE=str(token))
    with (state / "server.log").open("w+") as log:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
            ],
            cwd=source,
            env=env,
            stdout=log,
            stderr=log,
        )
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url + "/health", timeout=1) as response:
                        assert json.load(response)["profile"] == "jep-core-0.6"
                    break
                except OSError:
                    if proc.poll() is not None:
                        log.seek(0)
                        pytest.fail(log.read())
                    time.sleep(0.1)
            else:
                pytest.fail("Local API did not become ready")
            yield url, token.read_text()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def local_api(api_server, monkeypatch):
    url, token = api_server
    monkeypatch.setenv("JEP_API_URL", url)
    monkeypatch.setenv("JEP_API_KEY", token)
