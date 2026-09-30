# Changelog

## 0.6.1 - 2026-09-30

- Complete job-state normalization and fall back from stale realtime job records to the
  documented history endpoint.
- Add compact active/history job listing and persist OpenAPI region tokens with a locked,
  permission-restricted cache.
- Clarify that OpenAPI uploads take a remote directory; the local filename is supplied
  separately and is never part of the directory path.

## 0.6.0 - 2026-09-30

- Surface the job lifecycle in the downstream DSH bundle: submission, status, logs, and
  cancellation become first-class tools instead of CLI-only operations.
- Add a convenience job-log mode for OpenAPI jobs that derives
  `{work_dir}/std.{out,err}.{job_id}`, while keeping explicit absolute paths as the general
  contract and as the only mode available over SSH.
- Canonical Skill behaviour is unchanged: the underlying OpenAPI and SSH job operations shipped in
  0.5.0. This release carries the downstream tool registration and its version alignment.

## 0.5.1 - 2026-09-30

- Align downstream DSH, Codex Plugin, and npm package versioning at the canonical release version.
- Update the DSH downstream sync workflow to preserve prerelease and stable version strings without duplication.

## 0.5.0 - 2026-09-27

- Added repeatable configuration lifecycle and SSH key rotation metadata.
- Added SCNet OpenAPI authentication, multi-region discovery, jobs, files, and transfer support.
- Added shared internal OpenAPI client for CLI, plugins, and future adapters.
- Added Notebook region, resource, image, instance, URL, and safe lifecycle operations.
- Added sensitive-field redaction, dry-run support, and confirmation-driven mutations.
- Added verified one-line Codex Skill installation.
- Expanded canonical, Codex Plugin, and DSH synchronization validation.
