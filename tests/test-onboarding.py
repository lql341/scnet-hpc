#!/usr/bin/env python3
"""Credential and onboarding regression tests; no real SCNet requests or credentials."""
from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import platform
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import uuid

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import scnet
import scnet_credentials as credentials
from scnet_config import load_user_config, save_user_config


class CredentialInputTests(unittest.TestCase):
    def test_quotes_and_outer_whitespace_are_normalized(self):
        for value in (' "example-value" ', "'example-value'", "“example-value”"):
            self.assertEqual(credentials.normalize_credential(value, "AccessKey"), "example-value")

    def test_invalid_pastes_never_echo_the_input(self):
        for value in ('export SCNET_OPENAPI_SECRET_KEY="private-example"', '$env:SCNET_OPENAPI_SECRET_KEY="private-example"', "SecretKey:private-example", "private-example\nsecond-line", "private-example\u200b"):
            with self.subTest(value=value), self.assertRaises(credentials.CredentialError) as caught:
                credentials.normalize_credential(value, "SecretKey")
            self.assertNotIn("private-example", str(caught.exception))

    def test_invalid_interactive_paste_can_be_reentered(self):
        output = io.StringIO()
        with patch("scnet._ask_secret", side_effect=["SecretKey:private-example", '"correct-example"']), contextlib.redirect_stdout(output):
            self.assertEqual(scnet._ask_credential("SecretKey", secret=True), "correct-example")
        self.assertNotIn("private-example", output.getvalue())

    def test_partial_environment_is_not_mixed_with_a_saved_account(self):
        with patch.dict(os.environ, {"SCNET_OPENAPI_USER": "example-user"}, clear=True), patch("scnet_credentials.load_secure_credentials") as saved:
            with self.assertRaises(credentials.CredentialError):
                credentials.load_openapi_credentials()
            saved.assert_not_called()

    def test_complete_environment_overrides_system_store(self):
        env = {"SCNET_OPENAPI_USER": "example-user", "SCNET_OPENAPI_ACCESS_KEY": "example-access", "SCNET_OPENAPI_SECRET_KEY": "example-secret"}
        with patch.dict(os.environ, env, clear=True), patch("scnet_credentials.load_secure_credentials") as saved:
            data, provider = credentials.load_openapi_credentials()
        self.assertEqual(provider, "environment")
        self.assertEqual(data["access_key"], "example-access")
        saved.assert_not_called()

    def test_store_timeout_does_not_include_keychain_arguments(self):
        with patch("scnet_credentials.secure_store_name", return_value="macOS Keychain"), patch("scnet_credentials.subprocess.run", side_effect=subprocess.TimeoutExpired(["security", "private-example"], 30)):
            with self.assertRaises(credentials.CredentialError) as caught:
                credentials.store_openapi_credentials("example-user", "example-access", "private-example")
        self.assertNotIn("private-example", str(caught.exception))

    def test_store_failure_does_not_echo_external_stderr(self):
        with patch("scnet_credentials.secure_store_name", return_value="Secret Service"), patch("scnet_credentials.subprocess.run", return_value=Mock(returncode=1, stderr="private-example")):
            with self.assertRaises(credentials.CredentialError) as caught:
                credentials.store_openapi_credentials("example-user", "example-access", "private-example")
        self.assertNotIn("private-example", str(caught.exception))


class SetupOutcomeTests(unittest.TestCase):
    def configure(self, provider, store_error=None, readback=True, use_environment=False):
        backend = Mock()
        backend.discover_all_region_contexts.return_value = [{"name": "Example", "region_id": "example", "username": "cluster-user", "home_path": "/home/example", "schedulers": [{"id": "slurm", "name": "Slurm"}]}]
        data = {"user": "example-user", "access_key": "example-access", "secret_key": "private-example"}
        output = io.StringIO()
        with (
            patch("scnet.load_user_config", return_value={}),
            patch("scnet.load_openapi_credentials", return_value=(data, "environment") if use_environment else (None, None)),
            patch("scnet._ask_credential", side_effect=list(data.values())) as ask_value,
            patch("scnet._ask_yes_no", return_value=True),
            patch("scnet._choose", side_effect=lambda prompt, choices, default=1: choices[0]),
            patch("scnet._multi_choose", side_effect=lambda prompt, choices, defaults=None: choices),
            patch("scnet._with_openapi_credentials", return_value=(backend, {})),
            patch("scnet.secure_store_name", return_value=provider),
            patch("scnet.store_openapi_credentials", return_value=provider, side_effect=store_error),
            patch("scnet.load_secure_credentials", return_value=data if readback else None),
            patch("scnet.save_user_config", return_value=Path("example-config.json")),
            patch.dict(os.environ, {}, clear=True),
            contextlib.redirect_stdout(output),
        ):
            result = scnet.setup_panel("openapi", "new")
        if use_environment:
            ask_value.assert_not_called()
        self.assertNotIn("private-example", output.getvalue())
        self.assertNotIn("example-access", json.dumps(result))
        self.assertNotIn("private-example", json.dumps(result))
        return result, output.getvalue()

    def test_no_store_records_unpersisted_credentials(self):
        result, output = self.configure(None)
        self.assertEqual(result["openapi"]["credential_provider"], "not_saved")
        self.assertIn("凭据未保存", output)
        self.assertNotIn("持久保存已验证", output)

    def test_failed_store_does_not_report_success(self):
        result, output = self.configure("Secret Service", credentials.CredentialError("密钥环已锁定"))
        self.assertEqual(result["openapi"]["credential_provider"], "not_saved")
        self.assertIn("密钥环已锁定", output)
        self.assertNotIn("持久保存已验证", output)

    def test_failed_readback_does_not_report_persistence(self):
        result, output = self.configure("Windows Credential Manager", readback=False)
        self.assertEqual(result["openapi"]["credential_provider"], "not_saved")
        self.assertIn("读回校验失败", output)

    def test_verified_store_reports_actual_provider(self):
        result, output = self.configure("Windows Credential Manager")
        self.assertEqual(result["openapi"]["credential_provider"], "Windows Credential Manager")
        self.assertIn("持久保存已验证", output)

    def test_environment_credentials_can_be_saved_without_repasting(self):
        result, output = self.configure("Windows Credential Manager", use_environment=True)
        self.assertEqual(result["openapi"]["credential_provider"], "Windows Credential Manager")
        self.assertIn("持久保存已验证", output)

    def test_private_key_path_supports_quotes_and_spaces(self):
        self.assertEqual(scnet._private_key_path(' "/example/key with space.txt" '), Path("/example/key with space.txt"))

    def test_private_key_body_and_public_key_are_rejected_without_echo(self):
        for value in ("", "/example/key.pub", "PRIVATE KEY\nprivate-example"):
            with self.assertRaises(scnet.BackendError) as caught:
                scnet._private_key_path(value)
            self.assertNotIn("private-example", str(caught.exception))

    def test_windows_ssh_installer_stops_before_executing_a_shell(self):
        with patch("scnet.platform.system", return_value="Windows"), patch("scnet.subprocess.run") as run:
            with self.assertRaises(scnet.BackendError) as caught:
                scnet._run_setup_ssh("example", "key.txt", "cluster-user")
        self.assertIn("WSL2", str(caught.exception))
        run.assert_not_called()

    def test_adopted_ssh_key_records_the_actual_identity_path(self):
        path = str(ROOT / "does-not-exist/custom-identity")
        metadata = scnet._ssh_key_metadata("example", path, "cluster-user", installed_path=path)
        self.assertEqual(metadata["key_path"], path)

    def test_ssh_g_success_alone_does_not_mean_alias_is_configured(self):
        completed = Mock(returncode=0, stdout="hostname example\nport 22\nuser local-user\n", stderr="")
        with patch("scnet.shutil.which", return_value="ssh"), patch("scnet.subprocess.run", return_value=completed):
            report = scnet.doctor_report("ssh", "example", {"CLUSTER_ID": "example", "SSH_HOST": "cluster.example", "SSH_PORT": "2222"}, {}, no_network=True, timeout=5)
        check = next(item for item in report["checks"] if item["name"] == "ssh_config")
        self.assertFalse(check["ok"])
        self.assertIn("~/.ssh/config", check["detail"])

    def test_nonsecret_configuration_round_trip(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}):
            path = save_user_config({"default_backend": "openapi", "openapi": {"credential_provider": "not_saved"}})
            self.assertEqual(load_user_config()["openapi"]["credential_provider"], "not_saved")
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_local_followup_command_runs_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "Skill space's $name"
            (root / "scripts").mkdir(parents=True)
            (root / "scripts/scnet.py").write_text(
                "import json, sys; print(json.dumps(sys.argv[1:]))", encoding="utf-8"
            )
            with patch("scnet.REPO_ROOT", root):
                command = scnet._local_cli_command("--backend", "openapi", "doctor")
            if platform.system() == "Windows":
                executable = shutil.which("pwsh") or shutil.which("powershell")
                self.assertIsNotNone(executable)
                python_path = sys.executable.replace("'", "''")
                invocation = [executable, "-NoProfile", "-NonInteractive", "-Command", f"Set-Alias python '{python_path}'; {command}"]
            else:
                invocation = shlex.split(command)
                invocation[0] = sys.executable
            completed = subprocess.run(invocation, cwd=directory, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(completed.stdout), ["--backend", "openapi", "doctor"])


@unittest.skipUnless(platform.system() == "Windows", "Windows Credential Manager integration")
class WindowsCredentialTests(unittest.TestCase):
    def test_invalid_saved_encoding_has_a_redacted_recovery_error(self):
        target = "scnet-hpc-test-" + uuid.uuid4().hex
        with patch("scnet_credentials.SERVICE", target):
            try:
                credentials.store_openapi_credentials("example-user", "example-access", "example-secret")
                with patch("ctypes.string_at", return_value=b"\xffprivate-example"):
                    with self.assertRaises(credentials.CredentialError) as caught:
                        credentials.load_secure_credentials()
                self.assertIn("setup modify", str(caught.exception))
                self.assertNotIn("private-example", str(caught.exception))
            finally:
                credentials.delete_openapi_credentials()

    def test_native_store_read_update_delete_with_an_isolated_dummy_target(self):
        target = "scnet-hpc-test-" + uuid.uuid4().hex
        with patch("scnet_credentials.SERVICE", target):
            try:
                self.assertIsNone(credentials.load_secure_credentials())
                self.assertEqual(credentials.store_openapi_credentials("测试-user", "example-access", "example-secret"), "Windows Credential Manager")
                self.assertEqual(credentials.load_secure_credentials()["user"], "测试-user")
                credentials.store_openapi_credentials("updated-user", "example-access", "updated-secret")
                self.assertEqual(credentials.load_secure_credentials()["secret_key"], "updated-secret")
                self.assertEqual(credentials.delete_openapi_credentials(), (True, "Windows Credential Manager"))
                self.assertIsNone(credentials.load_secure_credentials())
                self.assertEqual(credentials.delete_openapi_credentials(), (False, "Windows Credential Manager"))
            finally:
                credentials.delete_openapi_credentials()


if __name__ == "__main__":
    unittest.main()
