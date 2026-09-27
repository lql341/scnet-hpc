#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scnet_backends import BackendContext  # noqa: E402
from scnet_backends.external import ExternalBackend  # noqa: E402
from scnet_backends.openapi import (  # noqa: E402
    OpenAPIBackend,
    canonical_signature,
    normalize_job,
    service_endpoint,
)
from scnet_backends.profile import list_profiles, parse_profile  # noqa: E402
from scnet import _parse_multi_numbers  # noqa: E402
from scnet_config import (  # noqa: E402
    config_path,
    load_user_config,
    reset_all_metadata,
    reset_openapi_metadata,
    reset_ssh_metadata,
    save_user_config,
)


class ProfileTests(unittest.TestCase):
    def test_repository_profiles_parse(self):
        profiles = list_profiles(REPO_ROOT)
        self.assertGreaterEqual(len(profiles), 1)
        self.assertTrue(all(item["cluster_id"] for item in profiles))

    def test_multiline_profile_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.conf"
            path.write_text(
                'CLUSTER_ID="demo"\nKNOWN_LIMITATIONS="first;\\\nsecond"\n',
                encoding="utf-8",
            )
            profile = parse_profile(path)
        self.assertEqual(profile["KNOWN_LIMITATIONS"], "first;second")


class SkillContextBudgetTests(unittest.TestCase):
    def test_entrypoint_stays_within_context_budget(self):
        text = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(
            len(text.encode("utf-8")),
            5000,
            "move conditional detail from SKILL.md into a routed reference",
        )
        frontmatter = text.split("---", 2)[1]
        description = next(
            line.split(":", 1)[1].strip()
            for line in frontmatter.splitlines()
            if line.startswith("description:")
        )
        self.assertLessEqual(
            len(description.split()),
            35,
            "keep skill discovery metadata concise and discriminating",
        )


class UserConfigTests(unittest.TestCase):
    def test_user_config_is_private_and_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}, clear=False):
                path = save_user_config(
                    {
                        "version": 1,
                        "cluster": "demo",
                        "default_backend": "ssh",
                        "ssh": {
                            "clusters": {
                                "demo": {
                                    "username": "alice",
                                    "key_expires_at": "2026-10-29",
                                }
                            }
                        },
                        "openapi": {
                            "regions": {
                                "11112": {"name": "Kunshan", "available": True}
                            }
                        },
                    }
                )
                self.assertEqual(path, config_path())
                self.assertEqual(load_user_config()["cluster"], "demo")
                merged = load_user_config()
                self.assertEqual(
                    merged["ssh"]["clusters"]["demo"]["username"], "alice"
                )
                self.assertEqual(
                    merged["openapi"]["regions"]["11112"]["name"], "Kunshan"
                )
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_scoped_and_full_metadata_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": directory}, clear=False):
                save_user_config(
                    {
                        "version": 1,
                        "cluster": "demo",
                        "default_backend": "openapi",
                        "ssh": {"clusters": {"demo": {"username": "alice"}}},
                        "openapi": {"default_region_id": "11250"},
                    }
                )
                self.assertTrue(reset_openapi_metadata())
                self.assertNotIn("openapi", load_user_config())
                self.assertTrue(reset_ssh_metadata("demo"))
                self.assertEqual(load_user_config()["ssh"]["clusters"], {})
                removed = reset_all_metadata()
                self.assertTrue(removed)
                self.assertFalse(config_path().exists())


class SelectionTests(unittest.TestCase):
    def test_multi_number_ranges(self):
        self.assertEqual(
            _parse_multi_numbers("1,3,5-7", 8),
            {0, 2, 4, 5, 6},
        )

    def test_multi_number_rejects_empty_or_out_of_range(self):
        with self.assertRaises(ValueError):
            _parse_multi_numbers("", 3)
        with self.assertRaises(ValueError):
            _parse_multi_numbers("4", 3)


class OpenAPIHelperTests(unittest.TestCase):
    def test_signature_matches_documented_algorithm(self):
        message = (
            '{"accessKey":"ak","timestamp":"1764597591","user":"alice"}'
        )
        expected = hmac.new(
            b"secret", message.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        self.assertEqual(
            canonical_signature("ak", "1764597591", "alice", "secret"),
            expected,
        )

    def test_service_endpoint_avoids_duplicate_service_segment(self):
        self.assertEqual(
            service_endpoint(
                "https://example.test/hpc", "hpc", "/openapi/v2/cluster"
            ),
            "https://example.test/hpc/openapi/v2/cluster",
        )
        self.assertEqual(
            service_endpoint(
                "https://example.test", "hpc", "/openapi/v2/cluster"
            ),
            "https://example.test/hpc/openapi/v2/cluster",
        )

    def test_job_normalization_is_compact(self):
        result = normalize_job(
            {
                "jobId": "42",
                "jobName": "probe",
                "jobStatus": "statR",
                "queue": "debug",
                "jobRunTime": "00:00:03",
                "jobInitAttr": {"large": "backend-specific data"},
            }
        )
        self.assertEqual(result["state"], "RUNNING")
        self.assertEqual(result["job_id"], "42")
        self.assertNotIn("jobInitAttr", result)


class FakeOpenAPIBackend(OpenAPIBackend):
    def __init__(self, context):
        super().__init__(context)
        self.requests = []
        self.response = None

    def _hpc_context(self, options):
        return (
            "https://example.test/hpc",
            "redacted-token",
            "123",
            "alice",
            {"clusterId": "456"},
        )

    def _json_request(self, method, url, **kwargs):
        self.requests.append((method, url, kwargs))
        return self.response


class OpenAPIOperationTests(unittest.TestCase):
    def setUp(self):
        context = BackendContext(
            repo_root=REPO_ROOT,
            profile_name=None,
            profile={},
            timeout=5,
        )
        self.backend = FakeOpenAPIBackend(context)

    def test_queue_response_is_normalized(self):
        self.backend.response = [
            {
                "queueName": "debug",
                "queNodes": "2",
                "queFreeNodes": "1",
                "queMaxDcuPN": "4",
            }
        ]
        result = self.backend.execute("queues", {})
        self.assertEqual(result[0]["partition"], "debug")
        self.assertEqual(result[0]["free_nodes"], "1")
        self.assertEqual(result[0]["max_dcus_per_node"], "4")
        self.assertNotIn("token", json.dumps(result))

    def test_submit_uses_documented_basic_command_shape(self):
        self.backend.response = "148"
        result = self.backend.execute(
            "submit",
            {
                "name": "probe",
                "command": "python3 probe.py",
                "work_dir": "/public/home/alice/probe",
                "queue": "debug",
                "nodes": 1,
                "cpus": 8,
                "dcus": 1,
                "scheduler_options": ["#SBATCH --account=test"],
            },
        )
        self.assertEqual(result, {"job_id": "148"})
        method, url, request = self.backend.requests[-1]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith("/hpc/openapi/v2/apptemplates/BASIC/BASE/job"))
        body = request["json_body"]["mapAppJobInfo"]
        self.assertEqual(body["GAP_NDCU"], "1")
        self.assertEqual(body["GAP_SCHEDULER_OPT_WEB"], "#SBATCH --account=test")
        self.assertNotIn("redacted-token", json.dumps(request["json_body"]))

    def test_preview_submit_does_not_resolve_region(self):
        preview = self.backend.preview(
            "submit",
            {
                "name": "probe",
                "command": "echo hello",
                "work_dir": "/public/home/alice/probe",
                "queue": "debug",
                "nodes": 1,
                "cpus": 1,
                "gpus": 0,
                "dcus": 1,
                "walltime": "00:05:00",
                "scheduler_options": [],
            },
        )
        self.assertTrue(preview["requires_network_resolution"])
        self.assertNotIn("redacted-token", json.dumps(preview))
        self.assertEqual(self.backend.requests, [])

    def test_raw_queue_output_preserves_compact_and_raw_forms(self):
        self.backend.response = [
            {"queueName": "debug", "queNodes": "2", "queFreeNodes": "1"}
        ]
        result = self.backend.execute("queues", {"raw": True})
        self.assertEqual(result["items"][0]["partition"], "debug")
        self.assertEqual(result["raw"][0]["queueName"], "debug")

    def test_raw_region_output_redacts_tokens(self):
        self.backend._regions = lambda: [
            {
                "clusterId": "456",
                "clusterName": "test-region",
                "token": "should-not-leak",
            }
        ]
        result = self.backend.execute("clusters", {"raw": True})
        self.assertEqual(result["items"][0]["region_id"], "456")
        self.assertEqual(result["raw"][0]["token"], "<redacted>")
        self.assertNotIn("should-not-leak", json.dumps(result))

    def test_chunked_upload_reads_one_chunk_at_a_time(self):
        self.backend._efile_context = lambda options: (
            "https://example.test/efile",
            "redacted-token",
            {},
        )
        chunks = []
        self.backend._multipart_request = (
            lambda url, token, fields, file_name, file_bytes, content_type: chunks.append(
                (url, fields, len(file_bytes))
            )
        )
        self.backend._json_request = lambda method, url, **kwargs: {
            "merged": True
        }
        with tempfile.NamedTemporaryFile() as file:
            file.write(b"x" * (2 * 1024 * 1024 + 17))
            file.flush()
            result = self.backend.execute(
                "upload",
                {
                    "local_path": file.name,
                    "remote_path": "/public/home/alice",
                    "chunk_size": 1024 * 1024,
                },
            )
        self.assertEqual(len(chunks), 3)
        self.assertEqual([item[2] for item in chunks], [1024 * 1024, 1024 * 1024, 17])
        self.assertEqual(result["chunks"], 3)

    def test_mkdir_preview_defaults_to_not_creating_parents(self):
        preview = self.backend.preview("mkdir", {"path": "/public/home/alice/work"})
        self.assertFalse(preview["parents"])

    def test_discovery_skips_regions_without_hpc_service(self):
        regions = [
            {"clusterId": "model", "clusterName": "Model", "token": "one"},
            {"clusterId": "hpc", "clusterName": "HPC", "token": "two"},
        ]
        self.backend._regions = lambda: regions

        def request(method, url, **kwargs):
            token = kwargs.get("token")
            if url.endswith("/center") and token == "one":
                return {"clusterUserInfo": {"userName": "alice"}}
            if url.endswith("/center") and token == "two":
                return {
                    "clusterUserInfo": {
                        "userName": "alice",
                        "homePath": "/public/home/alice",
                    },
                    "hpcUrls": [
                        {"enable": "true", "url": "https://example.test/hpc"}
                    ],
                }
            if url.endswith("/hpc/openapi/v2/cluster"):
                return [{"id": 123, "text": "slurm", "JobManagerType": "SLURM"}]
            raise AssertionError((method, url, kwargs))

        self.backend._json_request = request
        contexts = self.backend.discover_all_region_contexts()
        self.assertEqual([item["region_id"] for item in contexts], ["hpc"])


class FakeHTTPResponse:
    def __init__(self, data):
        self._body = json.dumps(
            {"code": "0", "msg": "success", "data": data}
        ).encode()
        self.headers = {"Content-Type": "application/json"}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self._body


class OpenAPIHTTPFlowTests(unittest.TestCase):
    def test_auth_center_scheduler_and_queue_flow(self):
        base = "https://mock.scnet.test"
        context = BackendContext(
            repo_root=REPO_ROOT,
            profile_name=None,
            profile={},
            timeout=5,
        )

        def fake_urlopen(request, timeout):
            self.assertEqual(timeout, 5)
            if request.full_url == base + "/api/user/v3/tokens":
                return FakeHTTPResponse(
                    [
                        {
                            "clusterId": "456",
                            "clusterName": "test-region",
                            "token": "region-token",
                        }
                    ]
                )
            if request.full_url == base + "/center":
                return FakeHTTPResponse(
                    {
                        "clusterUserInfo": {
                            "userName": "alice",
                            "homePath": "/public/home/alice",
                        },
                        "hpcUrls": [{"enable": "true", "url": base + "/hpc"}],
                        "efileUrls": [{"enable": "true", "url": base + "/efile"}],
                    }
                )
            if request.full_url == base + "/hpc/openapi/v2/cluster":
                return FakeHTTPResponse(
                    [{"id": 123, "text": "slurm", "JobManagerType": "SLURM"}]
                )
            if request.full_url.startswith(
                base
                + "/hpc/openapi/v2/queuenames/users/alice?strJobManagerID=123"
            ):
                return FakeHTTPResponse(
                    [
                        {
                            "queueName": "debug",
                            "queNodes": "2",
                            "queFreeNodes": "1",
                        }
                    ]
                )
            raise AssertionError(f"unexpected URL: {request.full_url}")

        with patch.dict(
            os.environ,
            {
                "SCNET_OPENAPI_USER": "alice",
                "SCNET_OPENAPI_ACCESS_KEY": "ak",
                "SCNET_OPENAPI_SECRET_KEY": "secret",
                "SCNET_OPENAPI_AUTH_BASE": base,
                "SCNET_OPENAPI_CENTER_URL": base + "/center",
            },
            clear=False,
        ), patch("scnet_backends.openapi.urlopen", side_effect=fake_urlopen):
            backend = OpenAPIBackend(context)
            result = backend.execute("queues", {"region": "456"})
        self.assertEqual(result[0]["partition"], "debug")
        self.assertEqual(result[0]["free_nodes"], "1")


class ExternalBackendTests(unittest.TestCase):
    def test_protocol_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "scnet-hpc-backend-demo"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import json, sys\n"
                "request = json.load(sys.stdin)\n"
                "if request['operation'] == 'capabilities':\n"
                "    data = {'capabilities': ['clusters']}\n"
                "else:\n"
                "    data = [{'name': 'external-demo'}]\n"
                "json.dump({'ok': True, 'protocol_version': 1, 'data': data}, sys.stdout)\n",
                encoding="utf-8",
            )
            executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
            context = BackendContext(
                repo_root=REPO_ROOT,
                profile_name=None,
                profile={},
                timeout=5,
            )
            backend = ExternalBackend(context, "demo", str(executable))
            result = backend.execute("clusters", {})
        self.assertEqual(result, [{"name": "external-demo"}])


if __name__ == "__main__":
    unittest.main()
