#!/bin/bash
set -eo pipefail
: "${FPPDIR:=/opt/fpp}"
. "${FPPDIR}/scripts/common"
PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
bash "$PLUGIN_DIR/scripts/preStop.sh"
python3 - <<'PY'
import json, urllib.request, urllib.parse
for name in ('LEDshows Connector Requests', 'LEDshows Connector Single Request'):
    url = 'http://127.0.0.1/api/playlist/' + urllib.parse.quote(name, safe='')
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            data = json.load(response)
        if data.get('desc') == 'Managed by LEDshows Connector':
            urllib.request.urlopen(urllib.request.Request(url, method='DELETE'), timeout=3).close()
    except Exception:
        pass
PY
# Only this connector's private configuration is removed; show files remain untouched.
rm -f "${MEDIADIR}/config/plugin.fpp-ledshows.json"
DATA="${MEDIADIR}/plugindata/fpp-ledshows"
rm -f "$DATA/config.json" "$DATA/runtime-state.json" "$DATA/status.json" "$DATA/csrf" "$DATA/connector.lock" "$DATA/config.json.tmp" "$DATA/runtime-state.tmp" "$DATA/status.tmp" "$DATA/audio-transfer.tmp"
rmdir "$DATA" 2>/dev/null || true
