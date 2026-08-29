"""guardiactl: ver y operar la infra minima del sistema de incidentes.

Habla HTTP con la API (`/infra/...`); nunca toca GCP/Cloudflare directamente.
Las mutaciones (vm start, dns restore) exigen --confirm.
"""
import argparse
import os
import sys
from typing import Any

import httpx

API_URL = os.environ.get("GUARDIACTL_API_URL", "http://localhost:8000")


def _get(path: str) -> dict[str, Any]:
    resp = httpx.get(f"{API_URL}{path}", timeout=10)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = httpx.post(f"{API_URL}{path}", json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


def cmd_vm_status(args: argparse.Namespace) -> int:
    data = _get("/infra/vm/status")
    print(f"{data['instance']}: {data['status']}")
    return 0


def cmd_vm_start(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("vm start es una mutacion: se requiere --confirm", file=sys.stderr)
        return 1
    data = _post("/infra/vm/start", {"confirm": True})
    print(f"{data['instance']}: {data['status']}")
    return 0


def cmd_dns_get(args: argparse.Namespace) -> int:
    data = _get("/infra/dns")
    for record in data["records"]:
        print(f"{record['name']} {record['type']} {record['content']}")
    return 0


def cmd_dns_restore(args: argparse.Namespace) -> int:
    if not args.confirm:
        print("dns restore es una mutacion: se requiere --confirm", file=sys.stderr)
        return 1
    data = _post("/infra/dns/restore", {"confirm": True})
    print(f"restored={data['restored']} created={data['created']} unchanged={data['unchanged']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="guardiactl")
    sub = parser.add_subparsers(dest="resource", required=True)

    vm = sub.add_parser("vm")
    vm_sub = vm.add_subparsers(dest="action", required=True)
    vm_sub.add_parser("status").set_defaults(func=cmd_vm_status)
    vm_start = vm_sub.add_parser("start")
    vm_start.add_argument("--confirm", action="store_true")
    vm_start.set_defaults(func=cmd_vm_start)

    dns = sub.add_parser("dns")
    dns_sub = dns.add_subparsers(dest="action", required=True)
    dns_sub.add_parser("get").set_defaults(func=cmd_dns_get)
    dns_restore = dns_sub.add_parser("restore")
    dns_restore.add_argument("--confirm", action="store_true")
    dns_restore.set_defaults(func=cmd_dns_restore)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except httpx.HTTPStatusError as exc:
        try:
            detail = exc.response.json().get("detail", exc.response.text)
        except ValueError:
            detail = exc.response.text
        print(f"la API respondio {exc.response.status_code}: {detail}", file=sys.stderr)
        return 1
    except httpx.HTTPError as exc:
        print(f"no se pudo conectar a la API en {API_URL}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
