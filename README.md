# scnet-hpc

`scnet-hpc` is a Codex and Claude Code skill for operating SCNet HPC clusters through
profile-based SSH and Slurm workflows.

It provides:

- SSH configuration for SCNet access endpoints;
- Slurm job generation for CPU and accelerator partitions;
- cluster discovery and refresh probes;
- login-node and compute-node workflow separation;
- offline dependency and shared-temporary-directory conventions;
- Hygon DCU/DTK compatibility guidance and compute-node verification.

The current accelerator-specific evidence focuses on Hygon DCU systems. Profiles for other
accelerators can reuse the connection and scheduling structure, but their software capabilities
must be verified independently.

## Repository structure

```text
scnet-hpc/
├── SKILL.md                 Skill entrypoint, routing, and operational invariants
├── agents/
│   └── openai.yaml          Codex UI metadata
├── clusters/
│   ├── _template.conf       Cluster profile template
│   └── <cluster>.conf       Versioned cluster profiles
├── scripts/
│   ├── _common.sh           Profile loading and shared functions
│   ├── setup-ssh.sh         SSH configuration
│   ├── new-job.sh           Slurm script generation
│   ├── probe-cluster.sh     Initial cluster discovery
│   ├── refresh-cluster.sh   Dynamic profile refresh
│   ├── run-compute-probe.sh Compute-node probe submission
│   ├── compute-probe.py     Accelerator capability probe
│   └── install.sh           Skill installation
├── references/              Operation-specific procedures
└── tests/                   Script regression tests
```

Cluster profiles remain at the repository root because they are executable configuration
consumed directly by the scripts. `references/` contains instructions loaded only for the
relevant operation.

## Installation

```bash
git clone https://github.com/lql341/scnet-hpc.git
cd scnet-hpc
./scripts/install.sh
```

Installation modes:

```bash
./scripts/install.sh --project  # Install into the current project
./scripts/install.sh --codex    # Select the Codex skill directory
./scripts/install.sh --claude   # Select the Claude Code skill directory
./scripts/install.sh --link     # Link the repository for local development
```

Existing installations are moved to a timestamped backup before replacement.

## Cluster selection

```bash
ls clusters/*.conf
sed -n '1,220p' clusters/<cluster>.conf
```

Profiles contain connection endpoints, scheduler limits, partition names, hardware descriptions,
module selections, network observations, and known limitations. Dynamic observations are written
to `clusters/.cache/<cluster>.auto.conf` and can override the corresponding versioned fields.

When multiple profiles exist, pass `--cluster <name>` explicitly.

## SSH configuration

Obtain the private key from the SCNet console, then run:

```bash
./scripts/setup-ssh.sh --cluster <cluster> <private-key-file> <username>
```

The script copies the key to `~/.ssh/id_rsa_<cluster>`, adds a missing host entry, configures
connection reuse and keepalive, and verifies the connection. It does not replace an existing SSH
host block. See [`references/setup.md`](references/setup.md) for manual configuration and diagnosis.

## Job generation

```bash
./scripts/new-job.sh --cluster <cluster> train 1 8 00:20:00
./scripts/new-job.sh --cluster <cluster> --cpu-only build 0 32 01:00:00
./scripts/new-job.sh --cluster <cluster> --partition <partition> probe 1 8 00:10:00
```

The generator derives a conservative memory request from `DEF_MEM_PER_CPU`, applies the
profile's GRES and module settings, configures offline-mode variables when needed, places
temporary files under shared home storage, and propagates the workload exit code.

Review the generated `.slurm` file before submission. Validate scheduler acceptance with
`sbatch --test-only` when supported. Remove `--test-only` only when actual submission is intended.

## Profile refresh

```bash
./scripts/refresh-cluster.sh --cluster <cluster>
./scripts/refresh-cluster.sh --cluster <cluster> --compute
./scripts/refresh-cluster.sh --cluster <cluster> --dry-run
```

The default refresh is read-only on the login node. `--compute` submits a small Slurm job and
therefore consumes cluster resources.

## Adding a cluster

After establishing a temporary working SSH alias:

```bash
./scripts/probe-cluster.sh <ssh-alias> <cluster-name> \
  > clusters/<cluster-name>.conf
```

Complete fields that cannot be established from the login node, particularly accelerator
architecture, module selection, CPU-only partition behavior, and compute-node network access.
Then configure the permanent SSH alias and run a bounded validation job. See
[`references/adding-cluster.md`](references/adding-cluster.md).

## References

| Document | Scope |
|---|---|
| [`setup.md`](references/setup.md) | SSH configuration and connection failures |
| [`environment.md`](references/environment.md) | Modules, Python environments, dependencies, and storage |
| [`troubleshooting.md`](references/troubleshooting.md) | Slurm, logs, runtime, network, and accelerator failures |
| [`adding-cluster.md`](references/adding-cluster.md) | Profile creation and cluster validation |
| [`hygon-dcu-development.md`](references/hygon-dcu-development.md) | Hygon DCU/DTK development resources |
| [`software-compatibility.md`](references/software-compatibility.md) | Compatibility validation and public reporting |
| [`quickstart-en.md`](references/quickstart-en.md) | English operating guide |

## Validation

```bash
bash tests/test-new-job.sh
```

The local test covers accelerator, CPU-only, explicit-partition, and invalid-input paths without
submitting remote jobs.

## Security and publication

Do not commit private keys, access tokens, personal usernames, internal hostnames, node names,
job identifiers, private mirror addresses, or generated job scripts containing user-specific
paths. Public compatibility reports should preserve reproducible environment and result data
while replacing identifying infrastructure details with placeholders.

## License

MIT
