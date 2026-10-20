#!/bin/bash
set -eo pipefail
: "${FPPDIR:=/opt/fpp}"
. "${FPPDIR}/scripts/common"
PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
command -v python3 >/dev/null || { echo 'Python 3 is required.'; exit 1; }
command -v flock >/dev/null || { echo 'flock is required.'; exit 1; }
DATA="${MEDIADIR}/plugindata/fpp-ledshows"
install -d -m 700 "$DATA"
CONFIG="$DATA/config.json"
OLD_CONFIG="${MEDIADIR}/config/plugin.fpp-ledshows.json"
if [ ! -e "$CONFIG" ] && [ -f "$OLD_CONFIG" ]; then
    mv "$OLD_CONFIG" "$CONFIG"
fi
if [ ! -e "$CONFIG" ]; then
    install -m 600 "$PLUGIN_DIR/config.example.json" "$CONFIG"
fi
chmod 600 "$CONFIG"
if [ "$(id -u)" = 0 ]; then chown -R fpp:fpp "$DATA"; fi
chmod 755 "$PLUGIN_DIR"/scripts/*.sh "$PLUGIN_DIR/connector.py"
bash "$PLUGIN_DIR/scripts/preStop.sh"
bash "$PLUGIN_DIR/scripts/postStart.sh"
echo 'LEDshows Connector installed. Open Content Setup > LEDshows Connector to configure.'
echo 'No show playback settings were changed and FPP was not restarted.'
