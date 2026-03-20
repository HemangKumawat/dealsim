#!/usr/bin/env bash
# =============================================================================
# restore.sh -- Restore DealSim from backup
#
# Usage:
#   ./restore.sh --full                    # Full restore (data + configs + certs)
#   ./restore.sh --data                    # Restore data files only
#   ./restore.sh --file feedback.jsonl     # Restore a single file
#   ./restore.sh --configs                 # Restore .env + nginx configs
#   ./restore.sh --list                    # List available backups
#   ./restore.sh --from 2026-03-19_14-00  # Restore from specific timestamp
#
# The script STOPS the application before restoring and restarts it after.
# It creates a local backup of current state before overwriting anything.
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
APP_DIR="/opt/dealsim"
S3_BUCKET="s3://dealsim-backups"
# Volume name matches the key declared in docker-compose.production.yml ("app-data"),
# prefixed by Docker with the project name (directory name = "dealsim").
VOLUME_NAME="${VOLUME_NAME:-dealsim_app-data}"
COMPOSE_FILE="${APP_DIR}/docker-compose.production.yml"
TIMESTAMP=$(date -u +"%Y-%m-%d_%H-%M")
TEMP_DIR="/tmp/dealsim-restore-${TIMESTAMP}"
LOCAL_BACKUP_DIR="/tmp/dealsim-pre-restore-${TIMESTAMP}"
LOG_PREFIX="[restore ${TIMESTAMP}]"

# GPG passphrase for .env decryption
ENV_ENCRYPT_PASSPHRASE="${ENV_ENCRYPT_PASSPHRASE:-}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log() { echo "${LOG_PREFIX} $1"; }

die() { echo "${LOG_PREFIX} FATAL: $1" >&2; exit 1; }

confirm() {
    local msg="$1"
    echo ""
    echo "  ${msg}"
    echo ""
    read -rp "  Continue? [y/N] " answer
    case "$answer" in
        [yY]|[yY][eE][sS]) return 0 ;;
        *) log "Aborted by user"; exit 0 ;;
    esac
}

cleanup() {
    rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

# ---------------------------------------------------------------------------
# Pre-restore safety: backup current state locally
# ---------------------------------------------------------------------------
backup_current_state() {
    log "Creating local backup of current state at ${LOCAL_BACKUP_DIR}/"
    mkdir -p "${LOCAL_BACKUP_DIR}"

    # Backup current data volume
    docker run --rm \
        -v "${VOLUME_NAME}:/source:ro" \
        -v "${LOCAL_BACKUP_DIR}:/backup" \
        alpine sh -c 'cp -a /source/* /backup/ 2>/dev/null || true'

    # Backup current .env
    if [ -f "${APP_DIR}/.env" ]; then
        cp "${APP_DIR}/.env" "${LOCAL_BACKUP_DIR}/dot-env.bak"
    fi

    local count
    count=$(find "${LOCAL_BACKUP_DIR}" -type f | wc -l)
    log "Pre-restore backup: ${count} files saved to ${LOCAL_BACKUP_DIR}/"
    echo ""
    echo "  If restore goes wrong, recover with:"
    echo "    docker run --rm -v ${VOLUME_NAME}:/data -v ${LOCAL_BACKUP_DIR}:/backup alpine sh -c 'cp -a /backup/* /data/'"
    echo ""
}

# ---------------------------------------------------------------------------
# List available backups
# ---------------------------------------------------------------------------
list_backups() {
    log "Available backups in ${S3_BUCKET}:"
    echo ""
    echo "=== Latest ==="
    s3cmd ls "${S3_BUCKET}/latest/" 2>/dev/null || echo "  (none)"
    echo ""
    echo "=== Hourly (last 7 days) ==="
    s3cmd ls "${S3_BUCKET}/hourly/" 2>/dev/null || echo "  (none)"
    echo ""
    echo "=== Daily configs ==="
    s3cmd ls "${S3_BUCKET}/daily/" 2>/dev/null || echo "  (none)"
}

# ---------------------------------------------------------------------------
# Download backup from S3
# ---------------------------------------------------------------------------
download_backup() {
    local source_path="${1:-latest}"
    mkdir -p "${TEMP_DIR}"

    if [ "${source_path}" = "latest" ]; then
        log "Downloading latest backup..."
        s3cmd get "${S3_BUCKET}/latest/data-backup.tar.gz" \
            "${TEMP_DIR}/data-backup.tar.gz" \
            --no-progress 2>&1 | tail -1
    else
        # source_path is a timestamp like 2026-03-19_14-00
        local date_part="${source_path%%_*}"
        log "Downloading backup from ${source_path}..."
        s3cmd get "${S3_BUCKET}/hourly/${date_part}/${source_path}/data-backup.tar.gz" \
            "${TEMP_DIR}/data-backup.tar.gz" \
            --no-progress 2>&1 | tail -1
    fi

    if [ ! -f "${TEMP_DIR}/data-backup.tar.gz" ]; then
        die "Could not download data backup from ${source_path}"
    fi

    # Validate tarball
    if ! tar tzf "${TEMP_DIR}/data-backup.tar.gz" > /dev/null 2>&1; then
        die "Downloaded backup tarball is corrupt"
    fi

    tar xzf "${TEMP_DIR}/data-backup.tar.gz" -C "${TEMP_DIR}/"
    log "Backup downloaded and extracted"
}

# ---------------------------------------------------------------------------
# Stop application
# ---------------------------------------------------------------------------
stop_app() {
    log "Stopping DealSim application..."
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" stop app 2>/dev/null || true
    log "Application stopped"
}

# ---------------------------------------------------------------------------
# Start application
# ---------------------------------------------------------------------------
start_app() {
    log "Starting DealSim application..."
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" start app

    # Wait for health check
    log "Waiting for health check..."
    local retries=10
    while [ $retries -gt 0 ]; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log "Application is healthy"
            return 0
        fi
        retries=$((retries - 1))
        sleep 3
    done

    log "WARNING: Health check did not pass after 30 seconds"
    log "Check logs: docker compose -f ${COMPOSE_FILE} logs dealsim"
    return 1
}

# ---------------------------------------------------------------------------
# Restore: All data files
# ---------------------------------------------------------------------------
restore_data() {
    local source="${1:-latest}"

    download_backup "${source}"

    confirm "This will OVERWRITE all data in the '${VOLUME_NAME}' Docker volume with backup from '${source}'."

    backup_current_state
    stop_app

    log "Restoring data to Docker volume..."
    docker run --rm \
        -v "${VOLUME_NAME}:/data" \
        -v "${TEMP_DIR}:/backup:ro" \
        alpine sh -c '
            # Clear existing data (sessions, JSONL files, session subdirectory)
            rm -rf /data/*
            # Copy all backup contents, including per-session subdirectories
            # created by the per-session file-write change (SCALING_ANALYSIS Change 1)
            cp -a /backup/. /data/ 2>/dev/null || true
            # Set permissions to match the dealsim user (UID 1000) in the container
            chown -R 1000:1000 /data/
        '

    # Show what was restored
    docker run --rm -v "${VOLUME_NAME}:/data:ro" alpine sh -c \
        'echo "Restored files:"; find /data -maxdepth 2 -ls | head -40'

    start_app
    log "Data restore complete"
}

# ---------------------------------------------------------------------------
# Restore: Single file
# ---------------------------------------------------------------------------
restore_file() {
    local filename="$1"
    local source="${2:-latest}"

    download_backup "${source}"

    if [ ! -f "${TEMP_DIR}/${filename}" ]; then
        die "File '${filename}' not found in backup. Available files:"
        ls "${TEMP_DIR}/"
    fi

    local backup_lines
    backup_lines=$(wc -l < "${TEMP_DIR}/${filename}" 2>/dev/null || echo "?")
    confirm "This will OVERWRITE '${filename}' (${backup_lines} lines) in the Docker volume."

    backup_current_state
    stop_app

    log "Restoring ${filename}..."
    docker run --rm \
        -v "${VOLUME_NAME}:/data" \
        -v "${TEMP_DIR}:/backup:ro" \
        alpine sh -c "cp /backup/${filename} /data/${filename} && chown 1000:1000 /data/${filename}"

    start_app
    log "File '${filename}' restored"
}

# ---------------------------------------------------------------------------
# Restore: Configs (.env + nginx)
# ---------------------------------------------------------------------------
restore_configs() {
    log "Downloading config backups..."
    mkdir -p "${TEMP_DIR}/configs"

    # Download encrypted .env
    if s3cmd get "${S3_BUCKET}/latest/env-backup.enc" "${TEMP_DIR}/configs/env-backup.enc" --no-progress 2>/dev/null; then
        if [ -n "${ENV_ENCRYPT_PASSPHRASE}" ]; then
            gpg --batch --yes --passphrase "${ENV_ENCRYPT_PASSPHRASE}" \
                --decrypt -o "${TEMP_DIR}/configs/.env" \
                "${TEMP_DIR}/configs/env-backup.enc"
            log ".env decrypted"
        else
            die "Cannot decrypt .env -- set ENV_ENCRYPT_PASSPHRASE environment variable"
        fi
    elif s3cmd get "${S3_BUCKET}/latest/env-backup.txt" "${TEMP_DIR}/configs/.env" --no-progress 2>/dev/null; then
        log "WARNING: .env was stored unencrypted"
    else
        log "WARNING: No .env backup found"
    fi

    # Download nginx configs
    if s3cmd get "${S3_BUCKET}/latest/nginx-backup.tar.gz" "${TEMP_DIR}/configs/nginx-backup.tar.gz" --no-progress 2>/dev/null; then
        log "nginx config backup downloaded"
    else
        log "WARNING: No nginx config backup found"
    fi

    confirm "This will OVERWRITE .env and nginx/ configs in ${APP_DIR}."

    # Backup current configs
    if [ -f "${APP_DIR}/.env" ]; then
        cp "${APP_DIR}/.env" "${APP_DIR}/.env.bak.${TIMESTAMP}"
        log "Current .env backed up to .env.bak.${TIMESTAMP}"
    fi

    # Restore .env
    if [ -f "${TEMP_DIR}/configs/.env" ]; then
        cp "${TEMP_DIR}/configs/.env" "${APP_DIR}/.env"
        chmod 600 "${APP_DIR}/.env"
        log ".env restored"
    fi

    # Restore nginx configs
    if [ -f "${TEMP_DIR}/configs/nginx-backup.tar.gz" ]; then
        tar xzf "${TEMP_DIR}/configs/nginx-backup.tar.gz" -C "${APP_DIR}/"
        log "nginx configs restored"
    fi

    log "Config restore complete. Restart the stack to apply:"
    echo "  docker compose -f ${COMPOSE_FILE} up -d"
}

# ---------------------------------------------------------------------------
# Full restore (data + configs + certs)
# ---------------------------------------------------------------------------
restore_full() {
    local source="${1:-latest}"

    log "=== FULL RESTORE from ${source} ==="
    confirm "This will perform a FULL restore: data files, .env, nginx configs. The application will be stopped during restore."

    backup_current_state

    # Restore data
    download_backup "${source}"
    stop_app

    log "Restoring data to Docker volume..."
    docker run --rm \
        -v "${VOLUME_NAME}:/data" \
        -v "${TEMP_DIR}:/backup:ro" \
        alpine sh -c '
            rm -rf /data/*
            cp -a /backup/. /data/ 2>/dev/null || true
            chown -R 1000:1000 /data/
        '

    # Restore configs (non-interactive since we already confirmed)
    mkdir -p "${TEMP_DIR}/configs"
    s3cmd get "${S3_BUCKET}/latest/env-backup.enc" "${TEMP_DIR}/configs/env-backup.enc" --no-progress 2>/dev/null || true
    s3cmd get "${S3_BUCKET}/latest/env-backup.txt" "${TEMP_DIR}/configs/.env" --no-progress 2>/dev/null || true
    s3cmd get "${S3_BUCKET}/latest/nginx-backup.tar.gz" "${TEMP_DIR}/configs/nginx-backup.tar.gz" --no-progress 2>/dev/null || true

    if [ -f "${TEMP_DIR}/configs/env-backup.enc" ] && [ -n "${ENV_ENCRYPT_PASSPHRASE}" ]; then
        gpg --batch --yes --passphrase "${ENV_ENCRYPT_PASSPHRASE}" \
            --decrypt -o "${TEMP_DIR}/configs/.env" \
            "${TEMP_DIR}/configs/env-backup.enc"
    fi

    if [ -f "${TEMP_DIR}/configs/.env" ]; then
        cp "${TEMP_DIR}/configs/.env" "${APP_DIR}/.env"
        chmod 600 "${APP_DIR}/.env"
        log ".env restored"
    fi

    if [ -f "${TEMP_DIR}/configs/nginx-backup.tar.gz" ]; then
        tar xzf "${TEMP_DIR}/configs/nginx-backup.tar.gz" -C "${APP_DIR}/"
        log "nginx configs restored"
    fi

    # Restart everything
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" up -d

    # Wait for health
    log "Waiting for application startup..."
    sleep 15
    local health
    health=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")

    if [ "${health}" = "200" ]; then
        log "=== FULL RESTORE COMPLETE -- application healthy ==="
    else
        log "WARNING: Application returned HTTP ${health} after restore"
        log "Check logs: docker compose -f ${COMPOSE_FILE} logs dealsim"
        log "Pre-restore backup available at: ${LOCAL_BACKUP_DIR}/"
    fi
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
main() {
    local mode="${1:---help}"
    local source="latest"

    # Parse --from flag
    for i in "$@"; do
        case "$i" in
            --from) shift; source="${2:-latest}"; shift ;;
        esac
    done

    case "${mode}" in
        --full)
            restore_full "${source}"
            ;;
        --data)
            restore_data "${source}"
            ;;
        --file)
            local filename="${2:-}"
            if [ -z "${filename}" ]; then
                die "Usage: $0 --file <filename> [--from <timestamp>]"
            fi
            restore_file "${filename}" "${source}"
            ;;
        --configs)
            restore_configs
            ;;
        --list)
            list_backups
            ;;
        --help|*)
            echo "DealSim Restore Script"
            echo ""
            echo "Usage:"
            echo "  $0 --full                        Full restore (data + configs)"
            echo "  $0 --data                        Restore data files only"
            echo "  $0 --file <filename>             Restore a single file"
            echo "  $0 --configs                     Restore .env + nginx configs"
            echo "  $0 --list                        List available backups"
            echo ""
            echo "Options:"
            echo "  --from <timestamp>               Restore from specific backup"
            echo "                                   e.g. --from 2026-03-19_14-00"
            echo ""
            echo "Environment variables:"
            echo "  ENV_ENCRYPT_PASSPHRASE           GPG passphrase for .env decryption"
            echo ""
            echo "The script creates a local backup before overwriting anything."
            echo "Pre-restore backups are saved to /tmp/dealsim-pre-restore-*/"
            ;;
    esac
}

main "$@"
