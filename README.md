# The Codex - Docker Compose Setup

This repository contains a collection of Docker Compose configurations for various services used in my homelab environment. All sensitive credentials have been moved from the Docker Compose files to .env files for improved security and management.

## Security Improvements

Previously, sensitive information such as API keys, passwords, and secrets were hardcoded directly in the Docker Compose files. This approach posed security risks as these files could be accidentally committed to version control or exposed in logs.

To address this, I've implemented a secure approach by:

1. Moving all sensitive credentials to `.env` files
2. Using the `env_file` directive in Docker Compose to load environment variables
3. Adding `.env` files to `.gitignore` to prevent accidental commits
4. Creating `.env.example` templates for easy setup

## Directory Structure

Each service directory contains:
- `docker-compose.yml` - The main Docker Compose configuration
- `.env` - Environment variables (not committed to version control)
- `.env.example` - Template with placeholder values

## How to Use

1. **Copy the example files**:
   ```bash
   cp service_name/.env.example service_name/.env
   ```

2. **Edit the .env files** with your actual credentials:
   ```bash
   nano service_name/.env
   ```

3. **Start the services**:
   ```bash
   docker compose up -d
   ```

## Services

### Arcane
- **Purpose**: Application management and orchestration
- **Credentials**: ENCRYPTION_KEY, JWT_SECRET

### Netbox
- **Purpose**: Network automation and documentation
- **Credentials**: SECRET_KEY, DB_PASSWORD, REDIS_PASSWORD, REDIS_CACHE_PASSWORD

### Newt
- **Purpose**: Network monitoring and management
- **Credentials**: NEWT_ID, NEWT_SECRET

### Traefik
- **Purpose**: Reverse proxy and load balancer
- **Credentials**: CF_API_EMAIL, CF_DNS_API_TOKEN

### Immich
- **Purpose**: Self-hosted photo management
- **Credentials**: DB_PASSWORD, DB_USERNAME, DB_DATABASE_NAME

## Important Notes

1. **Never commit .env files** to version control - they are already ignored
2. **Always create .env files from .env.example** templates
3. **Use strong, unique passwords** for all services
4. **Regularly rotate sensitive credentials**
5. **Keep .env.example files updated** with any new environment variables

## Environment Variable Loading

Each Docker Compose file uses the `env_file` directive to load variables from the corresponding `.env` file:

```yaml
env_file:
  - .env
```

This approach provides better separation of configuration and code, making the setup more maintainable and secure.