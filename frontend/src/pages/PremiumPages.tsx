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

function GuideBlock({ title, body, code }: { title: string; body: string[]; code?: string }) {
  return (
    <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
      <h3 className="font-display text-2xl text-white">{title}</h3>
      <div className="mt-4 space-y-3 text-sm leading-7 text-slate-300">
        {body.map((item) => <p key={item}>{item}</p>)}
      </div>
      {code ? <pre className="mt-4 overflow-auto rounded-3xl border border-white/10 bg-slate-950/80 p-4 text-xs text-emerald-100">{code}</pre> : null}
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
  const [notice, setNotice] = useState("");

  async function refreshApps() {
    setActionError("");
    setNotice("");
    try {
      await api("/api/premium/applications/refresh", { method: "POST" });
      await apps.refetch();
      setNotice("Application inventory refreshed.");
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to refresh applications");
    }
  }

  async function previewExposure() {
    if (!selected || !domain.trim()) return;
    setActionError("");
    setNotice("");
    try {
      const response = await api<{ nginx_config: string; commands: string[] }>("/api/premium/exposure/preview", { method: "POST", body: JSON.stringify({ app_id: selected.id, domain, ssl_mode: sslMode, open_firewall: true }) });
      setPreview(response);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to preview exposure");
    }
  }

  async function applyExposure() {
    if (!selected || !domain.trim()) return;
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setActionError("");
    setNotice("");
    try {
      await api("/api/premium/exposure/apply", {
        method: "POST",
        body: JSON.stringify({ app_id: selected.id, domain, ssl_mode: sslMode, open_firewall: true, confirm_password: confirmPassword }),
      });
      setNotice(`Public exposure applied for ${selected.name}.`);
      await apps.refetch();
      setSelected(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to apply exposure");
    }
  }

  async function removeExposure() {
    if (!selected) return;
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setActionError("");
    setNotice("");
    try {
      await api("/api/premium/exposure/remove", {
        method: "POST",
        body: JSON.stringify({ app_id: selected.id, confirm_password: confirmPassword }),
      });
      setNotice(`Public exposure removed for ${selected.name}.`);
      await apps.refetch();
      setSelected(null);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to remove exposure");
    }
  }

  return (
    <>
      <Panel title="Applications" subtitle="Smart app detection across services, ports, runtimes, and working directories">
        <SectionHeader title="Detected Applications" subtitle="Igris scans live processes and service units to map actual apps running on the host" refresh={refreshApps} />
        <ErrorBanner error={apps.error || actionError} />
        {notice ? <Notice message={notice} /> : null}
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
              {app.public_domain ? <div className="mt-4 rounded-2xl border border-amber-400/20 bg-amber-500/10 px-4 py-3 text-sm text-amber-100">{app.public_domain}</div> : null}
            </button>
          ))}
        </div>
      </Panel>
      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.name ?? "Application"} subtitle={selected ? `${selected.app_type} | ${selected.runtime} | ${selected.path}` : undefined}>
        {selected ? (
          <div className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2">
              <div className="rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">Ports: {selected.ports.length ? selected.ports.join(", ") : "none detected"}</div>
              <div className="rounded-3xl border border-white/10 bg-black/20 p-4 text-sm text-slate-200">Service: {selected.service_name || "unmanaged"}</div>
            </div>
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
                <div className="flex flex-wrap gap-3">
                  <ActionButton onClick={applyExposure}>Apply Exposure</ActionButton>
                  {selected.public_domain ? <ActionButton onClick={removeExposure} className="bg-white/5 text-white hover:bg-white/10">Remove Current Exposure</ActionButton> : null}
                </div>
              </>
            ) : null}
            {!preview && selected.public_domain ? <ActionButton onClick={removeExposure} className="bg-white/5 text-white hover:bg-white/10">Remove Current Exposure</ActionButton> : null}
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
    setActionError("");
    setNotice("");
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
    setActionError("");
    setNotice("");
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

export function GuidePage() {
  const sections = [
    {
      title: "Table Of Contents",
      body: [
        "1. Platform foundations and first login",
        "2. Daily operator workflow",
        "3. Core operations modules",
        "4. AI and command guidance",
        "5. Application discovery, deployments, and public exposure",
        "6. Incidents, explain, scan, and topology",
        "7. Monitoring, alerts, and integrations",
        "8. CLI reference and production habits",
      ],
    },
    {
      title: "Platform Foundations And First Login",
      body: [
        "Install Igris on an Ubuntu or Debian server, then run the setup wizard as root. The setup flow prepares admin access, dashboard binding, monitoring, and alert behavior.",
        "After setup, open the dashboard on your server IP and configured port. The first login should be followed by a quick validation pass across Overview, Services, Alerts, and Settings so you know the service is healthy and the system state looks correct.",
        "Use the CLI for fast checks and automation-friendly workflows, and use the dashboard for investigation, guided operations, and multi-step management flows.",
      ],
      code: "sudo ./install.sh\nsudo igris --setup\nhttp://YOUR_SERVER_IP:2511\nsudo systemctl status igris.service\nigris doctor",
    },
    {
      title: "Daily Operator Workflow",
      body: [
        "A strong production routine starts at Overview. Look at CPU, memory, disk, failed services, pending updates, and the AI monitor summary before you begin any change.",
        "If something looks wrong, move next to Incidents for structured findings, then use Services, Processes, Logs, and Files to drill into the exact failure.",
        "If an app change is required, use Applications to understand ownership and ports, Deployments to deliver code changes, and Public Exposure controls to publish or remove ingress safely.",
        "Resolve alerts only after the underlying problem is actually handled. Igris works best when operators treat it as an operational record, not only a control panel.",
      ],
      code: "Recommended sequence:\nOverview -> Incidents -> Services/Processes/Logs -> Applications -> Deployments -> Alerts",
    },
    {
      title: "Core Operations Modules",
      body: [
        "Overview is the health summary page. Use it to understand the machine quickly: host identity, resource usage, failed services, top processes, and update pressure.",
        "Services is the systemd control room. Use start, stop, restart, reload, enable, disable, and logs when operating service-managed workloads. Restart is best for full process recycle; reload is best when config changes can be applied without a hard restart.",
        "Packages manages apt-backed operations. Review upgradable packages before bulk upgrades, and prefer controlled maintenance windows for package-wide changes on important servers.",
        "Firewall manages UFW with explicit TCP and UDP choice for port rules. Use allow app profile when available, and allow/deny port when you need direct port-level control.",
        "Users, Files, Processes, and Logs form the main troubleshooting toolkit. Users manages accounts and sudo. Files is the safer config editor and explorer. Processes identifies resource-heavy processes. Logs gives system and service context during failures.",
      ],
      code: "Examples:\n- Restart failed unit after log review\n- Open /etc config in Files for quick edit\n- Use Processes to identify CPU spikes\n- Use Logs when failures involve multiple services",
    },
    {
      title: "AI And Command Guidance",
      body: [
        "AI Root Assistant is the guided operations surface. Use it when you want a server-aware answer instead of manually piecing together ports, services, logs, and incidents.",
        "The most effective prompts are concrete and operational. Ask why an app is unreachable, why nginx is failing, what is running on the server, or how to approach a deployment. Avoid vague prompts if you want precise action suggestions.",
        "When the assistant suggests commands, review the exact command, the reason, and the risk level. Igris keeps a history of assistant actions so you can understand what was proposed or executed later.",
        "Console complements the assistant. It is an audited command runner with re-auth, explain, safer-command guidance, and recent command recall. It is best for focused commands, not long-lived interactive shells.",
      ],
      code: "Good assistant prompts:\n- Why is my app not reachable?\n- Check why nginx is failing\n- Explain what is running on this server\n- Help me deploy this Node app\n\nGood console pattern:\n1. Explain command\n2. Review safer version\n3. Run after confirmation",
    },
    {
      title: "Application Discovery, Deployments, And Public Exposure",
      body: [
        "Applications is the smart inventory page. It detects apps from process metadata, service working directories, ports, and project files like package manifests, Python metadata, Docker files, and common startup patterns.",
        "Use Applications when you inherit a server and need to understand what workloads exist, where they live, which service owns them, and whether they are public or private.",
        "Deployments is for managed git-backed delivery. Store repo URL, branch, install/build/restart commands, then run the deploy pipeline. On failure, Igris records logs and attempts to roll back to the previous git revision.",
        "Public Exposure is the nginx-backed publication workflow. Preview config first, confirm domain and SSL mode, then apply. Igris validates nginx before reload and preserves config backups for safer rollback behavior.",
        "A clean production app workflow is: detect app, confirm service binding, save deployment config, run deployment, verify health, then expose publicly only after the app is stable locally.",
      ],
      code: "Recommended app flow:\n1. Applications -> refresh inventory\n2. Deployments -> save repo/build/restart config\n3. Run deploy pipeline\n4. Verify service logs and app port\n5. Exposure preview\n6. Apply exposure",
    },
    {
      title: "Incidents, Explain, Scan, And Topology",
      body: [
        "Incidents is the rule-driven event timeline. It currently tracks failed services, crash loops, high CPU, high memory, disk pressure, nginx validation failures, unstable deployments, and exposed apps that do not answer correctly.",
        "Preview Fix is the safe first move. It shows the commands Igris would run for remediation before you approve execution. This is useful for service restart decisions, nginx reload paths, and resource-pressure investigation.",
        "Explain My Server is the machine narrative page. Use it when you need to brief someone else, onboard yourself to a server, or decide what deserves attention next.",
        "Scan & Fix is currently driven through Explain and Incidents. It is best used as a review pass before maintenance or when a host feels unhealthy but the cause is not immediately obvious.",
        "System Map turns current server facts into a topology-style view across apps, ports, domains, and deployment records. It is especially useful on busy multi-app hosts where ownership and routing are easy to lose track of.",
      ],
      code: "High-signal recovery path:\nOverview -> Incidents -> Preview Fix -> Services/Logs -> Explain -> System Map",
    },
    {
      title: "Monitoring, Alerts, And Integrations",
      body: [
        "Background monitoring currently watches CPU, memory, disk, failed services, incidents, and application inventory refresh. The AI monitor summary on Overview is the fast version of that operational picture.",
        "Alerts stores monitor findings, update events, and manual tests. Treat alert resolution as a real operational acknowledgment, not just a UI cleanup action.",
        "Integrations sends selected events to Discord or generic webhooks. Use this when you want deployment changes, incidents, or exposure updates to be visible outside the dashboard.",
        "For serious environments, configure at least one external integration and use email alerts if that path is part of your workflow. Igris becomes much more reliable as an operational tool when important changes leave the dashboard and reach your team channel.",
      ],
      code: "Recommended alerting pattern:\n1. Keep monitor enabled\n2. Add Discord or webhook integration\n3. Use test alert\n4. Verify delivery path before relying on it in production",
    },
    {
      title: "CLI Reference And Production Habits",
      body: [
        "The CLI is best for quick checks, backups, restores, and script-friendly operational work. It is also the fastest way to inspect health when you are already SSHed into the host.",
        "Use `igris doctor` after install or after big system changes. Use `igris overview` and `igris health` for quick JSON-style state snapshots. Use `igris logs` when you want journal output immediately.",
        "Before risky changes, use `igris backup` to preserve config and runtime data. For update-related work, use `igris update-check` before `igris --update`.",
        "Good production habits inside Igris are simple: inspect before changing, preview before applying, verify after changes, and rely on audit history instead of memory alone.",
      ],
      code: "Useful CLI set:\nigris help\nigris doctor\nigris overview\nigris health\nigris logs 300 igris.service\nigris services failed\nigris packages upgradable\nigris backup ./igris-backup",
    },
  ];

  return (
    <Panel title="Guide" subtitle="Advanced A-to-Z handbook for every major Igris feature with professional usage patterns and production guidance">
      <SectionHeader title="Igris Handbook" subtitle="Learn the platform like an operator: setup, workflows, recovery paths, examples, and production habits." />
      <div className="grid gap-6 xl:grid-cols-[0.55fr,1fr]">
        <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
          <h3 className="font-display text-2xl text-white">Table Of Contents</h3>
          <p className="mt-3 text-sm leading-6 text-slate-400">Use this handbook as a guided operating manual for Igris, not just a feature list. Each section is written to help with real server work.</p>
          <div className="mt-4 space-y-2 text-sm text-slate-300">
            {sections.map((section, index) => (
              <a key={section.title} href={`#guide-${index + 1}`} className="block rounded-2xl border border-white/10 bg-black/20 px-4 py-3 transition hover:bg-white/10">
                {index + 1}. {section.title}
              </a>
            ))}
          </div>
        </div>
        <div className="space-y-6">
          {sections.map((section, index) => (
            <div key={section.title} id={`guide-${index + 1}`}>
              <GuideBlock title={`${index + 1}. ${section.title}`} body={section.body} code={section.code} />
            </div>
          ))}
        </div>
      </div>
    </Panel>
  );
}
