import { FormEvent, ReactNode, useMemo, useState } from "react";
import type { ButtonHTMLAttributes } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "../api/client";
import { MetricCard } from "../components/MetricCard";
import { Panel } from "../components/Panel";
import type { Overview } from "../lib/types";

type ApplicationItem = { id: number; name: string; app_type: string; runtime: string; path: string; status: string; ports: number[]; service_name: string; process_name: string; public_domain: string; exposure_status: string; repo_url: string; branch: string; metadata: Record<string, unknown>; updated_at: string | null };
type IncidentItem = { id: number; rule_key: string; severity: string; title: string; summary: string; resource_key: string; status: string; suggested_fix: string; auto_remediation_enabled: boolean; action_summary: string; created_at: string | null; updated_at: string | null; resolved_at: string | null };
type AssistantHistoryItem = { id: number; prompt: string; summary: string; reasoning: string[]; suggestions: Array<{ label: string; reason: string; command: string; risk: string; requires_confirmation: boolean }>; executed_commands: Array<Record<string, unknown>>; status: string; dry_run: boolean; created_at: string | null };
type AssistantResponse = { id: number; summary: string; reasoning: string[]; suggestions: Array<{ label: string; reason: string; command: string; risk: string; requires_confirmation: boolean }>; context: { explain: { summary: string; recommendations: string[] }; apps: ApplicationItem[]; incidents: IncidentItem[] } & Record<string, unknown> };
type DeploymentItem = { id: number; app_name: string; repo_url: string; branch: string; revision: string; status: string; deployed_path: string; service_name: string; log_excerpt: string; created_at: string | null };
type SystemMapResponse = { summary: string; nodes: Array<{ id: string; label: string; kind: string; status?: string; path?: string }>; edges: Array<{ from: string; to: string; label: string }> };
type IntegrationItem = { id: number; name: string; kind: string; target_url: string; enabled: boolean; events: string[]; headers: Record<string, string>; updated_at: string | null };
type ExplainResponse = { summary: string; recommendations: string[]; applications: ApplicationItem[]; incidents: IncidentItem[]; open_ports: string[]; firewall: string; memory: Array<{ id: number; key: string; scope: string; value: Record<string, unknown>; updated_at: string | null }>; overview: Overview };

function askForConfirmation() {
  return window.prompt("Confirm with your dashboard password");
}

function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Request failed";
  return <div className="rounded-2xl border border-rose-500/35 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{message}</div>;
}

function Notice({ message, tone = "success" }: { message: string; tone?: "success" | "error" | "info" }) {
  const style =
    tone === "error"
      ? "border-rose-500/35 bg-rose-500/10 text-rose-100"
      : tone === "info"
        ? "border-sky-400/30 bg-sky-500/10 text-sky-100"
        : "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${style}`}>{message}</div>;
}

function ActionButton({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`inline-flex items-center justify-center rounded-2xl px-4 py-2.5 text-sm font-medium transition disabled:cursor-not-allowed disabled:opacity-50 ${className || "bg-ember-500 text-white hover:bg-ember-400"}`}
    />
  );
}

function Pill({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "success" | "warning" | "danger" }) {
  const style =
    tone === "success"
      ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-100"
      : tone === "warning"
        ? "border-amber-400/20 bg-amber-500/10 text-amber-100"
        : tone === "danger"
          ? "border-rose-500/20 bg-rose-500/10 text-rose-100"
          : "border-white/10 bg-white/5 text-slate-200";
  return <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-medium ${style}`}>{children}</span>;
}

function Modal({ open, title, subtitle, onClose, children }: { open: boolean; title: string; subtitle?: string; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm" onClick={onClose}>
      <div className="flex max-h-[88vh] w-full max-w-4xl flex-col overflow-hidden rounded-[2rem] border border-white/10 bg-[#0d1117] shadow-panel" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4 border-b border-white/10 px-6 py-5">
          <div>
            <h3 className="font-display text-2xl text-white">{title}</h3>
            {subtitle ? <p className="mt-2 text-sm text-slate-400">{subtitle}</p> : null}
          </div>
          <button type="button" onClick={onClose} className="rounded-2xl border border-white/10 bg-white/5 p-2 text-slate-300 transition hover:bg-white/10 hover:text-white">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="overflow-auto px-6 py-6">{children}</div>
      </div>
    </div>
  );
}

function SectionHeader({ title, subtitle, refresh }: { title: string; subtitle: string; refresh?: () => void }) {
  return (
    <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="font-display text-2xl text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
      </div>
      {refresh ? <button type="button" onClick={refresh} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition hover:bg-white/10">Refresh</button> : null}
    </div>
  );
}

export function AIAssistantPage() {
  const history = useQuery<AssistantHistoryItem[]>({ queryKey: ["assistant-history"], queryFn: () => api<AssistantHistoryItem[]>("/api/premium/assistant/history"), staleTime: 5000, refetchInterval: 10000 });
  const [prompt, setPrompt] = useState("Why is my app not reachable?");
  const [result, setResult] = useState<AssistantResponse | null>(null);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [busyCommand, setBusyCommand] = useState("");
  const quickPrompts = ["Why is my app not reachable?", "Check why nginx is failing", "Explain what is running on this server", "Help me deploy this Node app"];

  async function askAssistant(nextPrompt?: string) {
    const finalPrompt = (nextPrompt ?? prompt).trim();
    if (!finalPrompt) return;
    setActionError("");
    setNotice("");
    try {
      const response = await api<AssistantResponse>("/api/premium/assistant/query", { method: "POST", body: JSON.stringify({ prompt: finalPrompt, dry_run: true }) });
      setResult(response);
      setPrompt(finalPrompt);
      await history.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Assistant request failed");
    }
  }

  async function runSuggestion(command: string, requiresConfirmation: boolean) {
    const confirmPassword = requiresConfirmation ? askForConfirmation() : undefined;
    if (requiresConfirmation && !confirmPassword) return;
    setBusyCommand(command);
    try {
      const response = await api<{ returncode?: number }>("/api/premium/assistant/execute", { method: "POST", body: JSON.stringify({ prompt, command, confirm_password: confirmPassword, dry_run: false }) });
      setNotice(`AI action executed${typeof response.returncode === "number" ? ` with exit ${response.returncode}` : ""}.`);
      await history.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Assistant action failed");
    } finally {
      setBusyCommand("");
    }
  }

  return (
    <div className="space-y-6">
      <Panel title="AI Root Assistant" subtitle="Context-aware operational help with auditable safe actions">
        <SectionHeader title="Ask Igris" subtitle="Explain services, inspect failures, understand ports, and generate safe commands" refresh={() => history.refetch()} />
        <ErrorBanner error={history.error} />
        {actionError ? <Notice message={actionError} tone="error" /> : null}
        {notice ? <Notice message={notice} /> : null}
        <div className="grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
          <div className="space-y-4">
            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
              <textarea value={prompt} onChange={(event) => setPrompt(event.target.value)} className="min-h-[12rem] w-full rounded-3xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-100" placeholder="Ask about server health, services, logs, ports, deployments, or reverse proxy issues" />
              <div className="mt-4 flex flex-wrap gap-3">
                <ActionButton onClick={() => askAssistant()}>Analyze Server State</ActionButton>
                {quickPrompts.map((item) => <ActionButton key={item} onClick={() => askAssistant(item)} className="bg-white/5 text-white hover:bg-white/10">{item}</ActionButton>)}
              </div>
            </div>
            {result ? (
              <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
                <h3 className="font-display text-2xl text-white">Current Answer</h3>
                <p className="mt-3 text-sm leading-7 text-slate-200">{result.summary}</p>
                <div className="mt-5 space-y-2 text-sm text-slate-300">{result.reasoning.map((item) => <div key={item}>{item}</div>)}</div>
                <div className="mt-5 space-y-3">
                  {result.suggestions.map((item) => (
                    <div key={`${item.command}-${item.label}`} className="rounded-3xl border border-white/10 bg-black/20 p-4">
                      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <div className="text-sm font-medium text-white">{item.label}</div>
                            <Pill tone={item.risk === "low" ? "success" : item.risk === "medium" ? "warning" : "danger"}>{item.risk} risk</Pill>
                          </div>
                          <p className="mt-2 text-sm text-slate-300">{item.reason}</p>
                          <pre className="mt-3 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-emerald-100">{item.command}</pre>
                        </div>
                        <ActionButton onClick={() => runSuggestion(item.command, item.requires_confirmation)} disabled={busyCommand === item.command}>{busyCommand === item.command ? "Running..." : "Run approved action"}</ActionButton>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
          <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
            <h3 className="font-display text-2xl text-white">Last Actions</h3>
            <div className="mt-4 space-y-3">
              {(history.data ?? []).slice(0, 6).map((item) => (
                <div key={item.id} className="rounded-3xl border border-white/10 bg-black/20 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Pill tone={item.status === "executed" ? "success" : "warning"}>{item.status}</Pill>
                    <div className="text-xs text-slate-500">{item.created_at ? new Date(item.created_at).toLocaleString() : "unknown"}</div>
                  </div>
                  <div className="mt-2 text-sm font-medium text-white">{item.prompt}</div>
                  <p className="mt-2 text-sm text-slate-300">{item.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

export function ApplicationsPage() {
  const apps = useQuery<ApplicationItem[]>({ queryKey: ["premium-apps"], queryFn: () => api<ApplicationItem[]>("/api/premium/applications"), staleTime: 5000, refetchInterval: 15000 });
  const [selected, setSelected] = useState<ApplicationItem | null>(null);
  const [domain, setDomain] = useState("");
  const [sslMode, setSslMode] = useState("letsencrypt");
  const [preview, setPreview] = useState<{ nginx_config: string; commands: string[] } | null>(null);
  const [actionError, setActionError] = useState("");

  async function refreshApps() {
    try {
      await api("/api/premium/applications/refresh", { method: "POST" });
      await apps.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to refresh applications");
    }
  }

  async function previewExposure() {
    if (!selected || !domain.trim()) return;
    try {
      const response = await api<{ nginx_config: string; commands: string[] }>("/api/premium/exposure/preview", { method: "POST", body: JSON.stringify({ app_id: selected.id, domain, ssl_mode: sslMode, open_firewall: true }) });
      setPreview(response);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to preview exposure");
    }
  }

  return (
    <>
      <Panel title="Applications" subtitle="Smart app detection across services, ports, runtimes, and working directories">
        <SectionHeader title="Detected Applications" subtitle="Igris scans live processes and service units to map actual apps running on the host" refresh={refreshApps} />
        <ErrorBanner error={apps.error || actionError} />
        <div className="grid gap-4 xl:grid-cols-2">
          {(apps.data ?? []).map((app) => (
            <button key={app.id} type="button" onClick={() => { setSelected(app); setDomain(app.public_domain || ""); setPreview(null); }} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 text-left transition hover:bg-white/10">
              <div className="flex flex-wrap items-center gap-2">
                <Pill tone={app.status === "active" || app.status === "running" ? "success" : "warning"}>{app.status}</Pill>
                <Pill tone={app.exposure_status === "public" ? "warning" : "neutral"}>{app.exposure_status}</Pill>
                <Pill tone="neutral">{app.app_type}</Pill>
              </div>
              <h3 className="mt-4 font-display text-2xl text-white">{app.name}</h3>
              <p className="mt-2 text-sm text-slate-400">{app.path}</p>
              <div className="mt-4 flex flex-wrap gap-2 text-sm text-slate-300"><span>Runtime: {app.runtime}</span><span>Ports: {app.ports.length ? app.ports.join(", ") : "none"}</span></div>
            </button>
          ))}
        </div>
      </Panel>
      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.name ?? "Application"} subtitle={selected ? `${selected.app_type} • ${selected.runtime} • ${selected.path}` : undefined}>
        {selected ? (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-[1fr,220px,auto]">
              <input value={domain} onChange={(event) => setDomain(event.target.value)} placeholder="app.example.com" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
              <select value={sslMode} onChange={(event) => setSslMode(event.target.value)} className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white">
                <option value="letsencrypt">Let's Encrypt</option>
                <option value="cloudflare">Cloudflare</option>
                <option value="none">No SSL</option>
              </select>
              <ActionButton onClick={previewExposure}>Preview</ActionButton>
            </div>
            {preview ? (
              <>
                <pre className="overflow-auto rounded-3xl border border-white/10 bg-slate-950/80 p-4 text-xs text-emerald-100">{preview.nginx_config}</pre>
                <div className="space-y-2 text-sm text-slate-300">{preview.commands.map((command) => <div key={command}>{command}</div>)}</div>
              </>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </>
  );
}

export function DeploymentsPage() {
  const deployments = useQuery<DeploymentItem[]>({ queryKey: ["premium-deployments"], queryFn: () => api<DeploymentItem[]>("/api/premium/deployments"), staleTime: 5000, refetchInterval: 10000 });
  const apps = useQuery<ApplicationItem[]>({ queryKey: ["premium-deploy-apps"], queryFn: () => api<ApplicationItem[]>("/api/premium/applications"), staleTime: 5000 });
  const [form, setForm] = useState({ app_name: "", path: "", repo_url: "", branch: "main", runtime: "auto", install_command: "", build_command: "", restart_command: "", service_name: "", port: "" });
  const [selectedAppId, setSelectedAppId] = useState<number>(0);
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function saveDeploymentConfig(event: FormEvent) {
    event.preventDefault();
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    try {
      await api("/api/premium/deployments/configure", { method: "POST", body: JSON.stringify({ ...form, port: form.port ? Number(form.port) : null, confirm_password: confirmPassword }) });
      setNotice("Deployment configuration saved.");
      await apps.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to save deployment config");
    }
  }

  async function runDeployment() {
    if (!selectedAppId) return;
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    try {
      const response = await api<{ status: string }>("/api/premium/deployments/run", { method: "POST", body: JSON.stringify({ app_id: selectedAppId, confirm_password: confirmPassword }) });
      setNotice(`Deployment ${response.status}.`);
      await deployments.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Deployment failed");
    }
  }

  return (
    <Panel title="Deployments" subtitle="Git-based deploy config, redeploy actions, and deployment history">
      <SectionHeader title="GitHub Auto Deploy" subtitle="Configure repo-backed deployment flows and redeploy managed apps safely" refresh={() => deployments.refetch()} />
      <ErrorBanner error={deployments.error || apps.error || actionError} />
      {notice ? <Notice message={notice} /> : null}
      <div className="grid gap-6 xl:grid-cols-[1fr,1fr]">
        <form onSubmit={saveDeploymentConfig} className="space-y-4 rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <div className="grid gap-3 md:grid-cols-2">
            <input value={form.app_name} onChange={(event) => setForm((current) => ({ ...current, app_name: event.target.value }))} placeholder="App name" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.path} onChange={(event) => setForm((current) => ({ ...current, path: event.target.value }))} placeholder="/srv/app" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.repo_url} onChange={(event) => setForm((current) => ({ ...current, repo_url: event.target.value }))} placeholder="https://github.com/user/repo.git" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white md:col-span-2" />
            <input value={form.branch} onChange={(event) => setForm((current) => ({ ...current, branch: event.target.value }))} placeholder="main" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.service_name} onChange={(event) => setForm((current) => ({ ...current, service_name: event.target.value }))} placeholder="my-app.service" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.install_command} onChange={(event) => setForm((current) => ({ ...current, install_command: event.target.value }))} placeholder="npm install" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.build_command} onChange={(event) => setForm((current) => ({ ...current, build_command: event.target.value }))} placeholder="npm run build" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.restart_command} onChange={(event) => setForm((current) => ({ ...current, restart_command: event.target.value }))} placeholder="pm2 restart ecosystem.config.js" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
            <input value={form.port} onChange={(event) => setForm((current) => ({ ...current, port: event.target.value }))} placeholder="3000" className="rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
          </div>
          <ActionButton type="submit">Save Deployment Config</ActionButton>
        </form>
        <div className="space-y-4 rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <select value={selectedAppId} onChange={(event) => setSelectedAppId(Number(event.target.value))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white">
            <option value={0}>Select an app</option>
            {(apps.data ?? []).map((app) => <option key={app.id} value={app.id}>{app.name} • {app.path}</option>)}
          </select>
          <ActionButton onClick={runDeployment} disabled={!selectedAppId}>Run Deploy Pipeline</ActionButton>
          <div className="space-y-3">
            {(deployments.data ?? []).map((deployment) => (
              <div key={deployment.id} className="rounded-3xl border border-white/10 bg-black/20 p-4">
                <div className="flex flex-wrap items-center gap-2"><Pill tone={deployment.status === "success" ? "success" : deployment.status === "failed" ? "danger" : "warning"}>{deployment.status}</Pill><div className="text-sm font-medium text-white">{deployment.app_name}</div></div>
                {deployment.log_excerpt ? <pre className="mt-3 max-h-40 overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-3 text-xs text-slate-300">{deployment.log_excerpt}</pre> : null}
              </div>
            ))}
          </div>
        </div>
      </div>
    </Panel>
  );
}

export function IncidentsPage() {
  const incidents = useQuery<IncidentItem[]>({ queryKey: ["premium-incidents"], queryFn: () => api<IncidentItem[]>("/api/premium/incidents"), staleTime: 5000, refetchInterval: 10000 });
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [dryRun, setDryRun] = useState<Record<number, string[]>>({});

  async function scanIncidents() {
    try {
      await api("/api/premium/incidents/scan", { method: "POST" });
      await incidents.refetch();
      setNotice("Incident scan completed.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to scan incidents");
    }
  }

  async function previewRemediation(incidentId: number) {
    try {
      const response = await api<{ commands: string[] }>(`/api/premium/incidents/${incidentId}/remediate`, { method: "POST", body: JSON.stringify({ dry_run: true }) });
      setDryRun((current) => ({ ...current, [incidentId]: response.commands ?? [] }));
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to preview remediation");
    }
  }

  async function executeRemediation(incidentId: number) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    try {
      await api(`/api/premium/incidents/${incidentId}/remediate`, { method: "POST", body: JSON.stringify({ dry_run: false, confirm_password: confirmPassword }) });
      setNotice(`Remediation executed for incident ${incidentId}.`);
      await incidents.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to remediate incident");
    }
  }

  return (
    <Panel title="Incidents" subtitle="Rule-driven detection, explanation, and safe remediation previews">
      <SectionHeader title="Incident Timeline" subtitle="Service failures, resource pressure, reverse proxy errors, and unstable deployments" refresh={scanIncidents} />
      <ErrorBanner error={incidents.error || actionError} />
      {notice ? <Notice message={notice} /> : null}
      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Open" value={String((incidents.data ?? []).filter((item) => item.status === "open").length)} />
        <MetricCard label="Critical" value={String((incidents.data ?? []).filter((item) => item.severity === "critical" && item.status === "open").length)} accent="from-rose-500/25 to-transparent" />
        <MetricCard label="Auto-Remediation" value={String((incidents.data ?? []).filter((item) => item.auto_remediation_enabled).length)} accent="from-amber-500/25 to-transparent" />
      </div>
      <div className="mt-6 space-y-4">
        {(incidents.data ?? []).map((incident) => (
          <div key={incident.id} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Pill tone={incident.severity === "critical" ? "danger" : "warning"}>{incident.severity}</Pill>
                  <Pill tone={incident.status === "resolved" ? "success" : "warning"}>{incident.status}</Pill>
                </div>
                <h3 className="mt-3 font-display text-2xl text-white">{incident.title}</h3>
                <p className="mt-3 text-sm leading-7 text-slate-300">{incident.summary}</p>
                <div className="mt-3 rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">{incident.suggested_fix}</div>
                {dryRun[incident.id]?.length ? <pre className="mt-3 overflow-auto rounded-3xl border border-sky-400/20 bg-sky-500/10 p-4 text-xs text-sky-50">{dryRun[incident.id].join("\n")}</pre> : null}
              </div>
              <div className="flex flex-col gap-3">
                <ActionButton onClick={() => previewRemediation(incident.id)} className="bg-white/5 text-white hover:bg-white/10">Preview Fix</ActionButton>
                {incident.status === "open" ? <ActionButton onClick={() => executeRemediation(incident.id)}>Apply Fix</ActionButton> : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export function SystemMapPage() {
  const systemMap = useQuery<SystemMapResponse>({ queryKey: ["premium-system-map"], queryFn: () => api<SystemMapResponse>("/api/premium/system-map"), staleTime: 5000, refetchInterval: 15000 });
  const groupedNodes = useMemo(() => {
    const groups: Record<string, SystemMapResponse["nodes"]> = {};
    for (const node of systemMap.data?.nodes ?? []) {
      groups[node.kind] = groups[node.kind] ?? [];
      groups[node.kind].push(node);
    }
    return groups;
  }, [systemMap.data]);

  return (
    <Panel title="System Map" subtitle="Live relationships between apps, ports, domains, and deployment sources">
      <SectionHeader title="Topology Graph" subtitle="A refreshable server map built from detected apps, public exposure, and deployment records" refresh={() => systemMap.refetch()} />
      <ErrorBanner error={systemMap.error} />
      <div className="rounded-[1.75rem] border border-sky-400/20 bg-sky-500/10 p-5 text-sm text-sky-50">{systemMap.data?.summary ?? "Loading topology graph..."}</div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1fr,1fr]">
        <div className="space-y-4">
          {Object.entries(groupedNodes).map(([group, nodes]) => (
            <div key={group} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
              <h3 className="font-display text-2xl capitalize text-white">{group}</h3>
              <div className="mt-4 grid gap-3 md:grid-cols-2">
                {nodes.map((node) => <div key={node.id} className="rounded-3xl border border-white/10 bg-black/20 p-4"><div className="text-sm font-medium text-white">{node.label}</div><div className="mt-1 text-xs text-slate-500">{node.path ?? node.id}</div></div>)}
              </div>
            </div>
          ))}
        </div>
        <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <h3 className="font-display text-2xl text-white">Relationships</h3>
          <div className="mt-4 space-y-3">
            {(systemMap.data?.edges ?? []).map((edge) => <div key={`${edge.from}-${edge.to}-${edge.label}`} className="rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200"><div className="font-medium text-white">{edge.label}</div><div className="mt-2 text-slate-400">{edge.from} → {edge.to}</div></div>)}
          </div>
        </div>
      </div>
    </Panel>
  );
}

export function ExplainPage() {
  const explain = useQuery<ExplainResponse>({ queryKey: ["premium-explain"], queryFn: () => api<ExplainResponse>("/api/premium/explain"), staleTime: 5000, refetchInterval: 15000 });
  const [scanSummary, setScanSummary] = useState<{ count: number; issues: Array<{ severity: string; title: string; suggested_fix: string }> } | null>(null);
  const [actionError, setActionError] = useState("");

  async function runScanFix() {
    try {
      const response = await api<{ count: number; issues: Array<{ severity: string; title: string; suggested_fix: string }> }>("/api/premium/scan-fix", { method: "POST" });
      setScanSummary(response);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Scan failed");
    }
  }

  return (
    <Panel title="Explain My Server" subtitle="A higher-level explanation of what is running, public, risky, and worth improving next">
      <SectionHeader title="Server Story" subtitle="Translate raw system state into an actionable operations narrative" refresh={() => explain.refetch()} />
      <ErrorBanner error={explain.error || actionError} />
      <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
        <h3 className="font-display text-3xl text-white">{explain.data?.summary ?? "Building explanation..."}</h3>
        <div className="mt-5 flex flex-wrap gap-3">
          <ActionButton onClick={runScanFix}>Scan & Fix</ActionButton>
          {(explain.data?.recommendations ?? []).map((item) => <Pill key={item} tone="warning">{item}</Pill>)}
        </div>
      </div>
      {scanSummary ? <div className="mt-6 rounded-[1.75rem] border border-sky-400/20 bg-sky-500/10 p-5 text-sm text-sky-50">{scanSummary.count} issue(s) found.</div> : null}
    </Panel>
  );
}

export function IntegrationsPage() {
  const integrations = useQuery<IntegrationItem[]>({ queryKey: ["premium-integrations"], queryFn: () => api<IntegrationItem[]>("/api/premium/integrations"), staleTime: 5000 });
  const [form, setForm] = useState({ name: "", kind: "discord", target_url: "", events: "deployment.success,deployment.failed,exposure.applied,incident.ai-monitor" });
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function saveIntegration(event: FormEvent) {
    event.preventDefault();
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    try {
      await api("/api/premium/integrations", { method: "POST", body: JSON.stringify({ name: form.name, kind: form.kind, target_url: form.target_url, enabled: true, events: form.events.split(",").map((item) => item.trim()).filter(Boolean), headers: {}, confirm_password: confirmPassword }) });
      setNotice("Integration saved.");
      await integrations.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to save integration");
    }
  }

  return (
    <Panel title="Alerts & Integrations" subtitle="Discord and generic webhook fan-out for incidents, exposure, deploys, and AI actions">
      <SectionHeader title="Notification Integrations" subtitle="Connect Discord webhooks and generic webhooks to Igris event streams" refresh={() => integrations.refetch()} />
      <ErrorBanner error={integrations.error || actionError} />
      {notice ? <Notice message={notice} /> : null}
      <div className="grid gap-6 xl:grid-cols-[1fr,1fr]">
        <form onSubmit={saveIntegration} className="space-y-4 rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} placeholder="Ops Discord" className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
          <select value={form.kind} onChange={(event) => setForm((current) => ({ ...current, kind: event.target.value }))} className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white"><option value="discord">Discord Webhook</option><option value="webhook">Generic Webhook</option></select>
          <input value={form.target_url} onChange={(event) => setForm((current) => ({ ...current, target_url: event.target.value }))} placeholder="https://discord.com/api/webhooks/..." className="w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
          <textarea value={form.events} onChange={(event) => setForm((current) => ({ ...current, events: event.target.value }))} className="min-h-[8rem] w-full rounded-2xl border border-white/10 bg-black/20 px-4 py-3 text-white" />
          <ActionButton type="submit">Save Integration</ActionButton>
        </form>
        <div className="space-y-4 rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          {(integrations.data ?? []).map((item) => <div key={item.id} className="rounded-3xl border border-white/10 bg-black/20 p-4"><div className="flex flex-wrap items-center gap-2"><Pill tone={item.enabled ? "success" : "warning"}>{item.kind}</Pill><div className="text-sm font-medium text-white">{item.name}</div></div><div className="mt-2 break-all text-sm text-slate-400">{item.target_url}</div></div>)}
        </div>
      </div>
    </Panel>
  );
}
