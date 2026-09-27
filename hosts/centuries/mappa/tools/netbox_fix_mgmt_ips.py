#!/usr/bin/env python3
"""One-off: bring NetBox in line with the VLAN migration (2026-09).

Idempotent, and a dry run by default. Nothing changes until you pass --apply.

    export NETBOX_URL=https://netbox.sqrd.link NETBOX_TOKEN=<write token>
    python3 netbox_fix_mgmt_ips.py            # shows what it would do
    python3 netbox_fix_mgmt_ips.py --apply    # does it

What it does:
  switch, beneden, boven  move their existing IP to Management (same object, so the primary flag stays)
  nastradamus             add 10.10.10.20 on eth0 as primary, keep 10.10.100.12 labelled legacy
  centuries               make the existing 10.10.100.75 its primary
  pbs                     create vm interface eth0 plus 10.10.10.30, make it primary
Standard library only.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("NETBOX_URL", "https://netbox.sqrd.link").rstrip("/")
TOKEN = os.environ.get("NETBOX_TOKEN")
APPLY = "--apply" in sys.argv

MOVES = [  # (device, old address, new address)
    ("switch", "10.10.100.250/24", "10.10.10.201/24"),
    ("beneden", "10.10.100.90/24", "10.10.10.202/24"),
    ("boven", "10.10.100.91/24", "10.10.10.203/24"),
]
LEGACY = "legacy Servers interface, not yet retired"


def api(method, path, body=None):
    url = f"{BASE}/api/{path}"
    req = urllib.request.Request(url, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Token {TOKEN}", "Accept": "application/json", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else None
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {url} -> {e.code}: {e.read().decode()[:400]}")


def get_one(path, **q):
    res = api("GET", f"{path}?{urllib.parse.urlencode(q)}")["results"]
    return res[0] if res else None


def write(method, path, body, why):
    print(("APPLY " if APPLY else "would ") + f"{method} {path} {json.dumps(body)}  # {why}")
    return api(method, path, body) if APPLY else {"id": "<new>"}


def ip(addr):
    return get_one("ipam/ip-addresses/", address=addr)


def main():
    if not TOKEN:
        sys.exit("set NETBOX_TOKEN (needs write permission on ipam, dcim, virtualization)")

    # 1. switch and APs: move the address in place
    for dev, old, new in MOVES:
        if ip(new):
            print(f"ok    {dev}: {new} already exists")
            continue
        cur = ip(old)
        if not cur:
            sys.exit(f"{dev}: neither {old} nor {new} found, check by hand")
        write("PATCH", f"ipam/ip-addresses/{cur['id']}/", {"address": new}, f"{dev} to Management")

    # 2. nastradamus: new primary, old one kept and labelled
    nas = get_one("dcim/devices/", name="nastradamus.sqrd.link")
    iface = get_one("dcim/interfaces/", device_id=nas["id"], name="eth0")
    new = ip("10.10.10.20/24") or write("POST", "ipam/ip-addresses/", {
        "address": "10.10.10.20/24", "status": "active",
        "assigned_object_type": "dcim.interface", "assigned_object_id": iface["id"]}, "nastradamus Management IP")
    if (nas.get("primary_ip4") or {}).get("id") != new["id"]:
        write("PATCH", f"dcim/devices/{nas['id']}/", {"primary_ip4": new["id"]}, "nastradamus primary")
    else:
        print("ok    nastradamus primary already 10.10.10.20")
    old = ip("10.10.100.12/24")
    if old and old.get("description") != LEGACY:
        write("PATCH", f"ipam/ip-addresses/{old['id']}/", {"description": LEGACY}, "mark legacy")

    # 3. centuries: the IP exists, it just isn't primary
    cen = get_one("virtualization/virtual-machines/", name="centuries.sqrd.link")
    cip = ip("10.10.100.75/24")
    if (cen.get("primary_ip4") or {}).get("id") != cip["id"]:
        write("PATCH", f"virtualization/virtual-machines/{cen['id']}/", {"primary_ip4": cip["id"]}, "centuries primary")
    else:
        print("ok    centuries primary already set")

    # 4. pbs: no interface, no IP
    pbs = get_one("virtualization/virtual-machines/", name="pbs.sqrd.link")
    vif = get_one("virtualization/interfaces/", virtual_machine_id=pbs["id"], name="eth0") or write(
        "POST", "virtualization/interfaces/", {"virtual_machine": pbs["id"], "name": "eth0"}, "pbs interface")
    pip = ip("10.10.10.30/24") or write("POST", "ipam/ip-addresses/", {
        "address": "10.10.10.30/24", "status": "active",
        "assigned_object_type": "virtualization.vminterface", "assigned_object_id": vif["id"]}, "pbs Management IP")
    if (pbs.get("primary_ip4") or {}).get("id") != pip["id"]:
        write("PATCH", f"virtualization/virtual-machines/{pbs['id']}/", {"primary_ip4": pip["id"]}, "pbs primary")
    else:
        print("ok    pbs primary already set")

    print("\ndone." if APPLY else "\ndry run only. Re-run with --apply.")


if __name__ == "__main__":
    main()
