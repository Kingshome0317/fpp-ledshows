#!/bin/bash
set -eo pipefail
: "${FPPDIR:=/opt/fpp}"
. "${FPPDIR}/scripts/common"
PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DATA="${MEDIADIR}/plugindata/fpp-ledshows"
CONFIG="$DATA/config.json"
[ -f "$CONFIG" ] || exit 0
export LOGDIR
umask 077
if [ "$(id -u)" = 0 ]; then
    nohup runuser -u fpp -- flock -w 20 "$DATA/connector.lock" python3 "$PLUGIN_DIR/connector.py" --config "$CONFIG" </dev/null >/dev/null 2>&1 &
else
    nohup flock -w 20 "$DATA/connector.lock" python3 "$PLUGIN_DIR/connector.py" --config "$CONFIG" </dev/null >/dev/null 2>&1 &
fi
