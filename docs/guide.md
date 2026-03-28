# Igris Guide

## Table Of Contents

1. Platform Overview
2. Installation, Setup, And First Validation
3. Recommended Daily Workflow
4. Core Dashboard Modules
5. AI And Guided Operations
6. Applications, Deployments, And Public Exposure
7. Incidents, Explain, Scan, And System Map
8. Alerts, Monitoring, And Integrations
9. CLI Reference
10. Security Model And Production Habits
11. Data, Config, And Plugin Foundation
12. Current Limits

---

## 1. Platform Overview

Igris is a self-hosted server command center for Ubuntu and Debian systems. It combines:

- a web dashboard
- an admin CLI
- audited command execution
- service, package, firewall, user, file, and process management
- monitoring and alerting
- smart app inventory
- deployment and public exposure workflows

Igris works best when used as an operational surface for real server maintenance, not only as a visual shell around Linux commands.

---

## 2. Installation, Setup, And First Validation

### Install

```bash
git clone https://github.com/hasib9797/igris
cd igris
sudo ./install.sh
```

### Setup

```bash
sudo igris --setup
```

The setup flow configures:

- admin credentials
- dashboard binding
- monitoring behavior
- alert preferences
- update behavior

### First validation after setup

After setup, do a quick validation pass:

```bash
sudo systemctl status igris.service
igris doctor
igris overview
```

Then open:

```text
http://YOUR_SERVER_IP:2511
```

And confirm:

- dashboard loads
- Overview has live data
- Alerts page is reachable
- Services list loads
- Console is disabled or enabled exactly as you expect

---

## 3. Recommended Daily Workflow

For professional day-to-day operations:

1. Start with Overview.
2. Check Incidents and Alerts.
3. Use Applications to understand the workload layout.
4. Use Services, Processes, Logs, and Files to investigate.
5. Use AI Assistant when you want guided reasoning or safe command suggestions.
6. Use Deployments for code updates.
7. Use Integrations so important events leave the dashboard and reach your team channel.

For production troubleshooting:

1. Observe first.
2. Preview next.
3. Change carefully.
4. Verify after change.
5. Resolve alerts only after the issue is truly handled.

---

## 4. Core Dashboard Modules

### Overview

Overview is the main health page. It currently shows:

- hostname
- OS and kernel
- CPU, memory, disk, and uptime
- local and public IP
- failed services
- pending package updates
- top processes
- AI monitor summary

Use it for:

- first look after login
- pre-change health review
- post-change verification

### Services

Services is the systemd control page.

Current actions:

- start
- stop
- restart
- reload
- enable
- disable
- view logs

Best practice:

- inspect logs before restart when the cause is unclear
- use reload only if the service supports live config reload
- confirm `active/sub` state after a change

Example workflow:

1. Search the unit name.
2. Open logs.
3. Restart or reload.
4. Recheck Overview and Alerts.

### Packages

Packages works with `apt`.

Current capabilities:

- search packages
- install package
- remove package
- reinstall package
- update package index
- upgrade all upgradable packages
- inspect installed packages
- inspect upgradable packages

Recommended usage:

- review updates first from Overview or CLI
- use bulk upgrades in a planned maintenance window
- inspect service state after upgrading packages tied to production apps

### Firewall

Firewall works with `ufw`.

Current capabilities:

- enable or disable UFW
- allow port
- deny port
- allow app profile
- inspect rules and status

Important behavior:

- port rules explicitly require TCP or UDP choice

Use cases:

- open a known app port temporarily
- allow standard app profiles like nginx when available
- verify current exposure before public rollout

### Users

Users manages local Linux accounts.

Current capabilities:

- list users
- create user
- choose shell
- set initial password
- apply permission presets
- grant or revoke sudo
- lock or unlock user
- reset password
- delete user

Recommended usage:

- use presets for consistency
- grant sudo only when required
- lock before delete if you want a safer staged offboarding path

### Tasks

Tasks stores reusable command tasks.

Current capabilities:

- create task
- list tasks
- run task
- delete task

Use tasks for:

- repeated maintenance commands
- standard cleanup jobs
- repeatable recovery commands you trust

### Files

Files is the safer in-dashboard file explorer.

Current capabilities:

- browse safe roots
- navigate with breadcrumbs
- search/filter current folder
- create folder
- upload file
- edit text file
- download file
- delete path

Common safe roots:

- `/etc`
- `/var/log`
- `/home`
- `/opt`
- `/srv`
- `/tmp`

Best usage:

- edit app configs
- inspect logs or text files quickly
- upload known-good config fragments

### Processes

Processes is the live process page.

Current capabilities:

- real-time refresh
- CPU and memory view
- high-to-low sorting
- process filter
- `TERM`
- `KILL`

Best usage:

- identify resource spikes
- isolate runaway workers
- confirm whether an app process is alive before touching systemd

### Logs

Logs is the broader journal and service log viewer.

Current capabilities:

- system logs
- service logs
- filtering
- live log stream endpoint support

Best usage:

- cross-service troubleshooting
- system-wide issue investigation
- confirming whether failures are isolated or systemic

### Alerts

Alerts is the event history page.

It currently stores:

- monitor alerts
- update alerts
- manual test alerts

Current actions:

- create test alert
- resolve alert
- clear resolved alerts

### Console

Console is the audited command execution page.

Current capabilities:

- run shell commands
- re-auth protection
- output and exit code
- AI explain overlay
- safer command suggestion
- recent command list

Important limit:

- this is not yet a persistent multi-session PTY terminal

Best usage:

- precise one-shot commands
- post-fix verification commands
- command explanation before execution

---

## 5. AI And Guided Operations

### AI Root Assistant

The AI Assistant uses current server context to answer operational questions.

Current strengths:

- explain what is running
- inspect reachability context
- inspect reverse proxy context
- suggest safe commands
- keep assistant history
- execute allowed commands after confirmation

Good prompt examples:

- Why is my app not reachable?
- Check why nginx is failing
- Explain what is running on this server
- Help me deploy this Node app

Best practice:

- ask concrete questions
- review reasoning and suggested commands
- approve execution only after understanding the exact action

### Command explain workflow

Console and AI together work best like this:

1. Write the command.
2. Use Explain.
3. Review risk level.
4. Review safer command.
5. Run only if the command still makes sense.

This is especially useful before:

- file deletion
- service restarts
- package actions
- reverse proxy changes

---

## 6. Applications, Deployments, And Public Exposure

### Applications

Applications is the smart app inventory.

Detection sources currently include:

- process working directories
- process command lines
- service working directories
- listening ports
- project files such as:
  - `package.json`
  - `requirements.txt`
  - `pyproject.toml`
  - `manage.py`
  - `Dockerfile`
  - `docker-compose.yml`
  - `index.html`
  - `server.properties`

Current classifications include:

- Node
- NestJS
- Express
- React/Vite
- Python
- FastAPI
- Django
- static site
- containerized app
- Minecraft-style server detection

Per app, Igris currently tracks:

- name
- type
- runtime
- path
- status
- ports
- service binding
- process binding
- public domain
- repo and branch when configured

### Deployments

Deployments stores and runs managed deployment config.

Current capabilities:

- save app deployment config
- define repo URL and branch
- define install, build, and restart commands
- run deploy pipeline
- record deploy history
- attempt rollback on failure

Best deployment workflow:

1. Confirm app is detected in Applications.
2. Save deploy configuration.
3. Run deployment.
4. Review logs and service health.
5. Only then expose publicly if needed.

### Public Exposure

Public Exposure uses nginx-backed routing.

Current capabilities:

- preview nginx config
- choose domain
- choose SSL mode
- preview commands
- apply exposure
- remove exposure
- validate nginx before reload
- preserve config backups before overwrite

Recommended usage:

- verify the app works locally first
- preview config every time
- use a valid domain only
- confirm the app port is correct before apply

Example safe rollout:

1. App is stable on local port.
2. Domain is ready.
3. Preview nginx config.
4. Apply exposure.
5. Recheck app reachability.

---

## 7. Incidents, Explain, Scan, And System Map

### Incidents

Incidents is the rule-driven issue timeline.

Current detections include:

- failed services
- crash loops
- high CPU
- high memory
- high disk usage
- nginx validation failure
- repeated deployment failures
- public app local reachability failure

Current actions:

- scan incidents
- preview remediation
- execute remediation with confirmation

Use Preview Fix first. Treat Apply Fix like a production action.

### Explain My Server

Explain My Server is the machine narrative page.

It combines:

- overview state
- detected apps
- open ports
- firewall summary
- incidents
- memory
- recommendations

Use it for:

- onboarding to an unfamiliar host
- quick operator briefings
- pre-maintenance understanding

### Scan & Fix

Scan & Fix currently works through the Explain and Incidents flow.

It currently:

- runs incident scan
- gathers current issues
- returns severity and suggested fixes

### System Map

System Map builds a topology-style view from:

- server node
- application nodes
- port nodes
- domain nodes
- deployment nodes

Use it for:

- understanding routing relationships
- understanding which apps are public
- understanding deployment to app linkage

---

## 8. Alerts, Monitoring, And Integrations

### Monitoring

Background monitoring currently checks:

- CPU usage
- memory usage
- disk usage
- failed services

It also refreshes:

- incident state
- app inventory

### Alerts

Alerts currently come from:

- manual dashboard tests
- monitor events
- update watch

Use test alerts when validating delivery after changing alert settings.

### Integrations

Supported endpoint types:

- Discord webhook
- generic webhook

Current event usage includes:

- deployment success/failure
- exposure applied/removed
- incident-related notifications

Recommended production setup:

1. Keep monitor enabled.
2. Configure at least one external delivery endpoint.
3. Trigger a test alert.
4. Confirm the external system received the event.

---

## 9. CLI Reference

Use `igris help` for current command help.

### Core commands

```bash
igris help
igris version
igris status
igris doctor
igris config
igris health
igris overview
```

### User and task commands

```bash
igris users list
igris tasks list
igris tasks run <id>
igris tasks <id>
```

### Package and service commands

```bash
igris packages upgradable
igris services failed
```

### File commands

```bash
igris files roots
igris files read /path/to/file
```

### Log and alert commands

```bash
igris logs
igris logs 300 nginx.service
igris alerts test
igris update-check
```

### Admin commands

```bash
igris --setup
igris --update
igris --restart
igris reset-admin
igris backup ./igris-backup
igris restore ./igris-backup
```

### Service helper commands

```bash
igris service install
igris service uninstall
igris open-port 2511
igris close-port 2511
```

---

## 10. Security Model And Production Habits

Current protections include:

- authenticated dashboard session
- cookie-based auth
- Argon2 password hashing
- re-auth for dangerous actions
- audit log entries
- explicit confirmation before sensitive actions
- limited AI safe-execution policy

Examples of actions that require confirmation:

- service changes
- firewall edits
- package installation/removal
- file write/delete
- user management
- task execution
- deployment and exposure changes
- AI execution actions

Production habits that matter:

- inspect before changing
- preview before applying
- verify after every high-impact change
- keep backups before risky work
- rely on alerts and incidents, not memory alone

---

## 11. Data, Config, And Plugin Foundation

Common locations:

- config: `/etc/igris/config.yaml`
- runtime data: `/var/lib/igris`
- audit log: `/var/log/igris/audit.log`

Useful references:

- [backend/sample-config.yaml](https://github.com/hasib9797/igris/blob/main/backend/sample-config.yaml)
- [docs/premium-architecture.md](https://github.com/hasib9797/igris/blob/main/docs/premium-architecture.md)
- [examples/hello-plugin/igris-plugin.yaml](https://github.com/hasib9797/igris/blob/main/examples/hello-plugin/igris-plugin.yaml)

Plugin foundation currently includes:

- manifest discovery
- registry persistence
- extension-point metadata

It is a foundation, not yet a full dynamic plugin marketplace/runtime.

---

## 12. Current Limits

To keep this guide honest, these are important current limits:

- Console is an audited command runner, not yet a full multi-session PTY terminal
- System Map is a structured topology view, not yet a full interactive graph canvas
- plugin runtime loading is foundational, not yet fully dynamic
- Cloudflare and SSL automation are still partial
- large-server hardening still benefits from Linux-host validation and soak testing
