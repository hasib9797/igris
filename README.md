# Igris

Igris is a self-hosted Ubuntu server manager with a web dashboard for system overview, services, packages, logs, processes, firewall rules, users, and safe file operations.

## Real Features

- FastAPI backend with cookie auth and Argon2 password hashing
- React dashboard served by the backend after production build
- Real system overview data from the host
- Real `systemctl` service management
- Real `apt` package search and package operations
- Real `journalctl` logs
- Real process inspection and termination
- Real `ufw` firewall actions
- Real user management with `useradd`, `usermod`, `gpasswd`, and `chpasswd`
- Safe file browsing and text editing under common admin roots
- Setup wizard that writes config, initializes SQLite, installs the systemd unit, and starts the service

## Install

```bash
git clone https://github.com/hasib9797/igris
cd igris
sudo ./install.sh
sudo igris --setup
```

## Access The Dashboard

After setup finishes, open:

```text
http://SERVER_IP:2511
```

The setup wizard prints the detected URL at the end.

## What `install.sh` Does

- installs Ubuntu dependencies:
  - `python3`
  - `python3-pip`
  - `python3-venv`
  - `nodejs`
  - `npm`
  - `ufw`
- builds the frontend with `npm install` and `npm run build`
- installs runtime files into `/usr/lib/igris`
- creates a global `/usr/bin/igris` command
- creates `/etc/igris` and `/var/lib/igris` if needed
- copies a default config if one does not already exist

## What `igris --setup` Does

- asks for the dashboard admin username
- asks for the dashboard password
- hashes the password with Argon2
- generates a session secret
- writes `/etc/igris/config.yaml`
- initializes `/var/lib/igris/database.db`
- installs `/etc/systemd/system/igris.service`
- installs `/etc/ufw/applications.d/igris`
- optionally runs `ufw allow <port>/tcp`
- runs `systemctl daemon-reload`
- runs `systemctl enable igris.service`
- runs `systemctl start igris.service`

## Useful Commands

```bash
igris --setup
igris status
igris reset-admin
```

## Troubleshooting

Check service status:

```bash
sudo systemctl status igris.service
```

Read service logs:

```bash
sudo journalctl -u igris.service -n 200 --no-pager
```

Verify the config file:

```bash
sudo cat /etc/igris/config.yaml
```

Verify the installed runtime:

```bash
ls -la /usr/lib/igris
```

If the dashboard does not load, make sure the port is open:

```bash
sudo ufw status
```

## Uninstall

Keep config and data:

```bash
sudo ./uninstall.sh
```

Remove config and data too:

```bash
sudo ./uninstall.sh --purge
```

## Development Notes

- Runtime config path: `/etc/igris/config.yaml`
- Runtime data path: `/var/lib/igris`
- Install root: `/usr/lib/igris`
- Service unit: `/etc/systemd/system/igris.service`
