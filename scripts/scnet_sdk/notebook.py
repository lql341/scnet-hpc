"""Read-only Notebook domain built on the shared SCNet OpenAPI client."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

from scnet_backends.base import BackendError

from .client import SCNetClient, service_endpoint


SENSITIVE_FIELDS = {
    "sshPassword",
    "password",
    "token",
    "userToken",
}


def _safe_url(value: Any) -> dict[str, Any] | None:
    if not value:
        return None
    split = urlsplit(str(value))
    return {
        "origin": urlunsplit((split.scheme, split.netloc, "", "", "")),
        "path": split.path,
        "credentials_redacted": bool(split.query),
    }


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in SENSITIVE_FIELDS:
                result[key] = "<redacted>" if item else item
            elif key in {"url", "sshUrl", "serviceUrl"}:
                result[key] = _safe_url(item)
            else:
                result[key] = _redact(item)
        return result
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


class NotebookService:
    def __init__(self, client: SCNetClient):
        self.client = client

    def _context(
        self, region: str | None
    ) -> tuple[str, str, dict[str, Any], dict[str, Any]]:
        return self.client.service_context(region, "aiUrls", "ai")

    def regions(self) -> list[dict[str, Any]]:
        result = []
        for region in self.client.regions():
            region_id = str(region.get("clusterId", ""))
            if region_id == "0" or not region.get("token"):
                continue
            try:
                ai_url, _, _, center = self._context(region_id)
            except BackendError:
                continue
            result.append(
                {
                    "region_id": region_id,
                    "name": region.get("clusterName") or center.get("name"),
                    "available": True,
                    "service": "notebook",
                    "endpoint_origin": _safe_url(ai_url),
                }
            )
        return result

    def resources(
        self, region: str, resource_id: str = ""
    ) -> list[dict[str, Any]]:
        _, token, selected, _ = self._context(region)
        params: dict[str, Any] = {
            "clusterIds": str(selected.get("clusterId"))
        }
        if resource_id:
            params["resourceId"] = resource_id
        data = self.client.request(
            "GET",
            "https://www.scnet.cn/ac/openapi/v2/resources/accelerators?"
            + urlencode(params),
            token=token,
        )
        return _redact(data if isinstance(data, list) else [])

    def images(
        self,
        region: str,
        *,
        access: str = "public",
        image_type: str = "",
        accelerator_type: str = "",
        name: str = "",
        start: int = 0,
        limit: int = 20,
    ) -> dict[str, Any]:
        ai_url, token, _, _ = self._context(region)
        body = {
            "access": access,
            "start": start,
            "limit": limit,
            "sort": "DESC",
            "orderBy": "create_time",
            "name": name,
            "type": image_type,
            "acceleratorType": accelerator_type,
        }
        data = self.client.request(
            "POST",
            service_endpoint(
                ai_url, "ai", "/openapi/v2/image/images"
            ),
            token=token,
            json_body=body,
        )
        return _redact(data if isinstance(data, dict) else {"data": data})

    def list_instances(
        self,
        region: str,
        *,
        name: str = "",
        status: str = "",
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        ai_url, token, _, _ = self._context(region)
        params: dict[str, Any] = {"page": page, "size": size}
        if name:
            params["notebookName"] = name
        if status:
            params["notebookStatus"] = status
        data = self.client.request(
            "GET",
            service_endpoint(
                ai_url, "ai", "/openapi/v2/notebook/list"
            )
            + "?"
            + urlencode(params),
            token=token,
        )
        return _redact(data if isinstance(data, dict) else {"records": []})

    def detail(self, region: str, notebook_id: str) -> dict[str, Any]:
        ai_url, token, _, _ = self._context(region)
        data = self.client.request(
            "GET",
            service_endpoint(
                ai_url, "ai", "/openapi/v2/notebook/detail"
            )
            + "?"
            + urlencode({"notebookId": notebook_id}),
            token=token,
        )
        return _redact(data if isinstance(data, dict) else {})

    def url(
        self, region: str, notebook_id: str, *, reveal: bool = False
    ) -> dict[str, Any]:
        ai_url, token, _, _ = self._context(region)
        data = self.client.request(
            "GET",
            service_endpoint(
                ai_url, "ai", "/openapi/v2/notebook/url"
            )
            + "?"
            + urlencode({"notebookId": notebook_id}),
            token=token,
        )
        if not isinstance(data, dict):
            return {}
        return data if reveal else _redact(data)
