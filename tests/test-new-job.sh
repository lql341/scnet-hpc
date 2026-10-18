#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

export SCNET_HPC_LIVE_NODE_COUNT=no
export SCNET_PYTHON="$(command -v python3)"

# Keep both ssh -G and live probes independent of local SSH configuration/network.
mkdir -p "$TEST_DIR/bin"
cat > "$TEST_DIR/bin/ssh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "-G" ]; then
    printf 'hostname mock.invalid\nuser ciuser\nport 22\n'
    exit 0
fi
printf 'probe\n' >> "$MOCK_SSH_LOG"
case "${MOCK_SSH_MODE:-fail}" in
    fail) echo 'simulated SSH connection failure' >&2; exit 255 ;;
    live) echo 'PartitionName=kshdnormal TotalNodes=777 State=UP' ;;
    empty) exit 0 ;;
    invalid) echo 'PartitionName=kshdnormal TotalNodes=invalid' ;;
    partial) echo 'PartitionName=kshdnormal TotalNodes=777'; exit 255 ;;
    *) echo 'unexpected mock SSH mode' >&2; exit 1 ;;
esac
EOF
chmod +x "$TEST_DIR/bin/ssh"
export PATH="$TEST_DIR/bin:$PATH"
export MOCK_SSH_LOG="$TEST_DIR/ssh-probes.log"

(
    cd "$TEST_DIR"

    "$REPO_ROOT/scripts/new-job.sh" --no-auto --cluster kseshell --user ciuser \
        dcu-smoke 1 8 00:05:00 >/dev/null
    grep -q '^#SBATCH --partition=kshdnormal$' dcu-smoke.slurm
    grep -q '^#SBATCH --gres=dcu:1' dcu-smoke.slurm

    "$REPO_ROOT/scripts/new-job.sh" --no-auto --cluster kseshell --user ciuser --cpu-only \
        cpu-build 0 32 01:00:00 >/dev/null
    grep -q '^#SBATCH --partition=kshcnormal$' cpu-build.slurm
    if grep -q '^#SBATCH --gres=' cpu-build.slurm; then
        echo "CPU 作业不应包含 --gres" >&2
        exit 1
    fi

    "$REPO_ROOT/scripts/new-job.sh" --no-auto --cluster kseshell --user ciuser \
        --partition kshdAI short-probe 1 8 00:10:00 >/dev/null
    grep -q '^#SBATCH --partition=kshdAI$' short-probe.slurm

    if "$REPO_ROOT/scripts/new-job.sh" --no-auto --cluster kseshell --user ciuser \
        'bad name' 1 8 00:05:00 >/dev/null 2>&1; then
        echo "非法作业名应被拒绝" >&2
        exit 1
    fi

    if [ -e "$MOCK_SSH_LOG" ]; then
        echo "禁用实时节点数探测时不应连接 SSH" >&2
        exit 1
    fi

    # A failed/empty/invalid probe keeps the profile count; valid output from a
    # failed SSH command must also be discarded. A successful probe uses live data.
    for mode in fail empty invalid partial live; do
        name="probe-$mode"
        env -u SCNET_HPC_LIVE_NODE_COUNT MOCK_SSH_MODE="$mode" \
            "$REPO_ROOT/scripts/new-job.sh" --no-auto --cluster kseshell --user ciuser \
            "$name" 1 8 00:05:00 > "$name.summary" 2> "$name.stderr"
        grep -q '^#SBATCH --partition=kshdnormal$' "$name.slurm"
        if [ "$mode" = live ]; then
            grep -Fq '节点数=777（来源：live）' "$name.summary"
        else
            grep -Fq '节点数=1368（来源：profile/cache）' "$name.summary"
        fi
        test ! -s "$name.stderr"
    done
    test "$(wc -l < "$MOCK_SSH_LOG")" -eq 5
)

echo "new-job tests passed"
