#!/usr/bin/env bash

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_DIR="$(mktemp -d)"
trap 'rm -rf "$TEST_DIR"' EXIT

export SCNET_HPC_LIVE_NODE_COUNT=no

(
    cd "$TEST_DIR"

    "$REPO_ROOT/scripts/new-job.sh" --cluster kseshell --user ciuser \
        dcu-smoke 1 8 00:05:00 >/dev/null
    grep -q '^#SBATCH --partition=kshdnormal$' dcu-smoke.slurm
    grep -q '^#SBATCH --gres=dcu:1' dcu-smoke.slurm

    "$REPO_ROOT/scripts/new-job.sh" --cluster kseshell --user ciuser --cpu-only \
        cpu-build 0 32 01:00:00 >/dev/null
    grep -q '^#SBATCH --partition=kshcnormal$' cpu-build.slurm
    if grep -q '^#SBATCH --gres=' cpu-build.slurm; then
        echo "CPU 作业不应包含 --gres" >&2
        exit 1
    fi

    "$REPO_ROOT/scripts/new-job.sh" --cluster kseshell --user ciuser \
        --partition kshdAI short-probe 1 8 00:10:00 >/dev/null
    grep -q '^#SBATCH --partition=kshdAI$' short-probe.slurm

    if "$REPO_ROOT/scripts/new-job.sh" --cluster kseshell --user ciuser \
        'bad name' 1 8 00:05:00 >/dev/null 2>&1; then
        echo "非法作业名应被拒绝" >&2
        exit 1
    fi
)

echo "new-job tests passed"
