#!/bin/sh
set -eu
[ "$(id -u)" -eq 0 ] || { echo 'Run as root; no reduced-privilege fallback is installed.' >&2; exit 1; }
SRC=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ROOT=/opt/torsionfield-autogenic
STATE=/var/lib/torsionfield
install -d -m 0755 "$ROOT/resident" "$ROOT/extension" "$ROOT/userscript" "$STATE"
install -m 0755 "$SRC/resident/tf_resident.py" "$ROOT/resident/tf_resident.py"
install -m 0755 "$SRC/resident/browser_recover.mjs" "$ROOT/resident/browser_recover.mjs"
install -m 0755 "$SRC/resident/browser_control.mjs" "$ROOT/resident/browser_control.mjs"
cp "$SRC/extension/"*.js "$SRC/extension/manifest.json" "$ROOT/extension/"
cp "$SRC/userscript/torsionfield-autogenic.user.js" "$ROOT/userscript/"
python3 - <<'PY'
from pathlib import Path
import secrets
p=Path('/var/lib/torsionfield/token')
if not p.exists():
    p.write_text(secrets.token_urlsafe(48)+'\n')
    p.chmod(0o600)
token=p.read_text().strip()
for f in [Path('/opt/torsionfield-autogenic/extension/runtime_config.js'),Path('/opt/torsionfield-autogenic/userscript/torsionfield-autogenic.user.js')]:
    f.write_text(f.read_text().replace('__TF_RESIDENT_TOKEN__',token))
PY
cat >/etc/systemd/system/torsionfield-resident.service <<'UNIT'
[Unit]
Description=Torsionfield Autogenic Privileged Resident
After=network.target

[Service]
Type=simple
Environment=TF_RESIDENT_STATE=/var/lib/torsionfield
ExecStart=/usr/bin/python3 /opt/torsionfield-autogenic/resident/tf_resident.py
Restart=always
RestartSec=1
User=root
Group=root

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now torsionfield-resident.service
curl -fsS http://127.0.0.1:17373/v1/health
