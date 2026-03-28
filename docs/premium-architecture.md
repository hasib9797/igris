# Igris Premium Architecture

## Current Structure

Igris keeps the existing FastAPI + SQLite + React dashboard stack intact and layers the new features on top of it.

### Existing Core

- `backend/app/api/routes.py`
  Existing operational API for services, packages, users, files, logs, alerts, and console actions.
- `backend/app/services/modules/*`
  Low-level system operations for Linux admin workflows.
- `backend/app/services/automation.py`
  Background monitor and update loops.
- `frontend/src/App.tsx`
  Existing dashboard shell and operational modules.

## New Premium Integration Points

### Backend Models

New tables were added without modifying the old tables:

- `ManagedApp`
  Smart app inventory and public exposure state.
- `IncidentRecord`
  Rule-driven incident history and remediation context.
- `DeploymentRecord`
  Git-based deployment history and rollback trace.
- `AIActionRecord`
  AI assistant prompts, reasoning summaries, proposed commands, and executed actions.
- `MemoryRecord`
  Local server memory and operator preferences.
- `IntegrationEndpoint`
  Discord and generic webhook endpoints.
- `PluginRecord`
  Registered plugin manifests and extension-point metadata.

### Backend Services

- `backend/app/services/applications.py`
  Detects apps from process cwd, service working directories, ports, and project files.
- `backend/app/services/incidents.py`
  Scans for failed services, crash loops, nginx validation failures, pressure events, unstable deployments, and public-app reachability issues.
- `backend/app/services/assistant.py`
  Modular AI assistant provider interface with the current local heuristic provider, server-state context builder, safe command policy, and action history.
- `backend/app/services/deployments.py`
  Deployment config storage, git-based deploy pipeline, nginx exposure preview/apply/remove, and rollback handling.
- `backend/app/services/explain.py`
  Explain My Server and Scan & Fix summaries.
- `backend/app/services/system_map.py`
  Builds graph nodes and edges for the visual topology view.
- `backend/app/services/integrations.py`
  Reusable notifier fan-out for Discord and generic webhooks.
- `backend/app/services/memory.py`
  Persistent memory/preferences storage.
- `backend/app/services/plugins.py`
  Plugin manifest discovery and registration foundation.

### API Layer

- `backend/app/api/routes_premium.py`
  New premium route group mounted under `/api/premium`.

## Frontend Surfaces

New dashboard pages are mounted inside the existing dashboard shell:

- AI Assistant
- Applications
- Deployments
- Incidents
- System Map
- Explain My Server
- Alerts & Integrations

Page implementations live in:

- `frontend/src/pages/PremiumPages.tsx`

## Plugin Foundation

Plugin discovery looks for:

- `plugins/<plugin-name>/igris-plugin.yaml`

Current manifest fields supported by the registry:

- `id`
- `name`
- `version`
- `enabled`
- `extension_points.pages`
- `extension_points.widgets`
- `extension_points.actions`
- `extension_points.diagnostics`
- `permissions`

The backend persists manifests in `PluginRecord` so future plugin loading and permission enforcement can build on the same registry.

## Notes

- This upgrade preserves the existing service setup and core operations.
- Dangerous actions still require confirmation and are audit logged.
- Auto-remediation remains safe-by-default and is opt-in per rule.
