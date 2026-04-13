# The Codex

Infrastructure-as-code for the SQRD homelab. Docker Compose configs, Ansible playbooks, and service definitions — one repo for all hosts.

All sensitive credentials are stored in `.env` files and excluded from version control via `.gitignore`.

---

## Repository Structure

```
the_codex/
├── hosts/
│   ├── docker/          # docker.sqrd.link (10.10.100.75) — main Docker VM
│   ├── prtsr/           # Hetzner VPS — public edge node (proxy.prtsr.nl)
│   └── nastradamus/     # nastradamus (10.10.100.12) — TrueNAS + Docker
├── ansible/
│   ├── netbox.yml       # dynamic inventory
│   └── playbooks/
└── README.md
```

> **Note:** The repo is currently being migrated from a flat structure to `hosts/`. Existing service folders at the root are from `docker.sqrd.link` and will move to `hosts/docker/`.

---

## Hosts

### docker.sqrd.link · `10.10.100.75`
Main Docker VM on Proxmox. Runs the bulk of services: media stack, automation, infra tooling.
- Reverse proxy: Traefik → `*.sqrd.link`
- Services: n8n, Netbox, Semaphore, arr stack, Vaultwarden, OpenWebUI, and more

### prtsr · Hetzner VPS
Public edge node. Handles inbound traffic for `*.prtsr.nl` and tunnels back to internal Pangolin.
- Services: Pangolin, n8n, Waha, Uptime Kuma, website (nginx), Minecraft, Arcane

### nastradamus · `10.10.100.12`
TrueNAS Scale NAS + Docker host for storage-adjacent services.
- Services: AdGuard Home 2, Omada Controller, Arcane
- **Datasets:**
  | Dataset | Purpose |
  |---|---|
  | `dataverse` | Main TrueNAS storage pool |
  | `almanac` | Backups share |
  | `automatons` | TrueNAS-hosted apps |
  | `chronicles` | Image share (Immich) |
  | `visions` | Media share (arr suite) |

---

## Conventions

Each service directory contains:
- `docker-compose.yml` — main compose config
- `.env` — environment variables (not committed)
- `.env.example` — template with placeholder values

### Deploy a service

```bash
cd hosts/<hostname>/<service>
cp .env.example .env
nano .env
docker compose up -d
```

### Compose conventions
- Always `restart: unless-stopped`
- Traefik labels for all `*.sqrd.link` services
- Named volumes pointing to `/srv/docker/volumes/<app>/`
- All containers on the shared `proxy` network for Traefik

---

## Important Notes

- **Never commit `.env` files** — already in `.gitignore`
- **Always use `.env.example`** as the template for new setups
- Immich lives on nastradamus (not docker.sqrd.link) — uses the `chronicles` dataset
- Dynamic Ansible inventory is sourced from Netbox via the `ansible/netbox.yml` plugin config
