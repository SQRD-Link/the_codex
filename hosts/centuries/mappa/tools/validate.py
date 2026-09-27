#!/usr/bin/env python3
"""Check policy.json + inventory.json before anything ships.

Run it after every edit (agents: always). Exit 0 = fine, 1 = errors.

    python3 tools/validate.py

1. JSON Schema (uses the `jsonschema` package if installed, otherwise skipped with a notice)
2. Referential integrity: every vlan:/host: reference points at something real
3. Sanity: unique ids, overlapping subnets, ACL shadowing (a rule that can never match)
"""
from __future__ import annotations

import ipaddress
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
POLICY = ROOT / "site/data/policy.json"
INVENTORY = ROOT / "site/data/inventory.json"


def main() -> int:
    errors: list[str] = []
    warns: list[str] = []
    policy = json.loads(POLICY.read_text())
    inv = json.loads(INVENTORY.read_text())

    try:
        import jsonschema  # type: ignore

        for doc, name in ((policy, "policy"), (inv, "inventory")):
            schema = json.loads((ROOT / f"schema/{name}.schema.json").read_text())
            for e in jsonschema.Draft202012Validator(schema).iter_errors(doc):
                errors.append(f"{name}: {'/'.join(map(str, e.path)) or '(root)'}: {e.message}")
    except ImportError:
        warns.append("jsonschema not installed; schema check skipped (pip install jsonschema)")

    aliases = {k.lower(): v for k, v in policy.get("aliases", {}).items()}

    def norm(x: str) -> str:
        s = x.lower().removesuffix(".sqrd.link")
        return aliases.get(s, s)

    vlans = {v["id"]: v for v in policy["vlans"]}
    hosts = {norm(h["id"]) for h in inv.get("hosts", [])}
    gw = norm(policy["gateway"]["id"])

    # unique ids and non-overlapping subnets
    ids = [v["id"] for v in policy["vlans"]]
    if len(ids) != len(set(ids)):
        errors.append("duplicate vlan id")
    vids = [v["vid"] for v in policy["vlans"]]
    if len(vids) != len(set(vids)):
        errors.append("duplicate VLAN vid")
    nets = [(v["id"], ipaddress.ip_network(v["subnet"])) for v in policy["vlans"]]
    for i, (a, na) in enumerate(nets):
        for b, nb in nets[i + 1:]:
            if na.overlaps(nb):
                errors.append(f"subnets of {a} and {b} overlap")

    def check_ref(ref: str, where: str) -> None:
        kind, _, val = ref.partition(":")
        if kind == "vlan" and val not in vlans:
            errors.append(f"{where}: unknown vlan '{val}'")
        elif kind == "host" and norm(val) not in hosts and norm(val) != gw:
            errors.append(f"{where}: unknown host '{val}' (not in inventory.json, and no alias)")
        elif kind == "edge" and val not in (policy.get("edge") or {}):
            errors.append(f"{where}: unknown edge '{val}'")

    rules = policy["acl"]["rules"]
    for r in rules:
        for t in r["from"] + r["to"]:
            check_ref(t, f"acl {r['id']}")
    rids = [r["id"] for r in rules]
    if len(rids) != len(set(rids)):
        errors.append("duplicate acl rule id")
    for d in policy.get("dns", []):
        check_ref(d["target"], f"dns {d['record']}")
    for p in (policy.get("edge") or {}).get("port_forwards", []):
        check_ref(p["to"], "port_forward")
    ts = policy.get("tailscale")
    if ts:
        check_ref("host:" + ts["host"], "tailscale.host")
        for v in ts.get("routes", []):
            check_ref("vlan:" + v, "tailscale.routes")
        routed = {v for v in vlans if vlans[v].get("tailscale")}
        if routed != set(ts.get("routes", [])):
            warns.append(f"tailscale.routes {sorted(ts.get('routes', []))} != vlans marked tailscale {sorted(routed)}")
    for hid, ov in policy.get("host_overrides", {}).items():
        if norm(hid) not in hosts:
            warns.append(f"host_overrides.{hid}: no such host in inventory (stale override?)")
        if "lean" in ov and ov["lean"] not in vlans:
            errors.append(f"host_overrides.{hid}.lean: unknown vlan '{ov['lean']}'")

    # shadowing: a later rule fully covered by an earlier one with the same scope never fires
    def covers(a: dict, b: dict) -> bool:
        return set(b["from"]) <= set(a["from"]) and set(b["to"]) <= set(a["to"]) and (not a.get("ports") or set(b.get("ports") or [0]) <= set(a["ports"]))

    for i, r in enumerate(rules):
        for earlier in rules[:i]:
            if covers(earlier, r):
                warns.append(f"acl {r['id']} is shadowed by {earlier['id']} and can never match")

    unverified = [r["id"] for r in rules if r.get("verified") is False]
    if unverified:
        warns.append("unverified ACL rules: " + ", ".join(unverified))

    for w in warns:
        print("warn :", w)
    for e in errors:
        print("ERROR:", e)
    print(f"{'FAIL' if errors else 'ok'}: {len(policy['vlans'])} vlans, {len(hosts)} hosts, {len(rules)} rules, {len(errors)} errors, {len(warns)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
