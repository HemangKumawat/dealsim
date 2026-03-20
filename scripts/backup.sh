#!/usr/bin/env bash
# =============================================================================
# scripts/backup.sh — Local backup for DealSim data directory
#
# Backs up the app-data Docker volume (sessions, feedback, events JSONL files)
# to a local directory as compressed archives. Rotates old archives to keep
# only the last N days.
#
# Usage:
#   bash scripts/backup.sh              # backup + rotate
#   bash scripts/backup.sh --verify     # verify the most recent archive
#   bash scripts/backup.sh --list       # list existing archives with sizes
#
# Crontab example (daily at 02:30 on the VPS):
#   30 2 * * *  root  /opt/dealsim/scripts/backup.sh >> /var/log/dealsim-backup.log 2>&1
#
# Environment variables (read from .env or set before calling):
#   BACKUP_DIR          Directory to store archives (default: /opt/backups/dealsim)
#   BACKUP_RETAIN_DAYS  Number of archives to keep  (default: 7)
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration — override via environment or .env
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(dirname "${SCRIPT_DIR}")"

# Load .env if present (so BACKUP_DIR and BACKUP_RETAIN_DAYS can live there)
if [[ -f "${APP_DIR}/.env" ]]; then
    set -o allexport
    # shellcheck disable=SC1090
    source "${APP_DIR}/.env"
    set +o allexport
fi

BACKUP_DIR="${BACKUP_DIR:-/opt/backups/dealsim}"
BACKUP_RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-7}"
# Docker names volumes as <project>_<volume-key>.
# The project name defaults to the directory name (e.g. "dealsim").
# Both docker-compose.yml and docker-compose.production.yml declare the
# volume key as "app-data", so the full name is "dealsim_app-data".
# Override VOLUME_NAME in .env if your project directory has a different name.
VOLUME_NAME="${VOLUME_NAME:-dealsim_app-data}"
TIMESTAMP=$(date -u +"%Y-%m-%d_%H-%M-%S")
ARCHIVE_NAME="dealsim_data_${TIMESTAMP}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"
TEMP_DIR="/tmp/dealsim-backup-${TIMESTAMP}"

# Optional Telegram alerts (no-op if tokens are empty)
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()   { echo "[$(date -u +%H:%M:%S)] $*"; }
alert() {
    log "ALERT: $*"
    if [[ -n "${TELEGRAM_BOT_TOKEN}" && -n "${TELEGRAM_CHAT_ID}" ]]; then
        curl -sf -X POST \
            "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
            -d "chat_id=${TELEGRAM_CHAT_ID}" \
            -d "text=DealSim backup alert: $*" \
            > /dev/null 2>&1 || true
    fi
}

cleanup() { rm -rf "${TEMP_DIR}"; }
trap cleanup EXIT

# ---------------------------------------------------------------------------
# backup — extract volume contents and compress to an archive
# ---------------------------------------------------------------------------
do_backup() {
    log "=== Starting backup ==="
    log "Volume      : ${VOLUME_NAME}"
    log "Destination : ${ARCHIVE_PATH}"

    mkdir -p "${BACKUP_DIR}" "${TEMP_DIR}"

    # Check the volume exists before trying to read it
    if ! docker volume inspect "${VOLUME_NAME}" &>/dev/null; then
        # Fallback: read from the bind-mounted data/ directory if the container
        # is not running (e.g., on a dev machine)
        if [[ -d "${APP_DIR}/data" ]]; then
            log "Docker volume not found — falling back to ${APP_DIR}/data"
            cp -a "${APP_DIR}/data/." "${TEMP_DIR}/"
        else
            alert "Volume ${VOLUME_NAME} not found and ${APP_DIR}/data does not exist."
            exit 1
        fi
    else
        # Extract the volume contents into a temp directory via a throwaway Alpine
        # container. Using :ro on the source ensures the backup never writes to it.
        docker run --rm \
            -v "${VOLUME_NAME}:/source:ro" \
            -v "${TEMP_DIR}:/backup" \
            alpine:3.19 \
            sh -c 'cp -a /source/. /backup/ 2>/dev/null; true'
    fi

    # Count files so we can catch empty backups early
    FILE_COUNT=$(find "${TEMP_DIR}" -type f | wc -l)
    if [[ "${FILE_COUNT}" -eq 0 ]]; then
        alert "Backup temp dir is empty — volume may have no data yet."
        # Not fatal on first run (app might not have written anything yet)
        log "WARNING: 0 files found. Archive will be empty."
    fi

    # Compress to archive
    tar czf "${ARCHIVE_PATH}" -C "${TEMP_DIR}" .

    ARCHIVE_SIZE=$(du -h "${ARCHIVE_PATH}" | cut -f1)
    log "Archive created : ${ARCHIVE_NAME} (${ARCHIVE_SIZE}, ${FILE_COUNT} files)"
}

# ---------------------------------------------------------------------------
# rotate — delete archives older than BACKUP_RETAIN_DAYS
# ---------------------------------------------------------------------------
do_rotate() {
    log "=== Rotating archives (keeping last ${BACKUP_RETAIN_DAYS} days) ==="

    if [[ ! -d "${BACKUP_DIR}" ]]; then
        log "Backup dir does not exist yet — nothing to rotate."
        return
    fi

    DELETED=0
    while IFS= read -r -d '' archive; do
        log "Removing old archive: $(basename "${archive}")"
        rm -f "${archive}"
        DELETED=$(( DELETED + 1 ))
    done < <(find "${BACKUP_DIR}" -maxdepth 1 -name "dealsim_data_*.tar.gz" \
             -mtime "+${BACKUP_RETAIN_DAYS}" -print0)

    if [[ "${DELETED}" -eq 0 ]]; then
        log "No archives older than ${BACKUP_RETAIN_DAYS} days found."
    else
        log "Removed ${DELETED} old archive(s)."
    fi
}

# ---------------------------------------------------------------------------
# verify — inspect the most recent archive for integrity
# ---------------------------------------------------------------------------
do_verify() {
    log "=== Verifying most recent archive ==="

    if [[ ! -d "${BACKUP_DIR}" ]]; then
        log "ERROR: Backup directory ${BACKUP_DIR} does not exist."
        exit 1
    fi

    # Find the newest archive
    LATEST=$(find "${BACKUP_DIR}" -maxdepth 1 -name "dealsim_data_*.tar.gz" \
             -printf '%T@ %p\n' 2>/dev/null | sort -rn | head -1 | awk '{print $2}')

    if [[ -z "${LATEST}" ]]; then
        log "ERROR: No archives found in ${BACKUP_DIR}."
        exit 1
    fi

    log "Checking : $(basename "${LATEST}")"
    log "Size     : $(du -h "${LATEST}" | cut -f1)"

    # 1. Tarball integrity check
    if ! tar tzf "${LATEST}" > /dev/null 2>&1; then
        alert "Archive ${LATEST} is corrupt (tar integrity check failed)."
        exit 1
    fi
    log "OK: tarball integrity check passed"

    # 2. Extract and inspect JSONL files
    mkdir -p "${TEMP_DIR}"
    tar xzf "${LATEST}" -C "${TEMP_DIR}"

    ERRORS=0
    for f in "${TEMP_DIR}"/*.jsonl; do
        [[ -f "${f}" ]] || continue
        FNAME=$(basename "${f}")
        LINE_COUNT=$(wc -l < "${f}")

        # Validate every non-empty line is valid JSON
        BAD=0
        while IFS= read -r line; do
            [[ -z "${line}" ]] && continue
            if ! python3 -c "import json, sys; json.loads(sys.argv[1])" "${line}" 2>/dev/null; then
                BAD=$(( BAD + 1 ))
            fi
        done < "${f}"

        if [[ "${BAD}" -gt 0 ]]; then
            log "WARNING: ${FNAME} — ${BAD} invalid JSON lines out of ${LINE_COUNT}"
            ERRORS=$(( ERRORS + 1 ))
        else
            log "OK: ${FNAME} — ${LINE_COUNT} lines, all valid JSON"
        fi
    done

    if [[ "${ERRORS}" -gt 0 ]]; then
        alert "Verification completed with ${ERRORS} JSONL error(s)."
        exit 1
    fi

    log "=== Verification PASSED ==="
}

# ---------------------------------------------------------------------------
# list — show existing archives sorted newest first
# ---------------------------------------------------------------------------
do_list() {
    if [[ ! -d "${BACKUP_DIR}" ]]; then
        echo "Backup directory ${BACKUP_DIR} does not exist."
        exit 0
    fi

    echo ""
    echo "Archives in ${BACKUP_DIR}:"
    echo "--------------------------------------------------"
    find "${BACKUP_DIR}" -maxdepth 1 -name "dealsim_data_*.tar.gz" \
         -printf '%TY-%Tm-%Td %TH:%TM  %s  %f\n' 2>/dev/null \
    | sort -rn \
    | awk '{printf "%s %s  %8.1f KB  %s\n", $1, $2, $3/1024, $4}' \
    || echo "(none found)"
    echo "--------------------------------------------------"
    echo ""
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
MODE="${1:-backup}"

case "${MODE}" in
    --verify)
        do_verify
        ;;
    --list)
        do_list
        ;;
    backup|"")
        do_backup
        do_rotate
        log "=== Backup complete ==="
        ;;
    *)
        echo "Usage: $(basename "$0") [--verify | --list]"
        echo "       $(basename "$0")             # backup + rotate (default)"
        exit 1
        ;;
esac
