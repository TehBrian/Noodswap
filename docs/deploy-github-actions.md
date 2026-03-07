# GitHub Actions Deploy (Ubuntu Host via SSH)

This setup keeps CI/build/publish/deploy fully in GitHub Actions using GitHub-hosted runners.

## Overview

1. `CI` workflow validates code.
2. `CD` workflow builds and pushes GHCR images (`:latest` + commit SHA) when CI succeeds on `main`.
3. `Deploy` workflow runs on GitHub-hosted `ubuntu-latest`, SSHes into your Ubuntu server, runs `deploy/update.sh`, then verifies the running container image matches.

## One-time server prep

On Ubuntu host:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
```

Create deploy user and checkout:

```bash
sudo useradd --system --create-home --home-dir /home/noodswap-user --shell /usr/sbin/nologin noodswap-user
sudo usermod -aG docker noodswap-user
sudo -u noodswap-user mkdir -p /home/noodswap-user/noodswap
sudo -u noodswap-user bash -lc 'cd /home/noodswap-user/noodswap && git clone https://github.com/TehBrian/Noodswap.git . && cd deploy && cp .env.example .env && cp runtime.env.example runtime.env && mkdir -p data/card_images'
sudo chown noodswap-user:noodswap-user /home/noodswap-user/noodswap/deploy/update.sh
sudo chmod 750 /home/noodswap-user/noodswap/deploy/update.sh
```

Edit `deploy/.env`:

```bash
IMAGE_REPOSITORY=ghcr.io/tehbrian/noodswap
```

Edit `deploy/runtime.env` and set at minimum:

```bash
DISCORD_TOKEN=<your-token>
```

If GHCR package visibility is private and deploy runs as `noodswap-user`, run one-time login as that user:

```bash
sudo -u noodswap-user docker login ghcr.io
```

## SSH access setup

The remote SSH user should be able to run deploy as `noodswap-user` (directly or via sudo).

If SSH user is different (for example `ubuntu`), allow sudo for deploy script only:

```bash
sudo tee /etc/sudoers.d/ubuntu-noodswap-deploy >/dev/null <<'EOF'
ubuntu ALL=(noodswap-user) NOPASSWD: /home/noodswap-user/noodswap/deploy/update.sh
EOF
sudo chmod 440 /etc/sudoers.d/ubuntu-noodswap-deploy
sudo visudo -cf /etc/sudoers.d/ubuntu-noodswap-deploy
```

## Repository settings

Required repository variables (`Settings -> Secrets and variables -> Actions -> Variables`):

- `DEPLOY_PATH` (example: `/home/noodswap-user/noodswap`)
- `DEPLOY_AS_USER` (example: `noodswap-user`)
- `DEPLOY_IMAGE_REPOSITORY` (example: `ghcr.io/tehbrian/noodswap`)

Required repository secrets (`Settings -> Secrets and variables -> Actions -> Secrets`):

- `DEPLOY_HOST` (server hostname or IP)
- `DEPLOY_SSH_USER` (SSH user)
- `DEPLOY_SSH_PRIVATE_KEY` (private key for SSH user)
- `DEPLOY_SSH_KNOWN_HOSTS` (`ssh-keyscan -H <host>` output)
- `DEPLOY_SSH_PORT` (example: `22`)
- `GHCR_READONLY_USERNAME`
- `GHCR_READONLY_TOKEN`

## Triggers

- Automatic deploy: on successful `CD` workflow run for `main`.

## Verification

After deploy workflow completes:

1. `docker ps` shows `noodswap-bot` running.
2. Workflow deploy step confirms container image equals `IMAGE_REPOSITORY:<sha>`.
3. `deploy/data/noodswap.db` persists across restarts.

## Notes

- This deploy path is SHA-pinned (immutable), not `latest`.
