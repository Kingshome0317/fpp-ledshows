#!/bin/bash
set -eo pipefail
: "${FPPDIR:=/opt/fpp}"
. "${FPPDIR}/scripts/common"
PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
bash "$PLUGIN_DIR/scripts/preStop.sh"
# Only this connector's private configuration is removed; show files remain untouched.
rm -f "${MEDIADIR}/config/plugin.fpp-ledshows.json"
DATA="${MEDIADIR}/plugindata/fpp-ledshows"
rm -f "$DATA/config.json" "$DATA/runtime-state.json" "$DATA/status.json" "$DATA/csrf" "$DATA/connector.lock" "$DATA/config.json.tmp" "$DATA/runtime-state.tmp" "$DATA/status.tmp"
rmdir "$DATA" 2>/dev/null || true
