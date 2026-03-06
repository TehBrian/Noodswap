# Jenkins Deploy (Ubuntu Host)

This setup keeps CI/builds in GitHub Actions and runs deployment locally on your Ubuntu server through Jenkins.

## Overview

1. `CI` workflow validates code.
2. `CD` workflow builds and pushes Docker images to GHCR (`:latest` + commit SHA).
3. Jenkins job receives push webhook, resolves the checked-out commit SHA, waits for that exact GHCR tag, then runs `./deploy/update.sh` on Ubuntu.

## One-time server prep

On Ubuntu host:

```bash
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-plugin git
sudo usermod -aG docker jenkins
sudo usermod -aG docker $USER
```

Then clone repo and prepare deploy files:

```bash
sudo useradd --system --create-home --home-dir /home/noodswap-user --shell /usr/sbin/nologin noodswap-user
sudo usermod -aG docker noodswap-user
sudo -u noodswap-user mkdir -p /home/noodswap-user/noodswap
sudo -u noodswap-user bash -lc 'cd /home/noodswap-user/noodswap && git clone <your-repo-url> . && cd deploy && cp .env.example .env && cp runtime.env.example runtime.env && mkdir -p data/card_images'
```

Edit `deploy/.env`:

```bash
IMAGE_REPOSITORY=ghcr.io/<your-github-user-or-org>/noodswap
```

Edit `deploy/runtime.env` and set at minimum:

```bash
DISCORD_TOKEN=<your-token>
```

## Jenkins job setup

1. Create a Pipeline job (or multibranch pipeline) pointing to this repository.
2. Use repository `Jenkinsfile`.
3. Add Jenkins credential:
   - Kind: `Username with password`
   - ID: `ghcr-readonly`
   - Username: your GitHub username or org service account
   - Password: GitHub PAT with `read:packages`
4. In job configuration/environment, set:
   - `DEPLOY_PATH=/home/noodswap-user/noodswap`
   - `IMAGE_REPOSITORY=ghcr.io/<your-github-user-or-org>/noodswap`
5. Add GitHub webhook to Jenkins endpoint for push events.

## Verification

Run one Jenkins build on `main` and verify:

1. `docker ps` shows `noodswap-bot` running.
2. `docker logs --tail 100 noodswap-bot` shows bot startup.
3. `deploy/data/noodswap.db` exists and persists across restarts.

## Deploy semantics (important)

- Jenkins deploys by immutable commit tag, not by mutable `latest`.
- Effective deploy image is `IMAGE_REPOSITORY:<git-rev-parse-HEAD>` from Jenkins checkout.
- This removes race conditions where Jenkins could otherwise pull an older `latest` if CD publish lags behind webhook delivery.
- Jenkins then validates the `noodswap-bot` container is running and that `docker inspect .Config.Image` matches the expected commit-tag image reference.
