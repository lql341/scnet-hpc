# Notebook service

Notebook is a separate SCNet OpenAPI service domain. It reuses platform authentication and
region discovery, but it is not a Slurm job and does not use `hpcUrls`.

Read-only commands:

```bash
python3 scripts/scnet.py --backend openapi notebook regions
python3 scripts/scnet.py --backend openapi --region <id> notebook resources
python3 scripts/scnet.py --backend openapi --region <id> notebook images
python3 scripts/scnet.py --backend openapi --region <id> notebook list
python3 scripts/scnet.py --backend openapi --region <id> notebook show <notebook-id>
python3 scripts/scnet.py --backend openapi --region <id> notebook url <notebook-id>
```

The default output redacts SSH passwords and URL query credentials. Use `--reveal` only when
the user explicitly needs a URL to open, and do not place the resulting value in reports or
long-lived logs.

Notebook creation, start, stop, and release are intentionally not exposed by this first
read-only integration. They consume resources or change external state and require a later
confirmation-driven workflow.

Official API sections:

- Notebook resource discovery;
- image discovery;
- instance list/detail;
- Jupyter URL lookup;
- instance lifecycle.
