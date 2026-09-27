# AGENTS.md: maintaining Pianta della Rete

Instructions for any AI agent (Homie, n8n agents, Claude Code) that changes this map.
Read all of this before editing anything.

---

## The one rule

**The drawing is never edited. Only data is.**
`site/mappa.js` places every building, wall and road from two JSON files. If a change seems to need an SVG edit, you are wrong about where the change belongs. Stop and ask.

---

## Where each fact lives

| Fact | Source of truth | File you touch |
|---|---|---|
| A host exists, its IP, role, tags, parent | NetBox | none. Fix NetBox, then run `tools/sync.py` |
| LXC vs VM, running or stopped | Proxmox | none (sync pulls it) |
| Client counts per VLAN | Omada | none (sync pulls it) |
| Services on a host | `the_codex/hosts/<host>/<app>/` | none (sync lists the directories) |
| VLANs, subnets, ward names, order | here | `site/data/policy.json` → `vlans` |
| Gateway ACL rules | Omada UI (no API) | `policy.json` → `acl.rules` |
| DNS records, rewrites | AdGuard / Cloudflare | `policy.json` → `dns` |
| Port-forwards, Tailscale routes | ER605 / Tailscale admin | `policy.json` → `edge`, `tailscale` |
| NetBox name differs from real name | here | `policy.json` → `aliases` |
| What NetBox *should* say | here | `policy.json` → `expect` |

`site/data/inventory.json` is **generated**. Never hand-edit it. The only exception is the one-time seed that ships with this repo.

---

## Procedures

### A host was added, removed, re-IP'd or renamed

1. Update NetBox (device or VM, primary IPv4, tags).
2. Run `python3 tools/sync.py`, or wait for the hourly `mappa-sync` run.
3. Check that the host shows up in the right ward. If it lands in Errata instead, its IP is outside every subnet in `policy.vlans`.
4. If NetBox uses a different name, add it to `policy.aliases` rather than renaming the host on the map.

### An ACL rule changed on the ER605

1. Edit `policy.acl.rules`. **Order is evaluation order** (first match wins), so keep it identical to Omada.
2. `rules` is the Omada rule number label. Rows that share a label are drawn as one gear.
3. Set `verified: false` unless the change was confirmed in the Omada UI or with a curl test.
4. Use only `vlan:<id>` and `host:<id>` references. `validate.py` rejects anything that doesn't resolve.

### A VLAN was added

1. Add it to `policy.vlans` with `id`, `vid`, `name`, `art` (Italian ward name), `subnet`, and `order`.
2. If the VLAN holds client devices, add `clients`.
3. Wards get their angle automatically, so there are no coordinates to set.

### A DNS record changed

Edit `policy.dns`. `target` is `host:<id>` or `edge:cloudflare`, and `value` is what it resolves to.

---

## After every edit

```sh
python3 tools/validate.py   # must print "ok"
```

- Bump `policy.meta.updated` to today.
- Commit to `the_codex` with a message that says *what changed in the network*, not "update json".
- A new warning from `validate.py` is fine to ship. An ERROR is not.

---

## Do not

- Do not delete Errata by editing `inventory.json`. Fix the source, or add an `expect` entry if the difference is intended.
- Do not add coordinates, colours or sizes to the JSON. Layout is deterministic from the data.
- Do not reference harbinger. It is decommissioned.
- Do not put secrets in `policy.json`. The map is served to the whole LAN.
