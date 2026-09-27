#!/usr/bin/env python3
"""Build site/data/inventory.json from the live sources of truth.

    NetBox   -> hosts, IPs, roles, tags, parents        (required)
    Proxmox  -> lxc vs vm, running/stopped, node         (optional)
    Omada    -> client counts per VLAN                   (optional)
    the_codex checkout -> services per host              (optional)

It never touches policy.json. Anything NetBox disagrees with the policy about
goes into inventory["drift"] and shows on the map as Errata. It does not get
silently "fixed".

Standard library only, so it runs in a bare python:3.12-alpine container.

Environment (see .env.example):
    NETBOX_URL, NETBOX_TOKEN
    PROXMOX_URL, PROXMOX_TOKEN_ID, PROXMOX_TOKEN_SECRET, PROXMOX_VERIFY_TLS=1
    OMADA_URL, OMADA_ID, OMADA_CLIENT_ID, OMADA_CLIENT_SECRET, OMADA_SITE, OMADA_VERIFY_TLS=1

Usage:
    python3 tools/sync.py [--policy site/data/policy.json] [--out site/data/inventory.json]
                          [--codex /path/to/the_codex] [--dry-run]
Exit codes: 0 written or unchanged, 1 NetBox unreachable, 2 bad policy.
"""
from __future__ import annotations

import argparse
import datetime as dt
import ipaddress
import json
import os
import pathlib
import ssl
import sys
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent

# NetBox device-role slug -> map glyph
ROLE_KIND = {
    "hypervisor": "hypervisor",
    "nas": "nas",
    "gateway": "gateway",
    "router": "gateway",
    "switch": "switch",
    "access-point": "ap",
}


# ---------------------------------------------------------------- http helpers
def _ctx(verify: bool) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not verify:  # homelab self-signed certs (Proxmox, Omada); opt-in via env only
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def http_json(url: str, headers: dict | None = None, data: dict | None = None, verify: bool = True, timeout: int = 20):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers={"Accept": "application/json", **(headers or {})})
    if body is not None:
        req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "mappa-sync/1.0")
    try:
        with urllib.request.urlopen(req, context=_ctx(verify), timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:  # surface the server's reason, not just the status
        body = e.read().decode(errors="replace")[:300].replace("\n", " ")
        raise RuntimeError(f"{e.code} {e.reason} from {url.split('?')[0]}: {body}") from None


def env_bool(name: str, default: bool = True) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() not in ("0", "false", "no", "")


# ---------------------------------------------------------------- sources
class Norm:
    def __init__(self, aliases: dict[str, str]):
        self.aliases = {k.lower(): v for k, v in aliases.items()}

    def __call__(self, name: str) -> str:
        s = str(name).lower()
        for suffix in (".sqrd.link", ".local", ".lan"):
            if s.endswith(suffix):
                s = s[: -len(suffix)]
        return self.aliases.get(s, s)


def netbox_all(base: str, token: str, path: str) -> list[dict]:
    out, url = [], f"{base.rstrip('/')}/api/{path}?limit=500"
    # NetBox >= 4.5 v2 tokens ("nbt_<key>.<secret>") use Bearer; legacy v1 tokens use "Token"
    token = token.strip().strip('"\'')
    for prefix in ("Bearer ", "Token "):  # tolerate a scheme pasted into .env
        if token.startswith(prefix):
            token = token[len(prefix):].strip()
    scheme = "Bearer" if token.startswith("nbt_") else "Token"
    hdr = {"Authorization": f"{scheme} {token}"}
    while url:
        page = http_json(url, hdr)
        out += page.get("results", [])
        url = page.get("next")
    return out


def from_netbox(norm: Norm, drift: list) -> tuple[list[dict], set[int]]:
    base, token = os.environ.get("NETBOX_URL"), os.environ.get("NETBOX_TOKEN")
    if not base or not token:
        raise RuntimeError("NETBOX_URL and NETBOX_TOKEN are required")
    devices = netbox_all(base, token, "dcim/devices/")
    vms = netbox_all(base, token, "virtualization/virtual-machines/")
    ips = netbox_all(base, token, "ipam/ip-addresses/")
    vlans = netbox_all(base, token, "ipam/vlans/")

    # every IP assigned to each object, so we can find legacy / secondary addresses
    by_obj: dict[tuple[str, int], list[str]] = {}
    for ip in ips:
        ao = ip.get("assigned_object") or {}
        owner = ao.get("device") or ao.get("virtual_machine")
        if not owner:
            continue
        kind = "device" if ao.get("device") else "vm"
        by_obj.setdefault((kind, owner["id"]), []).append(ip["address"].split("/")[0])

    hosts = []

    def mk(obj: dict, kind_key: str, kind: str) -> dict:
        name = norm(obj["name"])
        primary = ((obj.get("primary_ip4") or {}).get("address") or "").split("/")[0] or None
        all_ips = by_obj.get((kind_key, obj["id"]), [])
        if not primary and all_ips:
            drift.append({"severity": "warn", "object": name, "message": f"No primary IPv4 in NetBox. Using {all_ips[0]}."})
            primary = all_ips[0]
        if not primary:
            drift.append({"severity": "warn", "object": name, "message": "No IP address in NetBox at all."})
        h = {
            "id": name,
            "ip": primary,
            "kind": kind,
            "role": obj.get("description") or ((obj.get("role") or {}).get("name")) or None,
            "status": (obj.get("status") or {}).get("value"),
            "tags": sorted(t["slug"] for t in obj.get("tags") or []),
            "netbox_id": obj["id"],
            "netbox_name": obj["name"],
        }
        legacy = [i for i in all_ips if i != primary]
        if legacy:
            h["legacy_ips"] = legacy
        return h

    for d in devices:
        role = ((d.get("role") or d.get("device_role") or {}).get("slug")) or ""
        h = mk(d, "device", ROLE_KIND.get(role, "device"))
        model = (d.get("device_type") or {}).get("model")
        if model and model.lower() != h["id"]:
            h["model"] = model
        hosts.append(h)
    for v in vms:
        h = mk(v, "vm", "vm")
        parent = (v.get("device") or {}).get("name")
        if parent:
            h["parent"] = norm(parent)
        hosts.append(h)

    for h in hosts:
        if h["netbox_name"].lower().replace(".sqrd.link", "") != h["id"]:
            drift.append({"severity": "info", "object": h["id"], "message": f"NetBox calls it {h['netbox_name']}, mapped through policy.aliases."})
        del h["netbox_name"]
    return hosts, {v["vid"] for v in vlans}


def from_proxmox(hosts: list[dict], norm: Norm, drift: list, expect_missing: set[str]) -> bool:
    url, tid, sec = (os.environ.get(k) for k in ("PROXMOX_URL", "PROXMOX_TOKEN_ID", "PROXMOX_TOKEN_SECRET"))
    if not (url and tid and sec):
        return False
    res = http_json(
        f"{url.rstrip('/')}/api2/json/cluster/resources?type=vm",
        {"Authorization": f"PVEAPIToken={tid}={sec}"},
        verify=env_bool("PROXMOX_VERIFY_TLS"),
    )["data"]
    by = {norm(r["name"]): r for r in res if not r.get("template")}
    seen = set()
    for h in hosts:
        r = by.get(h["id"])
        if not r:
            if h["kind"] == "vm" and h["id"] not in expect_missing:
                drift.append({"severity": "info", "object": h["id"], "message": "VM in NetBox, not found in Proxmox."})
            continue
        seen.add(h["id"])
        h["kind"] = "lxc" if r["type"] == "lxc" else "vm"
        h["status"] = r.get("status", h.get("status"))
        h.setdefault("parent", norm(r["node"]))
        h["vmid"] = r.get("vmid")
    for name in sorted(set(by) - seen):
        drift.append({"severity": "warn", "object": name, "message": f"Guest {by[name]['vmid']} runs in Proxmox but is not in NetBox."})
    return True


def from_omada(policy: dict, drift: list) -> dict[str, int] | None:
    url, oid, cid, sec = (os.environ.get(k) for k in ("OMADA_URL", "OMADA_ID", "OMADA_CLIENT_ID", "OMADA_CLIENT_SECRET"))
    if not (url and oid and cid and sec):
        return None
    verify, base = env_bool("OMADA_VERIFY_TLS"), url.rstrip("/")
    try:
        resp = http_json(
            f"{base}/openapi/authorize/token?grant_type=client_credentials",
            data={"omadacId": oid, "client_id": cid, "client_secret": sec},
            verify=verify,
)
        if resp.get("errorCode") not in (0, None) or "result" not in resp:
            raise RuntimeError(f"token request refused: errorCode {resp.get('errorCode')}, {resp.get('msg')}")
        tok = resp["result"]["accessToken"]
        hdr = {"Authorization": f"AccessToken={tok}"}
        sites = http_json(f"{base}/openapi/v1/{oid}/sites?page=1&pageSize=100", hdr, verify=verify)["result"]["data"]
        want = os.environ.get("OMADA_SITE")
        site = next((s for s in sites if not want or s["name"] == want), None)
        if not site:
            raise RuntimeError(f"site {want!r} not found")
        clients = http_json(f"{base}/openapi/v1/{oid}/sites/{site['siteId']}/clients?page=1&pageSize=1000", hdr, verify=verify)["result"]["data"]
    except Exception as e:  # Omada is enrichment only; never fail the sync over it
        drift.append({"severity": "info", "object": "omada", "message": f"Client counts unavailable: {e}"})
        return None
    nets = [(v["id"], ipaddress.ip_network(v["subnet"])) for v in policy["vlans"]]
    counts: dict[str, int] = {}
    for c in clients:
        try:
            ip = ipaddress.ip_address(c.get("ip") or "")
        except ValueError:
            continue
        for vid, net in nets:
            if ip in net:
                counts[vid] = counts.get(vid, 0) + 1
    return counts


def from_codex(hosts: list[dict], codex: pathlib.Path | None) -> bool:
    """hosts/<host>/<app>/docker-compose.yml in the_codex -> services on that host."""
    if not codex or not (codex / "hosts").is_dir():
        return False
    by = {h["id"]: h for h in hosts}
    for hdir in (codex / "hosts").iterdir():
        h = by.get(hdir.name)
        if not h or not hdir.is_dir():
            continue
        apps = sorted(p.parent.name for p in hdir.glob("*/docker-compose.y*ml"))
        if apps:
            h["services"] = apps
    return True


# ---------------------------------------------------------------- checks
def check_policy(policy: dict, hosts: list[dict], nb_vids: set[int] | None, drift: list, norm: Norm) -> None:
    nets = [(v["id"], ipaddress.ip_network(v["subnet"])) for v in policy["vlans"]]
    gw = norm(policy.get("gateway", {}).get("id", ""))
    for h in hosts:
        if h["id"] == gw or not h.get("ip"):
            continue
        ip = ipaddress.ip_address(h["ip"])
        if not any(ip in n for _, n in nets):
            drift.append({"severity": "warn", "object": h["id"], "message": f"{h['ip']} is in no VLAN the policy knows. It won't be drawn."})
    if nb_vids is not None:
        missing = [f"{v['name']} ({v['vid']})" for v in policy["vlans"] if v["vid"] not in nb_vids]
        if missing:
            drift.append({"severity": "warn", "object": "netbox:vlans", "message": "Missing from NetBox: " + ", ".join(missing) + "."})
    by_id = {h["id"]: h for h in hosts}
    for hid, want in policy.get("expect", {}).get("vlan", {}).items():
        h = by_id.get(norm(hid))
        if not h or not h.get("ip"):
            continue
        got = next((vid for vid, n in nets if ipaddress.ip_address(h["ip"]) in n), None)
        if got != want:
            drift.append({"severity": "warn", "object": h["id"], "message": f"NetBox primary IP {h['ip']} puts it in {got or 'no VLAN'}, policy expects {want}."})
    allowed = set(policy.get("expect", {}).get("no_ansible", []))
    for h in hosts:
        if "no_ansible" in h.get("tags", []) and h["id"] not in allowed:
            drift.append({"severity": "warn", "object": h["id"], "message": "Tagged no_ansible in NetBox, but policy.expect.no_ansible doesn't list it. Bulk playbooks will skip it."})
    ids = {h["id"] for h in hosts}
    refs = []
    for r in policy.get("acl", {}).get("rules", []):
        refs += [t[5:] for t in r["from"] + r["to"] if t.startswith("host:")]
    refs += [d["target"][5:] for d in policy.get("dns", []) if d.get("target", "").startswith("host:")]
    refs += list(policy.get("host_overrides", {}))
    for ref in sorted(set(norm(x) for x in refs) - ids - {gw}):
        drift.append({"severity": "warn", "object": ref, "message": "Named in policy.json, but no such host in the inventory."})


# ---------------------------------------------------------------- main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--policy", default=str(ROOT / "site/data/policy.json"))
    ap.add_argument("--out", default=str(ROOT / "site/data/inventory.json"))
    ap.add_argument("--codex", default=os.environ.get("CODEX_PATH"))
    ap.add_argument("--dry-run", action="store_true", help="print, don't write")
    a = ap.parse_args()

    try:
        policy = json.loads(pathlib.Path(a.policy).read_text())
    except Exception as e:
        print(f"policy unreadable: {e}", file=sys.stderr)
        return 2
    norm = Norm(policy.get("aliases", {}))
    drift: list[dict] = []
    sources = {"netbox": False, "proxmox": False, "omada": False, "codex": False}

    try:
        hosts, nb_vids = from_netbox(norm, drift)
        sources["netbox"] = True
    except Exception as e:
        print(f"NetBox failed, keeping the old inventory: {e}", file=sys.stderr)
        return 1

    expect = policy.get("expect", {})
    try:
        sources["proxmox"] = from_proxmox(hosts, norm, drift, set(expect.get("not_in_proxmox", [])))
    except Exception as e:
        drift.append({"severity": "info", "object": "proxmox", "message": f"Unavailable: {e}"})
    counts = from_omada(policy, drift)
    sources["omada"] = counts is not None
    sources["codex"] = from_codex(hosts, pathlib.Path(a.codex) if a.codex else None)
    check_policy(policy, hosts, nb_vids, drift, norm)

    clients = [
        {"id": f"{v['id']}-devices", "vlan": v["id"], "label": v["clients"], "count": (counts or {}).get(v["id"])}
        for v in policy["vlans"]
        if v.get("clients")
    ]
    hosts.sort(key=lambda h: h["id"])
    inv = {
        "$schema": "../../schema/inventory.schema.json",
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "generator": "tools/sync.py (" + ", ".join(k for k, v in sources.items() if v) + ")",
        "sources": sources,
        "hosts": hosts,
        "clients": clients,
        "drift": drift,
    }

    out = pathlib.Path(a.out)
    text = json.dumps(inv, indent=2, ensure_ascii=False) + "\n"
    if a.dry_run:
        print(text)
        return 0
    # only rewrite when something other than the timestamp changed, so git history stays meaningful
    if out.exists():
        try:
            old = json.loads(out.read_text())
            if {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in inv.items() if k != "generated_at"}:
                print("inventory unchanged")
                return 0
        except json.JSONDecodeError:
            pass
    tmp = out.with_suffix(".tmp")
    tmp.write_text(text)
    tmp.replace(out)
    print(f"wrote {out}: {len(hosts)} hosts, {len(drift)} drift notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
