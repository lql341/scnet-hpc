#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
help="$("$REPO_ROOT/scripts/setup.sh" --help)"
printf '%s\n' "$help" | grep -q "configuration"
printf '%s\n' "$help" | grep -q -- "--skip-connect"

python_path="$(command -v python3)"
resolved="$(
    DSH_SCNET_PYTHON="$python_path" \
        bash -c 'set -euo pipefail; . "$1/scripts/_common.sh"; resolve_python' _ "$REPO_ROOT"
)"
[ "$resolved" = "$python_path" ]

if DSH_SCNET_PYTHON="$REPO_ROOT/does-not-exist" \
    bash -c 'set -euo pipefail; . "$1/scripts/_common.sh"; resolve_python' _ "$REPO_ROOT"; then
    echo "invalid injected Python path should fail" >&2
    exit 1
fi

python3 - "$REPO_ROOT" <<'PYTEST'
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root = Path(sys.argv[1])
source = (root / "scripts/setup.sh").read_text()
# Exercise the actual shell functions without starting the interactive panel.
def function(name):
    start = source.index(name + "() {\n")
    end = source.index("\n}\n", start) + 3
    return source[start:end]

functions = "\n".join(function(name) for name in ("ask", "choose", "json_string", "write_config"))
with tempfile.TemporaryDirectory() as temporary:
    env = dict(os.environ, XDG_CONFIG_HOME=temporary)
    prefix = 'set -euo pipefail\ndie() { echo "$*" >&2; exit 1; }\n' + functions
    result = subprocess.run(["bash", "-c", prefix + '\nSCNET_SETUP_CHOICE_DEFAULT=2 choose backend openapi ssh'],
                            input="\n", text=True, capture_output=True, env=env, check=True)
    assert result.stdout == "ssh", result.stdout
    config = Path(temporary) / "scnet-hpc/config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"default_backend": "openapi", "custom": {"retain": True}}))
    command = prefix + '\nSCRIPT_DIR="$1"; PYTHON_BIN="$2"; CLUSTER=example; DEFAULT_BACKEND=ssh; write_config'
    subprocess.run(["bash", "-c", command, "_", str(root / "scripts"), sys.executable],
                   text=True, capture_output=True, env=env, check=True)
    saved = json.loads(config.read_text())
    assert saved["custom"] == {"retain": True}
    assert saved["default_backend"] == "ssh" and saved["cluster"] == "example"
    before = config.read_bytes()
    result = subprocess.run(["bash", "-c", command, "_", str(root / "scripts"), ""],
                            text=True, capture_output=True, env=env)
    assert result.returncode != 0
    assert config.read_bytes() == before

# A pseudo-terminal satisfies the interactive entrypoint; TERM=dumb exercises numeric defaults.
import pty
def panel(env, answers, *arguments):
    master, slave = pty.openpty()
    try:
        process = subprocess.Popen(["bash", str(root / "scripts/setup.sh"), *arguments],
                                   stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, env=dict(env, TERM="dumb"))
        os.close(slave)
        slave = None
        os.write(master, answers.encode())
        stdout, stderr = process.communicate(timeout=15)
        return process.returncode, stdout + stderr
    finally:
        if slave is not None:
            os.close(slave)
        os.close(master)

with tempfile.TemporaryDirectory() as temporary:
    env = dict(os.environ, XDG_CONFIG_HOME=temporary, DSH_SCNET_PYTHON=sys.executable)
    code, output = panel(env, "\n\n", "--skip-connect")
    assert code == 0, output
    config = Path(temporary) / "scnet-hpc/config.json"
    assert json.loads(config.read_text())["default_backend"] == "openapi"
    # Existing configuration selects modify, allowing OpenAPI metadata refresh with skip-connect.
    region_cache = config.parent / "openapi.json"
    region_cache.write_text(json.dumps({"default_region_id": "example"}))
    code, output = panel(env, "\n\n", "--skip-connect")
    assert code == 0, output
    assert "默认项 3" in output, output
    saved = json.loads(config.read_text())
    saved["default_backend"] = "ssh"
    config.write_text(json.dumps(saved))
    code, output = panel(env, "\n\n", "--skip-connect")
    assert code != 0 and "没有已配置的 SSH profile" in output, output
    assert "默认项 2" in output, output
    before = config.read_bytes()
    env["DSH_SCNET_PYTHON"] = str(Path(temporary) / "missing-python")
    code, output = panel(env, "\n", "modify", "--backend", "openapi", "--skip-connect")
    assert code != 0 and "OpenAPI 配置需要 Python 3" in output, output
    assert config.read_bytes() == before
PYTEST

echo "setup panel smoke tests passed"
