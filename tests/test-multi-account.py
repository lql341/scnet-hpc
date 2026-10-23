#!/usr/bin/env python3
"""Session-scoped OpenAPI accounts; no network or real secrets."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scnet
import scnet_credentials as creds
from scnet_backends.profile import list_profiles, load_profile
from scnet_config import load_user_config, save_ssh_alias, save_user_config


class MultiAccountTests(unittest.TestCase):
    def test_namespaced_store_and_no_legacy_fallback(self):
        self.assertNotEqual(creds.account_service("alice"), creds.account_service("bob"))
        self.assertNotEqual(creds.account_service("alice"), creds.SERVICE)
        with patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "alice"}, clear=True), patch(
            "scnet_credentials.secure_store_name", return_value="macOS Keychain"
        ), patch("scnet_credentials.subprocess.run", return_value=Mock(returncode=1, stdout="")) as run:
            self.assertEqual(creds.load_openapi_credentials(), (None, None))
            self.assertIn(creds.account_service("alice"), run.call_args.args[0])
            self.assertNotIn(creds.SERVICE, run.call_args.args[0])

    def test_named_storage_targets_distinct_keychain_items(self):
        with patch("scnet_credentials.secure_store_name", return_value="macOS Keychain"), patch(
            "scnet_credentials.subprocess.run", return_value=Mock(returncode=0)
        ) as run:
            creds.store_openapi_credentials("alice", "ak", "sk", account="alice")
            first = run.call_args.args[0]
            creds.store_openapi_credentials("bob", "ak", "sk", account="bob")
            second = run.call_args.args[0]
            self.assertNotEqual(first[first.index("-s") + 1], second[second.index("-s") + 1])
            creds.delete_openapi_credentials("alice")
            self.assertIn(creds.account_service("alice"), run.call_args.args[0])

    def test_credentials_override_account_as_complete_set_only(self):
        env = {"SCNET_OPENAPI_ACCOUNT": "alice", "SCNET_OPENAPI_USER": "bob",
               "SCNET_OPENAPI_ACCESS_KEY": "ak", "SCNET_OPENAPI_SECRET_KEY": "sk"}
        with patch.dict(os.environ, env, clear=True), patch("scnet_credentials.load_secure_credentials") as store:
            self.assertEqual(creds.load_openapi_credentials()[0]["user"], "bob")
            store.assert_not_called()
        env.pop("SCNET_OPENAPI_SECRET_KEY")
        with patch.dict(os.environ, env, clear=True), patch("scnet_credentials.load_secure_credentials") as store:
            with self.assertRaises(creds.CredentialError):
                creds.load_openapi_credentials()
            store.assert_not_called()

    def test_invalid_alias_rejected_without_store_access(self):
        with patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "../alice"}, clear=True), patch("scnet_credentials.load_secure_credentials") as store:
            with self.assertRaises(creds.CredentialError):
                creds.load_openapi_credentials()
            store.assert_not_called()

    def test_setup_named_account_keeps_legacy_and_other_accounts(self):
        backend = Mock()
        backend.discover_all_region_contexts.return_value = [{
            "name": "New", "region_id": "new", "username": "new-user", "home_path": "/new",
            "schedulers": [{"id": "scheduler", "name": "Scheduler"}],
        }]
        old = {"platform_user": "legacy", "default_region_id": "old", "accounts": {
            "bob": {"platform_user": "bob", "default_region_id": "bob-region"}
        }}
        with (patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "alice"}, clear=True),
              patch("scnet.load_user_config", return_value={"default_backend": "ssh", "openapi": old}),
              patch("scnet.load_openapi_credentials", return_value=(None, None)),
              patch("scnet._ask_credential", side_effect=["alice", "ak", "sk"]),
              patch("scnet._choose", side_effect=lambda prompt, choices, default=1: choices[0]),
              patch("scnet._multi_choose", side_effect=lambda prompt, choices, defaults=None: choices),
              patch("scnet._with_openapi_credentials", return_value=(backend, {})),
              patch("scnet.secure_store_name", return_value=None),
              patch("scnet.save_user_config", return_value=Path("test.json")),
              contextlib.redirect_stdout(io.StringIO())):
            config = scnet.setup_panel("openapi", "new")
        self.assertEqual(config["default_backend"], "openapi")
        self.assertEqual(config["openapi"]["platform_user"], "legacy")
        self.assertEqual(config["openapi"]["accounts"]["bob"]["default_region_id"], "bob-region")
        self.assertEqual(config["openapi"]["accounts"]["alice"]["default_region_id"], "new")
        self.assertEqual(scnet.apply_openapi_defaults({}, config["openapi"]["accounts"]["alice"])["region"], "new")

    def test_named_account_region_defaults_are_isolated(self):
        config = {"openapi": {"default_region_id": "legacy", "accounts": {
            "alice": {"default_region_id": "alice-region"},
            "bob": {"default_region_id": "bob-region"},
        }}}
        with patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "alice"}, clear=True), patch(
            "scnet.load_user_config", return_value=config
        ), patch("scnet.load_profile", return_value=(None, {})), patch(
            "scnet.create_backend", return_value=Mock(execute=lambda operation, options: options["region"])
        ), patch("scnet.choose_backend", return_value="openapi"), patch(
            "scnet.summarize_output", side_effect=lambda operation, data: data
        ), patch("scnet.compact_output", side_effect=lambda operation, data, **kwargs: str(data)):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(scnet.main(["queues"]), 0)
            self.assertIn("alice-region", output.getvalue())
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(scnet.main(["--account", "bob", "queues"]), 0)
            self.assertIn("bob-region", output.getvalue())
            self.assertNotIn("alice-region", output.getvalue())

    def test_local_ssh_alias_inherits_profile_without_overwriting_base(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            repo = Path(directory) / "repo"
            (repo / "clusters").mkdir(parents=True)
            (repo / "clusters" / "base.conf").write_text('CLUSTER_ID="base"\nSSH_HOST="example.invalid"\nSSH_PORT="65032"\n')
            path = save_ssh_alias("base-user2", "base")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertIn("base-user2", [p["name"] for p in list_profiles(repo)])
            self.assertEqual(load_profile(repo, "base-user2")[1]["CLUSTER_ID"], "base-user2")
            self.assertEqual(load_profile(repo, "base-user2")[1]["SSH_PORT"], "65032")
            self.assertEqual(load_profile(repo, "base")[1]["CLUSTER_ID"], "base")
            with self.assertRaises(ValueError):
                save_ssh_alias("base-user2", "base")
            with self.assertRaises(ValueError):
                save_ssh_alias("../bad", "base")
            (repo / "clusters" / "base.conf").unlink()
            self.assertNotIn("base-user2", [p["name"] for p in list_profiles(repo)])

    @unittest.skipIf(os.name == "nt", "Bash panel runs under macOS/Linux/WSL2")
    def test_bash_loader_accepts_local_ssh_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
                save_ssh_alias("zzeshell-testing", "zzeshell")
            result = subprocess.run(
                ["bash", "-c", "export SCNET_HPC_LIVE_NODE_COUNT=no; source scripts/_common.sh; load_cluster zzeshell-testing; printf '%s' \"$CLUSTER_ID\""],
                cwd=Path(__file__).resolve().parent.parent,
                env={**os.environ, "XDG_CONFIG_HOME": directory},
                capture_output=True, text=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "zzeshell-testing")

    def test_ssh_setup_does_not_change_openapi_default(self):
        config = {"default_backend": "openapi", "ssh": {"clusters": {
            "sample": {"username": "cluster-user", "key_path": "/tmp/example-key"}
        }}}
        with (patch.dict(os.environ, {}, clear=True),
              patch("scnet.load_user_config", return_value=config),
              patch("scnet.list_profiles", return_value=[{"name": "sample"}]),
              patch("scnet.load_profile", return_value=(None, {})),
              patch("scnet._resolved_ssh_connection", return_value={}),
              patch("scnet._detect_ssh_username", return_value="cluster-user"),
              patch("scnet._choose", return_value="sample"),
              patch("scnet._ask", return_value="cluster-user"),
              patch("scnet.save_user_config", return_value=Path("test.json")),
              contextlib.redirect_stdout(io.StringIO())):
            try:
                scnet.setup_panel._skip_connect = True
                result = scnet.setup_panel("ssh", "modify")
            finally:
                scnet.setup_panel._skip_connect = False
        self.assertEqual(result["default_backend"], "openapi")

    def test_panel_adopts_existing_independent_alias_without_replacing_original(self):
        base = {"CLUSTER_ID": "base", "SSH_HOST": "example.invalid", "SSH_PORT": "65032"}
        found = {"username": "new-user", "key_path": "/tmp/example-key", "hostname": "example.invalid", "port": "65032"}
        current = {"default_backend": "openapi", "cluster": "base", "ssh": {"clusters": {
            "base": {"username": "old-user", "key_path": "/tmp/old-key"}
        }}}
        with (patch.dict(os.environ, {}, clear=True),
              patch("scnet.load_user_config", return_value=current),
              patch("scnet.list_profiles", return_value=[{"name": "base"}]),
              patch("scnet.load_profile", return_value=("base", base)),
              patch("scnet._ask_yes_no", side_effect=[True, False, True]),
              patch("scnet._choose", side_effect=lambda prompt, choices, default=1: choices[0]),
              patch("scnet._ask", side_effect=["base-user2", "new-user", ""]),
              patch("scnet._resolved_ssh_connection", side_effect=lambda name, profile: found if name=="base-user2" else {}),
              patch("scnet._detect_ssh_username", return_value="new-user"),
              patch("scnet.subprocess.run", return_value=Mock(returncode=0)),
              patch("scnet._ssh_key_metadata", return_value={"username": "new-user", "key_path": "/tmp/example-key"}),
              patch("scnet.save_ssh_alias") as register,
              patch("scnet.save_user_config", return_value=Path("test.json")),
              patch("scnet.Path.read_text", return_value="Host base-user2\n"),
              patch("pathlib.Path.is_file", return_value=True),
              contextlib.redirect_stdout(io.StringIO())):
            result = scnet.setup_panel("ssh", "new")
        register.assert_called_once_with("base-user2", "base")
        self.assertEqual(result["cluster"], "base")
        self.assertEqual(result["default_backend"], "openapi")
        self.assertEqual(result["ssh"]["clusters"]["base"]["username"], "old-user")
        self.assertEqual(result["ssh"]["clusters"]["base-user2"]["username"], "new-user")

    def test_panel_registers_new_alias_before_key_installer(self):
        alias = "example-panel-new-test"
        base = {"CLUSTER_ID": "zzeshell", "SSH_HOST": "example.invalid", "SSH_PORT": "65032"}
        calls = []
        with (patch.dict(os.environ, {}, clear=True),
              patch("scnet.load_user_config", return_value={"default_backend": "openapi"}),
              patch("scnet.list_profiles", return_value=[{"name": "zzeshell"}]),
              patch("scnet.load_profile", return_value=("zzeshell", base)),
              patch("scnet._ask_yes_no", side_effect=[True, True]),
              patch("scnet._choose", side_effect=lambda prompt, choices, default=1: choices[0]),
              patch("scnet._ask", side_effect=[alias, "/tmp/example-key", "new-user"]),
              patch("scnet._resolved_ssh_connection", return_value={}),
              patch("scnet._detect_ssh_username", return_value="new-user"),
              patch("scnet._run_setup_ssh", side_effect=lambda *args: calls.append("install")),
              patch("scnet.save_ssh_alias", side_effect=lambda *args: calls.append("register")),
              patch("scnet._ssh_key_metadata", return_value={"username": "new-user"}),
              patch("scnet.save_user_config", return_value=Path("test.json")),
              patch("scnet.Path.is_file", return_value=True),
              contextlib.redirect_stdout(io.StringIO())):
            result = scnet.setup_panel("ssh", "new")
        self.assertEqual(calls, ["register", "install"])
        self.assertEqual(result["default_backend"], "openapi")
        self.assertNotIn("cluster", result)
        self.assertIn(alias, result["ssh"]["clusters"])

    def test_mismatched_environment_user_cannot_use_saved_region(self):
        config = {"openapi": {"accounts": {"alice": {
            "platform_user": "alice", "default_region_id": "alice-region"
        }}}}
        backend = Mock()
        with patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "alice"}, clear=True), patch(
            "scnet.load_user_config", return_value=config
        ), patch("scnet.load_profile", return_value=(None, {})), patch(
            "scnet.create_backend", return_value=backend
        ), patch("scnet.choose_backend", return_value="openapi"), patch(
            "scnet.load_openapi_credentials", return_value=({"user": "bob"}, "environment")
        ), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(scnet.main(["queues"]), 2)
        backend.execute.assert_not_called()

    def test_cli_account_override_is_restored(self):
        with patch.dict(os.environ, {"SCNET_OPENAPI_ACCOUNT": "alice"}, clear=True), patch(
            "scnet.load_user_config", return_value={"openapi": {"accounts": {}}}
        ), patch("scnet.redacted_config", side_effect=lambda config: config):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(scnet.main(["--account", "bob", "config"]), 0)
            self.assertEqual(os.environ["SCNET_OPENAPI_ACCOUNT"], "alice")


if __name__ == "__main__":
    unittest.main()
