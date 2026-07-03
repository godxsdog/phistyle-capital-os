# Deployment

Date: 2026-07-03

Status: manual deploy formalization only. GitHub Actions, platform features, and legacy app integration are intentionally out of scope.

## Current Roles

- MacBook: development machine.
- GitHub: source of truth.
- Mac mini: server.
- Mac mini repository path: `/Users/kaichanghuang/Server/phistyle-capital-os`
- Remote deploy command from MacBook:

```sh
ssh kaichanghuang@KaiChangdeMac-mini.local "~/deploy_phistyle.sh"
```

## Workflow

```text
MacBook
  -> git push origin main
  -> ssh kaichanghuang@KaiChangdeMac-mini.local "~/deploy_phistyle.sh"
  -> Mac mini pulls GitHub main
  -> Mac mini restarts Docker Compose if docker-compose.yml exists
```

## MacBook Usage

From the local development repo:

```sh
scripts/remote_deploy.sh
```

This connects to the Mac mini and runs:

```sh
~/deploy_phistyle.sh
```

## Mac Mini Deploy Script

The canonical deploy script is stored in this repo at:

```text
scripts/deploy_phistyle.sh
```

The Mac mini should have a callable copy at:

```text
~/deploy_phistyle.sh
```

Current deploy behavior:

1. Change directory to `/Users/kaichanghuang/Server/phistyle-capital-os`.
2. Pull `main` from GitHub with `git pull origin main`.
3. Show `git status`.
4. If `docker-compose.yml` exists, run `docker compose up -d --build`.
5. If `docker-compose.yml` does not exist, print `No docker-compose.yml yet. Pull completed only.`

## Installation Notes

To install or refresh the Mac mini copy, copy `scripts/deploy_phistyle.sh` to the Mac mini as `~/deploy_phistyle.sh` and make it executable.

Example:

```sh
scp scripts/deploy_phistyle.sh kaichanghuang@KaiChangdeMac-mini.local:~/deploy_phistyle.sh
ssh kaichanghuang@KaiChangdeMac-mini.local "chmod +x ~/deploy_phistyle.sh"
```

## Explicit Non-Goals

- Do not implement GitHub Actions yet.
- Do not modify legacy apps.
- Do not implement platform features.
- Do not add app-specific deploy logic until runtime ownership is decided.

