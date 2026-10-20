#!/bin/bash
set -euo pipefail
PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
# Match the complete connector path and arguments; never signal another FPP process.
python3 - "$PLUGIN_DIR/connector.py" <<'PY'
import os, signal, sys
target = sys.argv[1].encode()
for pid in os.listdir('/proc'):
    if not pid.isdigit():
        continue
    try:
        args = open('/proc/' + pid + '/cmdline', 'rb').read().split(b'\0')
        if len(args) > 2 and os.path.basename(args[0]).startswith(b'python') and args[1] == target and b'--config' in args:
            os.kill(int(pid), signal.SIGTERM)
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        pass
PY
