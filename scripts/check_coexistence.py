"""Check command/file ownership in both wheel installation orders.

Usage: python scripts/check_coexistence.py TARGET.whl [EXTRA.whl ...]
The SDK, standalone CLI and historical agent SDK are tested together.
"""

import argparse
import email
import json
from pathlib import Path
import subprocess
import tempfile
import venv
import zipfile

BASE = ["jep-sdk-py==0.6.2", "jep-cli==0.6.1", "jep-agent-sdk==2.0.0"]
COMMANDS = {
    "jep-cli": "jep",
    "jep-agent-sdk": "jep-agent",
    "jep-runtime": "jep-runtime",
    "jep-e2e-demo": "jep-e2e",
}
MODULES = {
    "jep-sdk-py": "jep",
    "jep-cli": "jep_cli",
    "jep-agent-sdk": "jep_agent",
    "jep-runtime": "jep_runtime",
    "jep-e2e-demo": "jep_core",
}


def run(args, cwd):
    result = subprocess.run(
        [str(x) for x in args], cwd=cwd, capture_output=True, text=True, timeout=240
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return result.stdout


def wheel_name(path):
    with zipfile.ZipFile(path) as archive:
        metadata = next(
            n for n in archive.namelist() if n.endswith(".dist-info/METADATA")
        )
        return email.message_from_bytes(archive.read(metadata))["Name"]


def check(bin_dir, root, names):
    python = bin_dir / "python"
    code = """import importlib,json,sys
from importlib.metadata import distribution
names, modules = json.loads(sys.argv[1]), json.loads(sys.argv[2])
owned=[]
for name in names:
    package=distribution(name)
    files={str(package.locate_file(p).resolve()) for p in package.files}
    for previous in owned:
        assert not files & previous, files & previous
    owned.append(files)
    importlib.import_module(modules[name])
"""
    run([python, "-c", code, json.dumps(names), json.dumps(MODULES)], root)
    for name in names:
        if name in COMMANDS:
            run([bin_dir / COMMANDS[name], "--help"], root)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", type=Path, nargs="+")
    args = parser.parse_args()
    wheels = [path.resolve() for path in args.wheels]
    extra_names = [wheel_name(path) for path in wheels]
    assert all(name in MODULES for name in extra_names)
    names = [spec.split("==")[0] for spec in BASE] + extra_names
    for reverse in [False, True]:
        with tempfile.TemporaryDirectory(prefix="jep-installed-coexist-") as directory:
            root = Path(directory)
            venv.create(root / "env", with_pip=True)
            bin_dir = root / "env/bin"
            python = bin_dir / "python"
            groups = [BASE, wheels] if not reverse else [wheels, BASE]
            for group in groups:
                run(
                    [
                        python,
                        "-m",
                        "pip",
                        "install",
                        "--disable-pip-version-check",
                        *group,
                    ],
                    root,
                )
            remaining = list(names)
            check(bin_dir, root, remaining)
            # Each command-owning package can be removed without deleting another's files.
            for removed in [*extra_names, "jep-agent-sdk", "jep-cli"]:
                run([python, "-m", "pip", "uninstall", "-y", removed], root)
                remaining.remove(removed)
                check(bin_dir, root, remaining)
    print(
        "PASS: both install orders, disjoint file ownership and independent command uninstalls:",
        ", ".join(names),
    )


if __name__ == "__main__":
    main()
