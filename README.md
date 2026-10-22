# scnet-hpc

[中文](README_CN.md) | English

Current release: **0.6.14**

```bash
python3 scripts/scnet.py --version
```

<!-- scnet-release:start -->
## 0.6.14 highlights

- Recover malformed Windows credential entries with actionable, redacted guidance.
- Print absolute follow-up commands that work from any directory, with shell-appropriate quoting.
- Synchronize first-use preparation checklists into both distribution READMEs and clarify
  native Windows OpenAPI support, with regression coverage for both layouts.
<!-- scnet-release:end -->

`scnet-hpc` is a Codex and Claude Code skill for operating SCNet HPC clusters through
profile-based SSH, SCNet OpenAPI, and pluggable future backends. It complements the [SCNet desktop client](https://www.scnet.cn/ui/mall/client/download),
which provides official downloads for Windows 10+, macOS 12 Monterey+ (ARM and x86), and
Android preview builds.

## What to prepare for first use

Start with **OpenAPI** for queries and standard job management. Add SSH when you need remote
compilation, environment installation, or shell commands.

| Connection | Required inputs | Where to obtain them |
| --- | --- | --- |
| OpenAPI (default) | Platform username, AK, SK | Sign in to SCNet > Personal Center / 个人中心 > Access Control / 访问控制 > generate and download the authorization file. Use its `Accesskey` and `Secretkey` columns. |
| SSH (as needed) | Target cluster, cluster/Linux username, private-key file path | Select the region in the console > Command Line E-Shell / 命令行 E-Shell > SSH Connection / SSH 连接 at top left. Download the key and check host/port; verify the username with `whoami` in that region's web E-Shell. |

Your account needs access to the target region. Prepare credentials for the chosen connection;
explanations and offline preparation require none. **Enter AK/SK only in your own terminal's hidden
prompts. For SSH, supply a local file path. Keep keys and private-key contents out of chat.**

Ask your agent to help configure scnet-hpc for the first time. The Skill explains the inputs and
their sources before providing a local command for your OS and actual installation directory.
See the [first-use checklist](references/first-use.md) and configuration panel below.

Supported local operating systems:

- **Linux:** natively supported by the repository scripts;
- **macOS:** natively supported by the repository scripts;
- **Windows:** the Python OpenAPI entry point supports PowerShell and Windows Credential Manager.
  Use WSL2 for automatic SSH key installation and the complete Bash-based workflows.
  Git Bash may support some commands, but it is not a fully validated environment.

It provides:

- SSH configuration for SCNet access endpoints;
- structured resource and job operations through the SCNet OpenAPI control plane;
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
├── VERSION                  Synchronized SemVer release
├── CHANGELOG.md             Release history
├── SKILL.md                 Skill entrypoint, routing, and operational invariants
├── agents/
│   └── openai.yaml          Codex UI metadata
├── clusters/
│   ├── _template.conf       Cluster profile template
│   └── <cluster>.conf       Versioned cluster profiles
├── scripts/
│   ├── scnet.py              Backend-neutral CLI
│   ├── scnet_backends/       SSH, OpenAPI, and external adapters
│   ├── scnet_sdk/            Shared OpenAPI client and Notebook lifecycle service
│   ├── _common.sh           Profile loading and shared functions
│   ├── setup-ssh.sh         SSH configuration
│   ├── new-job.sh           Slurm script generation
│   ├── probe-cluster.sh     Initial cluster discovery
│   ├── refresh-cluster.sh   Dynamic profile refresh
│   ├── run-compute-probe.sh Compute-node probe submission
│   ├── setup.sh              Configuration and maintenance panel
│   ├── compute-probe.py     Accelerator capability probe
│   └── install.sh           Skill installation
├── references/              Operation-specific procedures
└── tests/                   Script regression tests
```

Cluster profiles remain at the repository root because they are executable configuration
consumed directly by the scripts. `references/` contains instructions loaded only for the
relevant operation.

## Installation

### One-line agent install

Paste this single sentence into Codex:

> Use `$skill-installer` to install the `scnet-hpc` Skill from the root of GitHub repository `lql341/scnet-hpc` (path `.`), name it `scnet-hpc`, do not overwrite an existing destination, then run `python3 scripts/scnet.py --help` from the installed directory and report the installation path.

This installs from the canonical repository rather than a downstream plugin mirror. The Skill
becomes available on the next turn.

The equivalent verified official installer command is:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo lql341/scnet-hpc \
  --path . \
  --name scnet-hpc \
  --method download
```

Verify:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/scnet-hpc/scripts/scnet.py" --help
```

### Install from a clone

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

## First-use configuration panel

On a new computer, run:

```bash
./scripts/setup.sh
```

The setup lifecycle is explicit:

```bash
./scripts/setup.sh new       # add a connection without replacing existing ones
./scripts/setup.sh modify    # edit defaults, rotate SSH keys, refresh OpenAPI
./scripts/setup.sh status    # read-only status
./scripts/setup.sh reset     # scoped reset; real SSH keys are preserved by default
```

The Bash panel can be rerun to select a profile, update an SSH user/key for that profile, and
record key-expiry metadata inferred from the downloaded filename. OpenAPI setup requires Python 3.
Without Python, only first-time SSH setup is supported; updating an existing main configuration
requires Python to preserve unrelated fields. The panel defaults to `new` on first use and
`modify` when configured. It preserves the saved backend choice and otherwise defaults to OpenAPI.
OpenAPI uses one platform username/AK/SK credential set to discover all authorized regions and
schedulers. It saves only non-secret choices under
`~/.config/scnet-hpc/config.json` (or `$XDG_CONFIG_HOME/scnet-hpc/config.json`); AK/SK and
tokens are never written there. SSH metadata is stored in `ssh/<profile>.json` and OpenAPI
region metadata in `openapi.json` under the same configuration directory.

Developers can use the richer Python panel, which validates OpenAPI credentials and discovers
authorized regions and schedulers:

```bash
python3 scripts/scnet.py setup
```

Paste the platform user, AccessKey, and SecretKey values individually in the setup panel;
both keys are hidden. The panel rejects pasted assignments, line breaks, and invisible characters,
verifies saved credentials by reading them back, and distinguishes region setup from credential persistence.

| Platform | Persistent AK/SK storage | Requirements |
|---|---|---|
| macOS | Built-in Keychain | No extra package; allow/unlock access when prompted |
| Linux desktop | Secret Service | `secret-tool` plus a running, unlocked keyring; Ubuntu/Debian: `libsecret-tools` |
| Linux server/headless | Environment injection | No keyring dependency for API calls; installing the CLI alone does not start a keyring |
| Native Windows | Current user's Windows Credential Manager | Python 3; no extra keyring package |

On Windows, run `python scripts/scnet.py setup new --mode openapi` from PowerShell.
Environment credentials take precedence over the system store. PowerShell `$env:` assignments affect
the current session and subsequently launched children, not an already-running desktop application.
See [`references/openapi.md`](references/openapi.md) for storage locations and injection examples.

Notebook is integrated as a separate service domain with read-only discovery and
confirmation-driven lifecycle operations:

```bash
python3 scripts/scnet.py --backend openapi notebook regions
python3 scripts/scnet.py --backend openapi --region <region-id> notebook resources
python3 scripts/scnet.py --backend openapi --region <region-id> notebook list
python3 scripts/scnet.py --dry-run --backend openapi \
  notebook create --region <region-id>
python3 scripts/scnet.py --backend openapi \
  notebook smoke --region <region-id>
```

Passwords and credential-bearing URL queries are redacted by default. Create automatically
selects the smallest available resource and trusted preset Jupyter image. Mutations require
confirmation; non-interactive callers must pass `--yes`. Smoke tests stop and release the
temporary instance in cleanup.

OpenAPI regions support multi-selection: use ↑/↓, Space, `a` for all, and Enter to save.
Enabled regions are stored separately from the single default region. Job submission always
requires exactly one target region to prevent duplicate submissions.

Obtain AK/SK from SCNet **Personal Center → Access Control**, where the authorization file can
be generated and downloaded. In an interactive terminal, use ↑/↓ and Enter or type a displayed
number and press Enter. Press Enter without a number to accept the current/default item.
On Ubuntu/Debian, install the Secret Service CLI with `sudo apt install libsecret-tools`.

Check the result without changing anything:

```bash
python3 scripts/scnet.py doctor
python3 scripts/scnet.py --backend openapi doctor
```

Use `./scripts/setup.sh --skip-connect` to save selections without installing a key or
contacting a remote service.
The default backend can still be overridden per command with `--backend`.

## Cluster selection

```bash
ls clusters/*.conf
sed -n '1,220p' clusters/<cluster>.conf
```

Profiles contain connection endpoints, scheduler limits, partition names, hardware descriptions,
module selections, network observations, and known limitations. Dynamic observations are written
to `clusters/.cache/<cluster>.auto.conf` and can override the corresponding versioned fields.

When multiple profiles exist, pass `--cluster <name>` explicitly.

## Backend selection

OpenAPI with AK/SK is the preferred default for structured cluster operations. SSH remains
available for environment setup, compilation, interactive diagnosis, and other shell workflows.
List built-in and discovered backends with:

```bash
python3 scripts/scnet.py backends
```

Examples:

```bash
python3 scripts/scnet.py --backend ssh --cluster <cluster> queues
python3 scripts/scnet.py --backend openapi clusters
python3 scripts/scnet.py --backend openapi --region <region-id> job <job-id>
```

Selection precedence is `--backend`, `SCNET_HPC_BACKEND`, saved setup-panel default, profile
`DEFAULT_BACKEND`, then `openapi`. Use `--backend ssh` to select SSH explicitly. The client does
not silently fall back between backends.

OpenAPI credentials are injected through environment variables or a host credential manager;
never put AK, SK, or tokens in a profile. See
[`references/openapi.md`](references/openapi.md). MCP bridges and platform connectors can be
registered through the external protocol in
[`references/backends.md`](references/backends.md).

OpenAPI supports remote directory creation and automatically switches files larger than 8 MiB
to the documented chunked upload flow. Use `--dry-run` to preview mutations without contacting
the backend.

## SSH configuration

SSH uses a private-key file downloaded from the target cluster console, independently of AK/SK.
Use the cluster/Linux username, which can differ from the platform account. The wizard previews the
target host, installed-key path, and handling of existing configuration before requesting input.
Enter the file path, not the private-key text or a `.pub` public-key file.

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
| [`backends.md`](references/backends.md) | Backend selection, capabilities, and extension protocol |
| [`openapi.md`](references/openapi.md) | OpenAPI credentials, commands, and validation boundaries |
| [`notebook.md`](references/notebook.md) | Notebook discovery, lifecycle, and redaction rules |

## Validation

```bash
bash tests/test-new-job.sh
python3 tests/test-backends.py
```

Local tests cover job generation, profile parsing, OpenAPI signing and normalization, and the
external backend contract. They do not submit remote jobs or call the live OpenAPI.

## Security and publication

Do not commit private keys, access tokens, personal usernames, internal hostnames, node names,
job identifiers, private mirror addresses, or generated job scripts containing user-specific
paths. Public compatibility reports should preserve reproducible environment and result data
while replacing identifying infrastructure details with placeholders.

## License

This project is released under the [MIT License](LICENSE). Subject to the license terms, the software may be used, copied, modified, merged, published, sublicensed, and distributed, including for commercial purposes.

Redistributions must retain the copyright notice and the MIT license notice. The software is provided “as is,” without warranties of any kind; users are responsible for evaluating the suitability and risks of the code, scripts, cluster profiles, and generated outputs for their own environment.

## Versioning

The source Skill, DSH package, and Codex Plugin use the same SemVer release train. `VERSION` is
the source of truth. Update the two `RELEASE_HIGHLIGHTS` files for the current English and Chinese
summary, then run `python3 .github/scripts/release_docs.py`. CI checks the generated README block,
synchronizes both distribution repositories, and publishes the matching tags, GitHub Releases,
and npm package after validation. Full history remains in [CHANGELOG.md](CHANGELOG.md).

## Compact output and waiting

Default job output includes ID, state, queue, and available exit code or failure reason.
Empty fields are omitted; zero and false are retained. Use `--details` for all normalized
fields and `--raw` for backend data. `--json` retains its envelope with compact formatting;
`--dry-run` always retains the complete preview. Consumers needing the previous complete
CLI payload must pass `--details`; SDK/backend return schemas are preserved.

```bash
python3 scripts/scnet.py --region <id> job <job-id>
python3 scripts/scnet.py --details --region <id> job <job-id>
python3 scripts/scnet.py --region <id> wait <job-id> --interval 3 --wait-timeout 180
```

`wait` polls internally and emits only the final result or timeout summary. OpenAPI live
`COMPLETED` can also describe a recently cancelled job: until accounting confirms the state,
output reports `FINALIZING`. Waiting may therefore include accounting update latency.
Transfers return the target path and byte count; logs return only the requested lines.
