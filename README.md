# The Codex - Docker Compose Setup

This repository contains Docker Compose configurations for services running on `docker.sqrd.link` (10.10.100.75).

All sensitive credentials are stored in `.env` files and excluded from version control via `.gitignore`.

## Directory Structure

Each service directory contains:
- `docker-compose.yml` — main compose config
- `.env` — environment variables (not committed)
- `.env.example` — template with placeholder values

## How to Use

1. Copy the example file:
   ```bash
   cp service_name/.env.example service_name/.env
   ```
2. Fill in credentials:
   ```bash
   nano service_name/.env
   ```
3. Start the service:
   ```bash
   docker compose up -d
   ```

## Services

### adguard-sync
Syncs AdGuard Home config from primary (10.10.100.1) to secondary (10.10.100.2).

### arcane
Docker management UI.

### arr_stack
Full media stack: Sonarr, Radarr, Lidarr, Bazarr, Prowlarr, SABnzbd, qBittorrent, Seerr.

### mealie
Recipe manager and meal planner. Available at `mealie.sqrd.link`.

### n8n
Workflow automation. Includes n8n app, Postgres database, and n8n-mcp server.
- n8n UI: `n8n.sqrd.link`
- n8n-mcp runs in HTTP mode on port 3001, connects to n8n via `N8N_API_KEY`

### netbox
IPAM and dynamic Ansible inventory source. Available at `netbox.sqrd.link`.

### newt
Pangolin tunnel client — connects back to internal Pangolin reverse proxy.

### openwebui
LLM frontend (OpenAI-compatible). Available at `openwebui.sqrd.link`.

### semaphore
Ansible UI and scheduler. Uses custom image (`semaphore-netbox`) with pynetbox support.

### traefik
Reverse proxy. Handles all `*.sqrd.link` routing via labels.

### vaultwarden
Self-hosted Bitwarden-compatible password manager.

## Important Notes

- **Never commit `.env` files** — already in `.gitignore`
- **Always use `.env.example`** as the template for new setups
- Immich is **not** running here — it lives on nastradamus (TrueNAS)
- All services attach to the shared `proxy` Docker network for Traefik routing
