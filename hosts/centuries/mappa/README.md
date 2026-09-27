# Pianta della Rete

The SQRD homelab network drawn as a Leonardo-style fortified-city plan, after his 1502 map of Imola. The drawing is generated from data, so it stays correct when the network changes.

- The **citadel** at the centre is the ER605. Every road between wards goes through it, because all inter-VLAN traffic is judged there.
- The **wards** are VLANs. Their size follows how many hosts live in them.
- The **walls** are the ACL boundaries.
- The **red-chalk roads** are permitted paths. Click a ward or a building to trace them.
- The **watchtower by the gate** is Pangolin, facing the world.
- The **long thread** under the walls is Tailscale. It still passes the gate, because Tailscale is not a bypass.
- The **gear train** on the left is the ACL, in evaluation order. Click a gear to see what that rule allows.
- **Errata** on the right lists what NetBox and the policy disagree about.
- The **Può passare?** button answers "can X reach Y on port Z", and says which rule decides.

## Layout

```
mappa/                         → the_codex/hosts/centuries/mappa/
├── docker-compose.yml         nginx + hourly sync sidecar
├── .env.example
├── AGENTS.md                  rules for AI agents editing the map
├── site/                      static, no build step, no CDN
│   ├── index.html  mappa.css  mappa.js
│   ├── fonts/                 IM Fell English (+SC), Homemade Apple, all OFL
│   └── data/
│       ├── policy.json        hand/agent maintained
│       └── inventory.json     generated (seed included)
├── schema/                    JSON Schemas for both files
└── tools/
    ├── sync.py                NetBox + Proxmox + Omada + the_codex → inventory.json
    ├── validate.py            schema + reference checks, run after every edit
    └── bundle.py              single-file HTML for sharing or printing
```

## Run it

```sh
python3 -m http.server -d site 8080       # local preview (fetch needs http, not file://)
python3 tools/sync.py --dry-run           # needs NETBOX_URL/NETBOX_TOKEN
python3 tools/validate.py
python3 tools/bundle.py                   # dist/pianta-della-rete.html
```

Deploy: copy the folder to `/srv/docker/compose/mappa/`, create `.env`, run `mkdir -p /srv/docker/volumes/mappa/data`, then `docker compose up -d`. Add a Pangolin resource for `mappa.sqrd.link` → centuries Traefik, because the wildcard lands on Pangolin first. Add `mappa` to NetBox as a service on centuries.

## Automation options

1. **The sidecar (default).** It re-syncs every hour. Zero moving parts.
2. **n8n.** Use a NetBox webhook on device, VM or IP change. The workflow runs `sync.py`, commits `inventory.json` to the_codex for history, and optionally pings you with the new Errata.
3. **Semaphore.** Add an `ansible/playbooks/mappa-sync.yml` that runs the script on centuries after inventory changes.
