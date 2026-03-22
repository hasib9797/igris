#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run uninstall.sh as root: sudo ./uninstall.sh" >&2
  exit 1
fi

PURGE_CONFIG=0
if [[ "${1:-}" == "--purge" ]]; then
  PURGE_CONFIG=1
fi

systemctl disable --now igris.service >/dev/null 2>&1 || true
rm -f /etc/systemd/system/igris.service
systemctl daemon-reload >/dev/null 2>&1 || true

rm -rf /usr/lib/igris
rm -f /usr/bin/igris
rm -f /etc/ufw/applications.d/igris

if [[ "${PURGE_CONFIG}" -eq 1 ]]; then
  rm -rf /etc/igris /var/lib/igris
fi

echo "Igris has been removed."
if [[ "${PURGE_CONFIG}" -eq 0 ]]; then
  echo "Configuration and data were kept. Use sudo ./uninstall.sh --purge to remove them too."
fi
