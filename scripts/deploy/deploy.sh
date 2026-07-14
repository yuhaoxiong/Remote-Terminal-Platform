#!/usr/bin/env bash
set -euo pipefail

APP_ROOT="${APP_ROOT:-/opt/edge-platform}"
APP_USER="${APP_USER:-edge-platform}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
BACKUP_ROOT="${BACKUP_ROOT:-/var/backups/edge-platform}"
DB_PATH="${DB_PATH:-/var/lib/edge-platform/platform.db}"
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:8000/api/health}"
SERVICE_NAME="${SERVICE_NAME:-edge-platform}"
GIT_BIN="${GIT_BIN:-/usr/bin/git}"
APP_PYTHON_BIN="${APP_PYTHON_BIN:-$APP_ROOT/.venv/bin/python}"
SYSTEM_PYTHON_BIN="${SYSTEM_PYTHON_BIN:-$(command -v python3.12 || true)}"
NPM_BIN="${NPM_BIN:-/usr/bin/npm}"

MODE="deploy"
if [[ "${1:-}" == "--rollback" ]]; then
    MODE="rollback"
    TARGET_REVISION="${2:-}"
else
    TARGET_REVISION="${1:-}"
fi

if [[ -z "$TARGET_REVISION" ]]; then
    echo "usage: deploy.sh <git-revision> | deploy.sh --rollback <git-revision>" >&2
    exit 2
fi

run_as_app() {
    sudo -H -n -u "$APP_USER" "$@"
}

git_as_app() {
    run_as_app "$GIT_BIN" -C "$APP_ROOT" "$@"
}

resolve_python_bin() {
    if [[ -x "$APP_PYTHON_BIN" ]]; then
        printf '%s' "$APP_PYTHON_BIN"
        return
    fi
    if [[ -n "$SYSTEM_PYTHON_BIN" && -x "$SYSTEM_PYTHON_BIN" ]]; then
        printf '%s' "$SYSTEM_PYTHON_BIN"
        return
    fi
    echo "[deploy] no usable Python 3.12 interpreter found" >&2
    return 1
}

read_database_revision() {
    if [[ ! -f "$DB_PATH" ]]; then
        printf '%s' "none"
        return
    fi
    local python_bin
    python_bin="$(resolve_python_bin)"
    run_as_app "$python_bin" - "$DB_PATH" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(sys.argv[1])
try:
    row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
except sqlite3.Error:
    row = None
finally:
    connection.close()
print(row[0] if row else "none")
PY
}

validate_health() {
    local payload="$1"
    printf '%s' "$payload" | run_as_app "$APP_PYTHON_BIN" -c '
import json
import sys

payload = json.load(sys.stdin)
if payload.get("status") != "ok" or payload.get("database") != "ok":
    raise SystemExit(f"unhealthy response: {payload}")
'
}

echo "[deploy] mode=$MODE start=$(date -Is)"
echo "[deploy] command paths git=$GIT_BIN app_python=$APP_PYTHON_BIN system_python=${SYSTEM_PYTHON_BIN:-none} npm=$NPM_BIN"

echo "[deploy] verify tracked worktree"
if [[ -n "$(git_as_app status --porcelain --untracked-files=no)" ]]; then
    echo "[deploy] refusing to deploy from a dirty tracked worktree: $APP_ROOT" >&2
    exit 1
fi

echo "[deploy] read current Git and database revisions"
PREVIOUS_REVISION="$(git_as_app rev-parse HEAD)"
DATABASE_REVISION_BEFORE="$(read_database_revision)"

echo "[deploy] fetch $DEPLOY_BRANCH and verify target"
git_as_app fetch origin "$DEPLOY_BRANCH"
TARGET_SHA="$(git_as_app rev-parse --verify "$TARGET_REVISION^{commit}")"
git_as_app merge-base --is-ancestor "$TARGET_SHA" "origin/$DEPLOY_BRANCH"

echo "[deploy] previous=$PREVIOUS_REVISION target=$TARGET_SHA database=$DATABASE_REVISION_BEFORE"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
sudo -n /usr/bin/mkdir -p "$BACKUP_ROOT"
BACKUP_PATH="none"
if [[ -f "$DB_PATH" ]]; then
    BACKUP_PATH="$BACKUP_ROOT/platform-$TIMESTAMP.db"
    echo "[deploy] backup sqlite to $BACKUP_PATH"
    sudo -n /usr/bin/cp "$DB_PATH" "$BACKUP_PATH"
else
    echo "[deploy] sqlite db not found yet, skip backup: $DB_PATH"
fi

STATE_PATH="$BACKUP_ROOT/deploy-$TIMESTAMP.state"
printf 'previous_revision=%s\ntarget_revision=%s\ndatabase_revision=%s\nbackup_path=%s\n' \
    "$PREVIOUS_REVISION" "$TARGET_SHA" "$DATABASE_REVISION_BEFORE" "$BACKUP_PATH" \
    | sudo -n /usr/bin/tee "$STATE_PATH" >/dev/null

echo "[deploy] checkout verified revision"
git_as_app checkout --detach "$TARGET_SHA"

echo "[deploy] install backend dependencies"
if [[ ! -x "$APP_ROOT/.venv/bin/python" ]]; then
    if [[ -z "$SYSTEM_PYTHON_BIN" || ! -x "$SYSTEM_PYTHON_BIN" ]]; then
        echo "[deploy] cannot create virtualenv: python3.12 is not available on PATH" >&2
        exit 1
    fi
    run_as_app "$SYSTEM_PYTHON_BIN" -m venv "$APP_ROOT/.venv"
fi
run_as_app "$APP_PYTHON_BIN" -m pip install --upgrade pip
run_as_app "$APP_PYTHON_BIN" -m pip install -r "$APP_ROOT/backend/requirements.txt"

if [[ "$MODE" == "rollback" ]]; then
    TARGET_DATABASE_HEAD="$(
        cd "$APP_ROOT/backend"
        run_as_app "$APP_PYTHON_BIN" -m alembic -c alembic.ini heads \
            | awk 'NR == 1 { print $1 }'
    )"
    CURRENT_DATABASE_REVISION="$(read_database_revision)"
    if [[ "$CURRENT_DATABASE_REVISION" != "none" && "$CURRENT_DATABASE_REVISION" != "$TARGET_DATABASE_HEAD" ]]; then
        echo "[deploy] rollback refused: database revision $CURRENT_DATABASE_REVISION is not target head $TARGET_DATABASE_HEAD" >&2
        echo "[deploy] restore a compatible database backup explicitly before retrying" >&2
        git_as_app checkout --detach "$PREVIOUS_REVISION"
        exit 1
    fi
fi

echo "[deploy] build frontend"
run_as_app "$NPM_BIN" --prefix "$APP_ROOT/frontend" ci
run_as_app "$NPM_BIN" --prefix "$APP_ROOT/frontend" run build

echo "[deploy] restart backend"
sudo -n /usr/bin/systemctl restart "$SERVICE_NAME"

echo "[deploy] validate and reload nginx"
sudo -n /usr/sbin/nginx -t
sudo -n /usr/bin/systemctl reload nginx

echo "[deploy] wait for health check"
HEALTH_PAYLOAD=""
for _ in $(seq 1 30); do
    if HEALTH_PAYLOAD="$(curl -fsS "$HEALTH_URL" 2>/dev/null)" && validate_health "$HEALTH_PAYLOAD"; then
        break
    fi
    HEALTH_PAYLOAD=""
    sleep 2
done

if [[ -z "$HEALTH_PAYLOAD" ]]; then
    echo "[deploy] health check failed" >&2
    echo "[deploy] previous revision: $PREVIOUS_REVISION" >&2
    echo "[deploy] database backup: $BACKUP_PATH" >&2
    exit 1
fi

printf '%s\n' "$TARGET_SHA" | sudo -n /usr/bin/tee "$BACKUP_ROOT/last-successful-revision" >/dev/null
echo "[deploy] success revision=$TARGET_SHA finished=$(date -Is)"
