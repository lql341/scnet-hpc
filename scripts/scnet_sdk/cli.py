"""CLI adapter for the internal SCNet service client."""

from __future__ import annotations

import argparse
from typing import Any, Mapping

from scnet_backends.base import BackendContext, BackendError

from .client import SCNetClient
from .notebook import NotebookService


def add_notebook_parser(subparsers: Any) -> None:
    notebook = subparsers.add_parser(
        "notebook", help="inspect SCNet Notebook resources and instances"
    )
    notebook.add_argument(
        "--region",
        default=argparse.SUPPRESS,
        help="region name or ID; otherwise use the saved Notebook default",
    )
    commands = notebook.add_subparsers(
        dest="notebook_operation", required=True
    )
    regions = commands.add_parser("regions", help="list Notebook-capable regions")

    resources = commands.add_parser(
        "resources", help="list Notebook accelerator resources"
    )
    resources.add_argument("--region", default=argparse.SUPPRESS)
    resources.add_argument("--resource-id", default="")

    images = commands.add_parser("images", help="list Notebook images")
    images.add_argument("--region", default=argparse.SUPPRESS)
    images.add_argument("--access", choices=("public", "private"), default="public")
    images.add_argument("--type", dest="image_type", default="")
    images.add_argument("--accelerator-type", default="")
    images.add_argument("--name", default="")
    images.add_argument("--start", type=int, default=0)
    images.add_argument("--limit", type=int, default=20)

    listing = commands.add_parser("list", help="list Notebook instances")
    listing.add_argument("--region", default=argparse.SUPPRESS)
    listing.add_argument("--name", default="")
    listing.add_argument("--status", default="")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--size", type=int, default=20)

    show = commands.add_parser("show", help="show one Notebook instance")
    show.add_argument("--region", default=argparse.SUPPRESS)
    show.add_argument("notebook_id")

    url = commands.add_parser("url", help="show the Jupyter access status")
    url.add_argument("--region", default=argparse.SUPPRESS)
    url.add_argument("notebook_id")
    url.add_argument(
        "--reveal",
        action="store_true",
        help="include the sensitive URL with embedded credentials",
    )


def _default_region(
    args: argparse.Namespace, config: Mapping[str, Any]
) -> str:
    region = getattr(args, "region", None)
    if region:
        return str(region)
    openapi = config.get("openapi")
    if isinstance(openapi, dict):
        value = (
            openapi.get("default_notebook_region_id")
            or openapi.get("default_region_id")
            or openapi.get("region_id")
        )
        if value:
            return str(value)
    raise BackendError(
        "Notebook region is not configured; run `notebook regions` "
        "or pass --region"
    )


def execute_notebook(
    args: argparse.Namespace,
    context: BackendContext,
    config: Mapping[str, Any],
) -> Any:
    service = NotebookService(SCNetClient(context))
    operation = args.notebook_operation
    if operation == "regions":
        return service.regions()
    region = _default_region(args, config)
    if operation == "resources":
        return service.resources(region, args.resource_id)
    if operation == "images":
        return service.images(
            region,
            access=args.access,
            image_type=args.image_type,
            accelerator_type=args.accelerator_type,
            name=args.name,
            start=args.start,
            limit=args.limit,
        )
    if operation == "list":
        return service.list_instances(
            region,
            name=args.name,
            status=args.status,
            page=args.page,
            size=args.size,
        )
    if operation == "show":
        return service.detail(region, args.notebook_id)
    if operation == "url":
        return service.url(
            region, args.notebook_id, reveal=args.reveal
        )
    raise BackendError(f"unsupported Notebook operation: {operation}")
