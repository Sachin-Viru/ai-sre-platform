#!/bin/bash

set -u

TEXTFILE_DIR="/var/lib/node_exporter/textfile_collector"

CONTAINER_FILE="${TEXTFILE_DIR}/sre_containers.prom"
SERVICE_FILE="${TEXTFILE_DIR}/sre_services.prom"

TMP_CONTAINER="${CONTAINER_FILE}.tmp"
TMP_SERVICE="${SERVICE_FILE}.tmp"

mkdir -p "$TEXTFILE_DIR"

# ============================================================
# DOCKER CONTAINERS
# Monitor containers configured with a restart policy
# ============================================================

{
    echo '# HELP sre_docker_container_running Whether a monitored Docker container is running (1=yes, 0=no)'
    echo '# TYPE sre_docker_container_running gauge'

    docker ps -a --format '{{.ID}}|{{.Names}}|{{.State}}' |
    while IFS='|' read -r id name state
    do
        [ -z "$id" ] && continue

        restart_policy=$(docker inspect \
            --format '{{.HostConfig.RestartPolicy.Name}}' \
            "$id" 2>/dev/null || true)

        case "$restart_policy" in
            always|unless-stopped|on-failure)
                ;;
            *)
                continue
                ;;
        esac

        if [ "$state" = "running" ]; then
            running=1
        else
            running=0
        fi

        printf 'sre_docker_container_running{id="%s",name="%s",restart_policy="%s"} %s\n' \
            "$id" "$name" "$restart_policy" "$running"
    done

} > "$TMP_CONTAINER"

mv "$TMP_CONTAINER" "$CONTAINER_FILE"


# ============================================================
# SYSTEMD SERVICES
# Monitor enabled, long-running services
# ============================================================

{
    echo '# HELP sre_systemd_service_active Whether an enabled long-running systemd service is active (1=yes, 0=no)'
    echo '# TYPE sre_systemd_service_active gauge'

    systemctl list-unit-files \
        --type=service \
        --state=enabled \
        --no-legend \
        --no-pager |
    awk '{print $1}' |
    while read -r unit
    do
        [ -z "$unit" ] && continue

        # Ignore template units
        case "$unit" in
            *@.service)
                continue
                ;;
        esac

        # Ignore oneshot services
        type=$(systemctl show "$unit" -p Type --value 2>/dev/null || true)

        if [ "$type" = "oneshot" ]; then
            continue
        fi

        if systemctl is-active --quiet "$unit"; then
            value=1
        else
            value=0
        fi

        printf 'sre_systemd_service_active{unit="%s"} %s\n' \
            "$unit" "$value"
    done

} > "$TMP_SERVICE"

mv "$TMP_SERVICE" "$SERVICE_FILE"
