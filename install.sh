#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run install.sh as root: sudo ./install.sh" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
INSTALL_DIR="/usr/lib/igris"
CONFIG_DIR="/etc/igris"
DATA_DIR="/var/lib/igris"
BIN_PATH="/usr/bin/igris"

log() {
  echo "[IGRIS] $1"
}

log "Installing dependencies..."
apt-get update
apt --fix-broken install -y || true
apt-get install -y python3 python3-pip python3-venv ufw curl git

if command -v node >/dev/null 2>&1; then
  log "Node.js already installed"
else
  log "Installing Node.js..."
  curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  apt-get install -y nodejs
fi

if ! command -v node >/dev/null 2>&1; then
  echo "[IGRIS] ERROR: node missing after installation" >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "[IGRIS] ERROR: npm missing after Node.js install" >&2
  exit 1
fi

node -v
npm -v

log "Building frontend..."
pushd "${REPO_ROOT}/frontend" >/dev/null
npm install
npm run build
popd >/dev/null

log "Installing backend..."
install -d "${INSTALL_DIR}" "${CONFIG_DIR}" "${DATA_DIR}"
rm -rf "${INSTALL_DIR}/backend" "${INSTALL_DIR}/cli" "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/frontend" "${INSTALL_DIR}/packaging" "${INSTALL_DIR}/public" "${INSTALL_DIR}/venv"

cp -a "${REPO_ROOT}/backend" "${INSTALL_DIR}/backend"
cp -a "${REPO_ROOT}/cli" "${INSTALL_DIR}/cli"
cp -a "${REPO_ROOT}/scripts" "${INSTALL_DIR}/scripts"
cp -a "${REPO_ROOT}/packaging" "${INSTALL_DIR}/packaging"
cp -a "${REPO_ROOT}/public" "${INSTALL_DIR}/public"
install -d "${INSTALL_DIR}/frontend"
cp -a "${REPO_ROOT}/frontend/dist" "${INSTALL_DIR}/frontend/dist"

python3 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"

cat > "${BIN_PATH}" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exec /usr/lib/igris/venv/bin/python /usr/lib/igris/cli/igris_cli.py "$@"
EOF

chmod 0755 "${BIN_PATH}"
chmod 0755 "${INSTALL_DIR}/cli/igris_cli.py"
find "${INSTALL_DIR}/scripts" -type f -name '*.py' -exec chmod 0755 {} \;
chown -R root:root "${INSTALL_DIR}"

if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
  cp "${INSTALL_DIR}/backend/sample-config.yaml" "${CONFIG_DIR}/config.yaml"
fi

log "Done."
echo ""
echo "Igris has been installed to ${INSTALL_DIR}."
echo "Next step:"
echo "  sudo igris --setup"
