#!/usr/bin/env bash
# docker_logs.sh — tail logs from a Docker container (macOS or Linux).
# Usage from Cowork: call_remote("scripts/docker_logs.sh", args=["my-container"])
#                    call_remote("scripts/docker_logs.sh", args=["my-container", "100"])
set -u

usage() {
  echo "Usage: $0 CONTAINER [LINES]" >&2
  echo "CONTAINER is the container name or ID." >&2
  echo "LINES is how many log lines to show (default 50)." >&2
  exit 2
}

CONTAINER="${1:-}"
LINES="${2:-50}"

if [ -z "$CONTAINER" ]; then
  usage
fi

case "$LINES" in
  *[!0-9]*)
    echo "LINES must be a positive number (got: $LINES)" >&2
    exit 2
    ;;
esac

if [ "$LINES" -lt 1 ]; then
  echo "LINES must be at least 1 (got: $LINES)" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "Error: docker CLI not found — install Docker Desktop or the Docker engine." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Error: Docker daemon is not running — start Docker Desktop or the docker service." >&2
  exit 1
fi

if ! docker inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Error: container '$CONTAINER' does not exist." >&2
  echo "Existing containers:" >&2
  docker ps -a --format '  {{.Names}}' 2>/dev/null | head -20 >&2 || true
  exit 1
fi

echo "=== DOCKER LOGS: $CONTAINER (last $LINES lines) ==="
docker logs --tail "$LINES" "$CONTAINER" 2>&1
exit 0
