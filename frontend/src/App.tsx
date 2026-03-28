import { FormEvent, useDeferredValue, useEffect, useMemo, useState } from "react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, BellRing, Blocks, FolderTree, Package2, RefreshCw, ScrollText, Server, Shield, TerminalSquare, Users, X } from "lucide-react";
import { api } from "./api/client";
import { MetricCard } from "./components/MetricCard";
import { Panel } from "./components/Panel";
import { useSession } from "./hooks/useSession";
import type { Overview } from "./lib/types";
import { LoginPage } from "./pages/LoginPage";

type ModuleKey = "overview" | "services" | "packages" | "firewall" | "users" | "files" | "processes" | "logs" | "alerts" | "console";
type ServiceItem = { name: string; load: string; active: string; sub: string; description: string };
type PackageSearchItem = { name: string; description: string };
type InstalledPackage = { name: string; version: string; installed: boolean; upgradable: boolean };
type UserItem = { username: string; uid: number; gid: number; home: string; shell: string };
type ProcessItem = { pid: number; name: string; username: string; cpu_percent: number; memory_percent: number; status: string };
type FileItem = { path: string; type: "file" | "directory"; size: number; owner: string | null; group: string | null; permissions: string; modified_at: string | null };
type FileReadResponse = { path: string; content: string; size: number; permissions: string };
type FirewallStatusResponse = { status: string };
type AlertItem = { id: number; level: string; message: string; source: string; resolved: boolean; created_at: string | null };
type FirewallProtocol = "tcp" | "udp";
type UserCreatePreset = "standard" | "operator" | "admin";
type SettingsState = {
  server_port: number;
  bind_address: string;
  session_timeout_minutes: number;
  allow_terminal: boolean;
  docker_enabled: boolean;
  require_reauth_for_dangerous_actions: boolean;
  admin_email: string;
  monitoring_enabled: boolean;
  auto_update_enabled: boolean;
};

const NAV_ITEMS: Array<{ key: ModuleKey; label: string; icon: typeof Activity }> = [
  { key: "overview", label: "Overview", icon: Activity },
  { key: "services", label: "Services", icon: Server },
  { key: "packages", label: "Packages", icon: Package2 },
  { key: "firewall", label: "Firewall", icon: Shield },
  { key: "users", label: "Users", icon: Users },
  { key: "files", label: "Files", icon: FolderTree },
  { key: "processes", label: "Processes", icon: Blocks },
  { key: "logs", label: "Logs", icon: ScrollText },
  { key: "alerts", label: "Alerts", icon: BellRing },
  { key: "console", label: "Console", icon: TerminalSquare },
];

function formatPercent(value: number) {
  return `${Number(value ?? 0).toFixed(0)}%`;
}

function formatUptime(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const days = Math.floor(hours / 24);
  return days > 0 ? `${days}d ${hours % 24}h` : `${hours}h`;
}

function formatBytes(value: number) {
  if (!value) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const index = Math.min(Math.floor(Math.log(value) / Math.log(1024)), units.length - 1);
  const amount = value / 1024 ** index;
  return `${amount.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
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

function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (checked: boolean) => void; label: string; description?: string }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left transition ${checked ? "border-ember-500/45 bg-ember-500/12" : "border-white/10 bg-white/5 hover:bg-white/10"}`}
    >
      <span>
        <span className="block text-sm font-medium text-white">{label}</span>
        {description ? <span className="mt-1 block text-xs text-slate-400">{description}</span> : null}
      </span>
      <span className={`relative h-7 w-12 rounded-full transition ${checked ? "bg-ember-500" : "bg-slate-700"}`}>
        <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${checked ? "left-6" : "left-1"}`} />
      </span>
    </button>
  );
}

function askForConfirmation() {
  return window.prompt("Confirm with your dashboard password");
}

function SectionHeader({ title, subtitle, refresh }: { title: string; subtitle: string; refresh?: () => void }) {
  return (
    <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 className="font-display text-2xl text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
      </div>
      {refresh ? (
        <button type="button" onClick={refresh} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition hover:bg-white/10">
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      ) : null}
    </div>
  );
}

function OverviewPage() {
  const overview = useQuery<Overview>({
    queryKey: ["overview"],
    queryFn: () => api<Overview>("/api/system/overview"),
    refetchInterval: 5000,
    staleTime: 2000,
  });
  const data = overview.data;

  return (
    <div className="space-y-6">
      <Panel title="Overview" subtitle="Live host state from the running Ubuntu node">
        <SectionHeader title="System State" subtitle="Real-time health and identity" refresh={() => overview.refetch()} />
        <ErrorBanner error={overview.error} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="CPU Load" value={data ? formatPercent(data.cpu_usage_percent) : "--"} />
          <MetricCard label="Memory" value={data ? formatPercent(data.ram_usage_percent) : "--"} accent="from-amber-500/25 to-transparent" />
          <MetricCard label="Disk" value={data ? formatPercent(data.disk_usage_percent) : "--"} accent="from-rose-500/25 to-transparent" />
          <MetricCard label="Uptime" value={data ? formatUptime(data.uptime_seconds) : "--"} accent="from-red-500/25 to-transparent" />
        </div>
        {data ? (
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.15fr,0.85fr]">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200"><div className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Hostname</div>{data.hostname}</div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200"><div className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Kernel</div>{data.kernel_version}</div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200"><div className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Local IP</div>{data.local_ip ?? "Unavailable"}</div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200"><div className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Public IP</div>{data.public_ip ?? "Unavailable"}</div>
              <div className="rounded-3xl border border-white/10 bg-white/5 p-4 text-sm text-slate-200 sm:col-span-2"><div className="mb-1 text-xs uppercase tracking-[0.2em] text-slate-500">Operating System</div>{data.os_version}</div>
            </div>
            <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
              <div className="mb-4 flex items-center justify-between">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Pending Updates</p>
                  <p className="mt-2 text-lg text-white">{data.pending_updates.length ? `${data.pending_updates.length} packages need attention` : "System is current"}</p>
                </div>
                <Pill tone={data.pending_updates.length ? "warning" : "success"}>{data.pending_updates.length ? "Updates available" : "Up to date"}</Pill>
              </div>
              <div className="space-y-2 text-sm text-slate-300">
                {data.pending_updates.length ? data.pending_updates.slice(0, 10).map((item) => <div key={item}>{item}</div>) : <div>No upgradable packages reported.</div>}
              </div>
            </div>
          </div>
        ) : null}
        {data ? (
          <div className="mt-6 rounded-[1.75rem] border border-sky-400/20 bg-sky-500/10 p-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.22em] text-sky-200/70">AI Monitor</p>
                <p className="mt-2 text-lg text-white">{data.ai_monitor_summary}</p>
              </div>
              <Pill tone={data.ai_monitor_findings.length ? "warning" : "success"}>{data.ai_monitor_findings.length ? "Attention needed" : "Healthy"}</Pill>
            </div>
            <div className="mt-4 space-y-2 text-sm text-sky-50/90">
              {data.ai_monitor_findings.length ? data.ai_monitor_findings.map((item) => <div key={item}>{item}</div>) : <div>No active monitor findings right now.</div>}
            </div>
          </div>
        ) : null}
      </Panel>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Failed Services" subtitle="Current systemd failures"><pre className="max-h-[20rem] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs text-slate-300">{JSON.stringify(data?.failed_services ?? [], null, 2)}</pre></Panel>
        <Panel title="Top Processes" subtitle="Highest CPU consumers"><pre className="max-h-[20rem] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs text-slate-300">{JSON.stringify(data?.top_processes ?? [], null, 2)}</pre></Panel>
      </div>
    </div>
  );
}

function ServicesPage() {
  const services = useQuery<ServiceItem[]>({
    queryKey: ["services"],
    queryFn: () => api<ServiceItem[]>("/api/services"),
    staleTime: 5000,
    refetchInterval: 10000,
  });
  const [filter, setFilter] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [selected, setSelected] = useState<ServiceItem | null>(null);
  const filtered = useMemo(() => {
    const term = filter.trim().toLowerCase();
    if (!term) return services.data ?? [];
    return (services.data ?? []).filter((item) => item.name.toLowerCase().includes(term) || item.description.toLowerCase().includes(term));
  }, [filter, services.data]);
  const logs = useQuery<{ logs: string }>({
    queryKey: ["service-logs", selected?.name],
    queryFn: () => api<{ logs: string }>(`/api/services/${encodeURIComponent(selected?.name ?? "")}/logs`),
    enabled: Boolean(selected?.name),
  });

  async function runAction(name: string, action: string) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api(`/api/services/${encodeURIComponent(name)}/${action}`, {
        method: "POST",
        body: JSON.stringify({ confirm_password: confirmPassword }),
      });
      setNotice(`Service ${action} completed for ${name}.`);
      await services.refetch();
      if (selected?.name === name) await logs.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Service action failed");
    }
  }

  return (
    <>
      <Panel title="Services" subtitle="Control real systemd units without leaving the dashboard">
        <SectionHeader title="Service Control" subtitle="Inspect service state and open logs in a dedicated panel" refresh={() => services.refetch()} />
        <ErrorBanner error={services.error} />
        {actionError ? <Notice message={actionError} tone="error" /> : null}
        {notice ? <Notice message={notice} /> : null}
        <div className="mb-5 grid gap-3 lg:grid-cols-[1fr,auto]">
          <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter services by name or description" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-ember-500/60" />
          <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">{filtered.length} services</div>
        </div>
        <div className="overflow-hidden rounded-[1.75rem] border border-white/10">
          <div className="max-h-[40rem] overflow-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead className="sticky top-0 bg-[#11161d] text-slate-400">
                <tr>
                  <th className="px-4 py-3">Service</th>
                  <th className="px-4 py-3">Load</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Controls</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((service) => (
                  <tr key={service.name} className="border-t border-white/5">
                    <td className="px-4 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium text-white">{service.name}</div>
                          <div className="mt-1 text-xs text-slate-400">{service.description || "No description"}</div>
                        </div>
                        <button type="button" onClick={() => setSelected(service)} className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white transition hover:bg-white/10">
                          View logs
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-4">{service.load}</td>
                    <td className="px-4 py-4"><Pill tone={service.active === "active" ? "success" : service.active === "failed" ? "danger" : "warning"}>{service.active}/{service.sub}</Pill></td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-2">
                        {["start", "stop", "restart", "reload", "enable", "disable"].map((action) => (
                          <ActionButton key={action} onClick={() => runAction(service.name, action)} className="bg-white/5 text-white hover:bg-white/10">{action}</ActionButton>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Panel>
      <Modal open={Boolean(selected)} onClose={() => setSelected(null)} title={selected?.name ?? "Service logs"} subtitle={selected ? `${selected.active}/${selected.sub} · ${selected.description || "systemd unit"}` : undefined}>
        <div className="mb-4 flex items-center justify-between gap-3">
          <Pill tone={selected?.active === "active" ? "success" : selected?.active === "failed" ? "danger" : "warning"}>{selected?.active}/{selected?.sub}</Pill>
          {selected ? <ActionButton onClick={() => logs.refetch()} className="bg-white/5 text-white hover:bg-white/10">Refresh logs</ActionButton> : null}
        </div>
        <ErrorBanner error={logs.error} />
        <pre className="max-h-[55vh] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{logs.data?.logs ?? "Loading logs..."}</pre>
      </Modal>
    </>
  );
}

function PackagesPage() {
  const [query, setQuery] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState("");
  const [mode, setMode] = useState<"installed" | "search">("installed");
  const installed = useQuery<InstalledPackage[]>({
    queryKey: ["packages-installed"],
    queryFn: () => api<InstalledPackage[]>("/api/packages/installed"),
    staleTime: 10000,
    refetchInterval: 15000,
  });
  const upgradable = useQuery<string[]>({
    queryKey: ["packages-upgradable"],
    queryFn: () => api<string[]>("/api/packages/upgradable"),
    staleTime: 10000,
    refetchInterval: 15000,
  });
  const searchResults = useQuery<PackageSearchItem[]>({
    queryKey: ["packages-search", searchTerm],
    queryFn: () => api<PackageSearchItem[]>(`/api/packages/search?query=${encodeURIComponent(searchTerm)}`),
    enabled: searchTerm.trim().length >= 2,
    staleTime: 20000,
  });
  const installedMap = useMemo(() => new Map((installed.data ?? []).map((item) => [item.name, item])), [installed.data]);

  async function runAction(action: "install" | "remove" | "reinstall", pkg: string) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setBusy(`${action}:${pkg}`);
    setActionError("");
    setNotice("");
    try {
      await api(`/api/packages/${action}`, { method: "POST", body: JSON.stringify({ package: pkg, confirm_password: confirmPassword }) });
      setNotice(`Package ${action === "install" ? "install/update" : action} completed for ${pkg}.`);
      await Promise.all([installed.refetch(), upgradable.refetch(), searchResults.refetch()]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Package action failed");
    } finally {
      setBusy("");
    }
  }

  async function updateIndex() {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setBusy("update-index");
    setActionError("");
    setNotice("");
    try {
      await api("/api/packages/update-index", { method: "POST", body: JSON.stringify({ confirm_password: confirmPassword }) });
      setNotice("Package index updated successfully.");
      await Promise.all([installed.refetch(), upgradable.refetch(), searchResults.refetch()]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Package index update failed");
    } finally {
      setBusy("");
    }
  }

  async function upgradeAll() {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setBusy("upgrade-all");
    setActionError("");
    setNotice("");
    try {
      await api("/api/packages/upgrade-all", { method: "POST", body: JSON.stringify({ confirm_password: confirmPassword }) });
      setNotice("All upgradable packages were upgraded.");
      await Promise.all([installed.refetch(), upgradable.refetch(), searchResults.refetch()]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Package upgrade failed");
    } finally {
      setBusy("");
    }
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    setSearchTerm(query.trim());
    setMode("search");
  }

  return (
    <Panel title="Packages" subtitle="Installed package visibility, updates, and APT operations">
      <SectionHeader title="Package Management" subtitle="Search, audit, and operate on the real package state" refresh={() => Promise.all([installed.refetch(), upgradable.refetch()])} />
      {actionError ? <Notice message={actionError} tone="error" /> : null}
      {notice ? <Notice message={notice} /> : null}
      <div className="mb-5 grid gap-3 xl:grid-cols-[1fr,auto]">
        <form onSubmit={submitSearch} className="flex flex-col gap-3 md:flex-row">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search for a package by name" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-ember-500/60" />
          <ActionButton type="submit">Search</ActionButton>
        </form>
        <div className="flex flex-wrap gap-3">
          <ActionButton type="button" onClick={updateIndex} className="bg-white/5 text-white hover:bg-white/10">{busy === "update-index" ? "Updating..." : "Refresh package index"}</ActionButton>
          <ActionButton type="button" onClick={upgradeAll}>{busy === "upgrade-all" ? "Upgrading..." : "Upgrade all"}</ActionButton>
        </div>
      </div>
      <div className="mb-5 flex flex-wrap gap-3">
        <button type="button" onClick={() => setMode("installed")} className={`rounded-2xl px-4 py-2.5 text-sm transition ${mode === "installed" ? "bg-ember-500 text-white" : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"}`}>Installed packages</button>
        <button type="button" onClick={() => setMode("search")} className={`rounded-2xl px-4 py-2.5 text-sm transition ${mode === "search" ? "bg-ember-500 text-white" : "border border-white/10 bg-white/5 text-slate-300 hover:bg-white/10"}`}>Search results</button>
        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-slate-300">{(upgradable.data ?? []).length} upgradable packages</div>
      </div>
      {mode === "installed" ? (
        <div className="overflow-hidden rounded-[1.75rem] border border-white/10">
          <ErrorBanner error={installed.error} />
          <div className="max-h-[38rem] overflow-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead className="sticky top-0 bg-[#11161d] text-slate-400">
                <tr><th className="px-4 py-3">Package</th><th className="px-4 py-3">Version</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Actions</th></tr>
              </thead>
              <tbody>
                {(installed.data ?? []).map((item) => (
                  <tr key={item.name} className="border-t border-white/5">
                    <td className="px-4 py-4 font-medium text-white">{item.name}</td>
                    <td className="px-4 py-4 text-slate-300">{item.version}</td>
                    <td className="px-4 py-4">{item.upgradable ? <Pill tone="warning">Update available</Pill> : <Pill tone="success">Installed</Pill>}</td>
                    <td className="px-4 py-4">
                      <div className="flex flex-wrap gap-2">
                        {item.upgradable ? <ActionButton onClick={() => runAction("install", item.name)}>{busy === `install:${item.name}` ? "Updating..." : "Update"}</ActionButton> : <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">Current</div>}
                        <ActionButton onClick={() => runAction("reinstall", item.name)} className="bg-white/5 text-white hover:bg-white/10">{busy === `reinstall:${item.name}` ? "..." : "Reinstall"}</ActionButton>
                        <ActionButton onClick={() => runAction("remove", item.name)} className="bg-rose-500/15 text-rose-100 hover:bg-rose-500/25">{busy === `remove:${item.name}` ? "..." : "Remove"}</ActionButton>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <ErrorBanner error={searchResults.error} />
          {!searchTerm ? <Notice message="Search for a package to inspect install status and available actions." tone="info" /> : null}
          {(searchResults.data ?? []).map((item) => {
            const installedInfo = installedMap.get(item.name);
            const isInstalled = Boolean(installedInfo?.installed);
            const needsUpdate = Boolean(installedInfo?.upgradable);
            return (
              <div key={item.name} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-lg font-semibold text-white">{item.name}</h3>
                      {isInstalled ? needsUpdate ? <Pill tone="warning">Installed · update available</Pill> : <Pill tone="success">Installed</Pill> : <Pill>Not installed</Pill>}
                    </div>
                    <p className="text-sm text-slate-400">{item.description}</p>
                    {installedInfo ? <p className="text-xs text-slate-500">Installed version: {installedInfo.version}</p> : null}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {!isInstalled ? <ActionButton onClick={() => runAction("install", item.name)}>{busy === `install:${item.name}` ? "Installing..." : "Install"}</ActionButton> : needsUpdate ? <ActionButton onClick={() => runAction("install", item.name)}>{busy === `install:${item.name}` ? "Updating..." : "Update"}</ActionButton> : <div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">Already current</div>}
                    {isInstalled ? <>
                      <ActionButton onClick={() => runAction("reinstall", item.name)} className="bg-white/5 text-white hover:bg-white/10">{busy === `reinstall:${item.name}` ? "..." : "Reinstall"}</ActionButton>
                      <ActionButton onClick={() => runAction("remove", item.name)} className="bg-rose-500/15 text-rose-100 hover:bg-rose-500/25">{busy === `remove:${item.name}` ? "..." : "Remove"}</ActionButton>
                    </> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}

function ProcessesPage() {
  const [searchInput, setSearchInput] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const deferredSearch = useDeferredValue(searchInput.trim());
  const processes = useQuery<ProcessItem[]>({
    queryKey: ["processes", deferredSearch],
    queryFn: () => api<ProcessItem[]>(`/api/processes${deferredSearch ? `?search=${encodeURIComponent(deferredSearch)}` : ""}`),
    staleTime: 0,
    refetchInterval: 2000,
  });
  const sortedProcesses = useMemo(
    () => [...(processes.data ?? [])].sort((left, right) => (right.cpu_percent - left.cpu_percent) || (right.memory_percent - left.memory_percent)),
    [processes.data],
  );

  async function killProcess(pid: number, signal: "TERM" | "KILL") {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/processes/kill", { method: "POST", body: JSON.stringify({ pid, signal, confirm_password: confirmPassword }) });
      setNotice(`Sent ${signal} to PID ${pid}.`);
      await processes.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Process action failed");
    }
  }

  return (
    <Panel title="Processes" subtitle="Live process inventory from psutil">
      <SectionHeader title="Process List" subtitle="Search and terminate active processes" refresh={() => processes.refetch()} />
      <div className="mb-4 grid gap-3 lg:grid-cols-[1fr,auto]">
        <input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search process name" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none transition placeholder:text-slate-500 focus:border-ember-500/60" />
        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">{sortedProcesses.length} processes</div>
      </div>
      <ErrorBanner error={processes.error} />
      {actionError ? <Notice message={actionError} tone="error" /> : null}
      {notice ? <Notice message={notice} /> : null}
      <div className="max-h-[40rem] overflow-auto rounded-[1.75rem] border border-white/10">
        <table className="min-w-full text-left text-sm text-slate-200">
          <thead className="sticky top-0 bg-[#11161d] text-slate-400">
            <tr><th className="px-4 py-3">PID</th><th className="px-4 py-3">Name</th><th className="px-4 py-3">CPU</th><th className="px-4 py-3">RAM</th><th className="px-4 py-3">User</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Action</th></tr>
          </thead>
          <tbody>
            {sortedProcesses.map((item) => (
              <tr key={item.pid} className="border-t border-white/5">
                <td className="px-4 py-3">{item.pid}</td>
                <td className="px-4 py-3 font-medium text-white">{item.name}</td>
                <td className="px-4 py-3">{formatPercent(item.cpu_percent)}</td>
                <td className="px-4 py-3">{formatPercent(item.memory_percent)}</td>
                <td className="px-4 py-3">{item.username}</td>
                <td className="px-4 py-3"><Pill tone={item.status === "running" ? "success" : "neutral"}>{item.status}</Pill></td>
                <td className="px-4 py-3">
                  <div className="flex flex-wrap gap-2">
                    <ActionButton onClick={() => killProcess(item.pid, "TERM")} className="bg-white/5 text-white hover:bg-white/10">TERM</ActionButton>
                    <ActionButton onClick={() => killProcess(item.pid, "KILL")} className="bg-rose-500/15 text-rose-100 hover:bg-rose-500/25">KILL</ActionButton>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}

function LogsPage() {
  const [showSystemLogs, setShowSystemLogs] = useState(false);
  const [selectedService, setSelectedService] = useState<ServiceItem | null>(null);
  const systemLogs = useQuery<{ logs: string }>({
    queryKey: ["system-logs"],
    queryFn: () => api<{ logs: string }>("/api/logs/system?lines=200"),
    refetchInterval: 5000,
    enabled: showSystemLogs,
  });
  const services = useQuery<ServiceItem[]>({
    queryKey: ["logs-services"],
    queryFn: () => api<ServiceItem[]>("/api/services"),
    staleTime: 5000,
    refetchInterval: 10000,
  });
  const runningServices = useMemo(
    () => (services.data ?? []).filter((item) => item.active === "active").sort((left, right) => left.name.localeCompare(right.name)),
    [services.data],
  );
  const serviceLogs = useQuery<{ logs: string }>({
    queryKey: ["logs-service", selectedService?.name],
    queryFn: () => api<{ logs: string }>(`/api/logs/service/${encodeURIComponent(selectedService?.name ?? "")}?lines=200`),
    enabled: Boolean(selectedService?.name),
    refetchInterval: selectedService ? 5000 : false,
  });

  return (
    <>
      <Panel title="Logs" subtitle="Open system and service journal views from responsive cards">
        <SectionHeader title="Log Browser" subtitle="Click a card to open responsive log popups instead of crowding the page" refresh={() => services.refetch()} />
        <div className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          <button
            type="button"
            onClick={() => setShowSystemLogs(true)}
            className="min-h-[5rem] rounded-2xl border border-rose-500/35 bg-gradient-to-br from-rose-500/18 via-rose-500/10 to-transparent px-4 py-4 text-left text-white transition hover:border-rose-400/55 hover:bg-rose-500/20"
          >
            <div className="text-sm font-semibold">System Logs</div>
            <div className="mt-2 text-xs text-rose-100/80">Open the full journalctl-backed system log viewer.</div>
          </button>
          <button
            type="button"
            onClick={() => services.refetch()}
            className="min-h-[5rem] rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-left text-white transition hover:border-white/20 hover:bg-white/10"
          >
            <div className="text-sm font-semibold">Refresh Services</div>
            <div className="mt-2 text-xs text-slate-400">Reload the list of active services before opening logs.</div>
          </button>
        </div>
        <Panel title="Running Services" subtitle="Click a service card to open its logs in a popup">
          <ErrorBanner error={services.error} />
          <div className="mb-4 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">
            {runningServices.length} running services
          </div>
          <div className="grid max-h-[34rem] grid-cols-2 gap-3 overflow-auto pr-1 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-2">
            {runningServices.map((service) => (
              <button
                key={service.name}
                type="button"
                onClick={() => setSelectedService(service)}
                className="min-h-[4.25rem] rounded-2xl border border-white/10 bg-white/5 px-4 py-4 text-left text-white transition hover:border-ember-500/40 hover:bg-white/10 hover:text-ember-100"
              >
                <div className="truncate text-sm font-medium">{service.name}</div>
              </button>
            ))}
            {!runningServices.length ? (
              <div className="rounded-2xl border border-dashed border-white/10 bg-white/5 px-4 py-5 text-sm text-slate-400">
                No running services found.
              </div>
            ) : null}
          </div>
        </Panel>
      </Panel>
      <Modal
        open={showSystemLogs}
        onClose={() => setShowSystemLogs(false)}
        title="System Logs"
        subtitle="Responsive system journal popup"
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <Pill tone="danger">system</Pill>
          <ActionButton onClick={() => systemLogs.refetch()} className="bg-white/5 text-white hover:bg-white/10">Refresh logs</ActionButton>
        </div>
        <ErrorBanner error={systemLogs.error} />
        <pre className="max-h-[60vh] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{systemLogs.data?.logs ?? "Loading system logs..."}</pre>
      </Modal>
      <Modal
        open={Boolean(selectedService)}
        onClose={() => setSelectedService(null)}
        title={selectedService?.name ?? "Service logs"}
        subtitle="Journal entries for the selected running service"
      >
        <div className="mb-4 flex items-center justify-between gap-3">
          <Pill tone="success">active</Pill>
          {selectedService ? <ActionButton onClick={() => serviceLogs.refetch()} className="bg-white/5 text-white hover:bg-white/10">Refresh logs</ActionButton> : null}
        </div>
        <ErrorBanner error={serviceLogs.error} />
        <pre className="max-h-[60vh] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{serviceLogs.data?.logs ?? "Loading logs..."}</pre>
      </Modal>
    </>
  );
}

function FirewallPage() {
  const firewall = useQuery<FirewallStatusResponse>({
    queryKey: ["firewall"],
    queryFn: () => api<FirewallStatusResponse>("/api/firewall/status"),
    staleTime: 5000,
    refetchInterval: 10000,
  });
  const [port, setPort] = useState("2511");
  const [protocol, setProtocol] = useState<FirewallProtocol>("tcp");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function protectedPost(path: string, body: Record<string, unknown> = {}) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api(path, { method: "POST", body: JSON.stringify({ ...body, confirm_password: confirmPassword }) });
      setNotice("Firewall update applied successfully.");
      await firewall.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Firewall update failed");
    }
  }

  return (
    <Panel title="Firewall" subtitle="UFW-backed firewall management">
      <SectionHeader title="UFW Status" subtitle="Enable, disable, and update the active rule set" refresh={() => firewall.refetch()} />
      <ErrorBanner error={firewall.error} />
      {actionError ? <Notice message={actionError} tone="error" /> : null}
      {notice ? <Notice message={notice} /> : null}
      <pre className="mb-6 max-h-[22rem] overflow-auto rounded-3xl border border-white/8 bg-slate-950/80 p-4 text-xs leading-6 text-slate-300">{firewall.data?.status ?? ""}</pre>
      <div className="grid gap-4 xl:grid-cols-[220px,1fr]">
        <div className="flex gap-3">
          <ActionButton onClick={() => protectedPost("/api/firewall/enable")}>Enable</ActionButton>
          <ActionButton onClick={() => protectedPost("/api/firewall/disable")} className="bg-white/5 text-white hover:bg-white/10">Disable</ActionButton>
        </div>
        <div className="flex flex-col gap-3 md:flex-row">
          <input value={port} onChange={(event) => setPort(event.target.value)} className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white md:w-40" />
          <div className="grid grid-cols-2 gap-2 rounded-2xl border border-white/10 bg-white/5 p-1">
            {(["tcp", "udp"] as FirewallProtocol[]).map((item) => (
              <button
                key={item}
                type="button"
                onClick={() => setProtocol(item)}
                className={`rounded-xl px-4 py-3 text-sm font-medium capitalize transition ${protocol === item ? "bg-ember-500 text-white" : "text-slate-300 hover:bg-white/10"}`}
              >
                {item}
              </button>
            ))}
          </div>
          <ActionButton onClick={() => protectedPost("/api/firewall/allow-port", { port: Number(port), protocol })}>Allow {protocol.toUpperCase()}</ActionButton>
          <ActionButton onClick={() => protectedPost("/api/firewall/deny-port", { port: Number(port), protocol })} className="bg-white/5 text-white hover:bg-white/10">Deny {protocol.toUpperCase()}</ActionButton>
        </div>
      </div>
    </Panel>
  );
}

function UsersPage() {
  const users = useQuery<UserItem[]>({
    queryKey: ["users"],
    queryFn: () => api<UserItem[]>("/api/users"),
    staleTime: 8000,
    refetchInterval: 15000,
  });
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [preset, setPreset] = useState<UserCreatePreset>("standard");
  const [createForm, setCreateForm] = useState({ username: "", shell: "/bin/bash", password: "", sudo: false });
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  function applyPreset(nextPreset: UserCreatePreset) {
    setPreset(nextPreset);
    setCreateForm((current) => ({
      ...current,
      shell: nextPreset === "standard" ? "/bin/bash" : "/bin/bash",
      sudo: nextPreset === "admin",
    }));
  }

  async function protectedUserAction(path: string, body: Record<string, unknown>) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api(path, { method: "POST", body: JSON.stringify({ ...body, confirm_password: confirmPassword }) });
      setNotice("User operation completed successfully.");
      await users.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "User operation failed");
    }
  }

  async function createUser(event: FormEvent) {
    event.preventDefault();
    await protectedUserAction("/api/users/create", createForm);
    setCreateForm({ username: "", shell: "/bin/bash", password: "", sudo: false });
    setPreset("standard");
    setShowCreateModal(false);
  }

  return (
    <>
      <Panel title="Users" subtitle="Local Linux account management">
        <div className="mb-6 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <h2 className="font-display text-2xl text-white">Accounts</h2>
            <p className="mt-2 text-sm text-slate-400">View and operate on system users</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <ActionButton onClick={() => setShowCreateModal(true)}>Create User</ActionButton>
            <button type="button" onClick={() => users.refetch()} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2.5 text-sm text-white transition hover:bg-white/10">
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
        <ErrorBanner error={users.error} />
        {actionError ? <Notice message={actionError} tone="error" /> : null}
        {notice ? <Notice message={notice} /> : null}
        <div className="max-h-[38rem] overflow-auto rounded-[1.75rem] border border-white/10">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="sticky top-0 bg-[#11161d] text-slate-400">
              <tr><th className="px-4 py-3">User</th><th className="px-4 py-3">Home</th><th className="px-4 py-3">Shell</th><th className="px-4 py-3">Actions</th></tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((item) => (
                <tr key={item.username} className="border-t border-white/5">
                  <td className="px-4 py-4"><div className="font-medium text-white">{item.username}</div><div className="mt-1 text-xs text-slate-500">UID {item.uid} · GID {item.gid}</div></td>
                  <td className="px-4 py-4">{item.home}</td>
                  <td className="px-4 py-4">{item.shell}</td>
                  <td className="px-4 py-4">
                    <div className="flex flex-wrap gap-2">
                      <ActionButton onClick={() => protectedUserAction("/api/users/lock", { username: item.username })} className="bg-white/5 text-white hover:bg-white/10" disabled={item.username === "root"}>Lock</ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/unlock", { username: item.username })} className="bg-white/5 text-white hover:bg-white/10">Unlock</ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/set-sudo", { username: item.username, enabled: true })} className="bg-white/5 text-white hover:bg-white/10">Grant sudo</ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/set-sudo", { username: item.username, enabled: false })} className="bg-white/5 text-white hover:bg-white/10">Revoke sudo</ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/delete", { username: item.username })} className="bg-rose-500/15 text-rose-100 hover:bg-rose-500/25" disabled={item.username === "root"}>Delete</ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Modal open={showCreateModal} onClose={() => setShowCreateModal(false)} title="Create User" subtitle="Provision a new local system account with a permission preset">
        <form onSubmit={createUser} className="space-y-5">
          <div className="grid gap-3 md:grid-cols-3">
            {([
              { key: "standard", title: "Standard", description: "Regular login user without sudo." },
              { key: "operator", title: "Operator", description: "Shell access for operations without sudo." },
              { key: "admin", title: "Admin", description: "Full shell access with sudo enabled." },
            ] as Array<{ key: UserCreatePreset; title: string; description: string }>).map((item) => (
              <button
                key={item.key}
                type="button"
                onClick={() => applyPreset(item.key)}
                className={`rounded-[1.5rem] border p-4 text-left transition ${preset === item.key ? "border-ember-500/50 bg-ember-500/12" : "border-white/10 bg-white/5 hover:bg-white/10"}`}
              >
                <div className="text-sm font-semibold text-white">{item.title}</div>
                <div className="mt-2 text-xs leading-6 text-slate-400">{item.description}</div>
              </button>
            ))}
          </div>
          <input value={createForm.username} onChange={(event) => setCreateForm((current) => ({ ...current, username: event.target.value }))} placeholder="Username" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <input value={createForm.shell} onChange={(event) => setCreateForm((current) => ({ ...current, shell: event.target.value }))} placeholder="/bin/bash" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <input type="password" value={createForm.password} onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))} placeholder="Initial password" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <Toggle checked={createForm.sudo} onChange={(checked) => setCreateForm((current) => ({ ...current, sudo: checked }))} label="Grant sudo access" description="Preset-aware permission toggle that you can still adjust manually before creating the user." />
          <div className="flex justify-end gap-3">
            <ActionButton type="button" onClick={() => setShowCreateModal(false)} className="bg-white/5 text-white hover:bg-white/10">Cancel</ActionButton>
            <ActionButton type="submit">Create User</ActionButton>
          </div>
        </form>
      </Modal>
    </>
  );
}

function FilesPage() {
  const [currentPath, setCurrentPath] = useState("/etc");
  const [selectedFile, setSelectedFile] = useState("");
  const [editorContent, setEditorContent] = useState("");
  const [newDir, setNewDir] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const files = useQuery<FileItem[]>({
    queryKey: ["files", currentPath],
    queryFn: () => api<FileItem[]>(`/api/files/list?path=${encodeURIComponent(currentPath)}`),
    staleTime: 3000,
    refetchInterval: 10000,
  });
  const fileContents = useQuery<FileReadResponse>({
    queryKey: ["file-read", selectedFile],
    queryFn: () => api<FileReadResponse>(`/api/files/read?path=${encodeURIComponent(selectedFile)}`),
    enabled: Boolean(selectedFile),
  });

  useEffect(() => {
    if (fileContents.data) setEditorContent(fileContents.data.content);
  }, [fileContents.data]);

  async function writeFile() {
    if (!selectedFile) return;
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/write", { method: "POST", body: JSON.stringify({ path: selectedFile, content: editorContent, create_backup: true, confirm_password: confirmPassword }) });
      setNotice(`Saved ${selectedFile}.`);
      await Promise.all([fileContents.refetch(), files.refetch()]);
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "File save failed");
    }
  }

  async function deletePath(path: string) {
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/delete", { method: "POST", body: JSON.stringify({ path, confirm_password: confirmPassword }) });
      setNotice(`Deleted ${path}.`);
      if (selectedFile === path) {
        setSelectedFile("");
        setEditorContent("");
      }
      await files.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Delete failed");
    }
  }

  async function createDirectory(event: FormEvent) {
    event.preventDefault();
    const confirmPassword = askForConfirmation();
    if (!confirmPassword) return;
    const target = newDir.startsWith("/") ? newDir : `${currentPath.replace(/\/$/, "")}/${newDir}`;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/mkdir", { method: "POST", body: JSON.stringify({ path: target, confirm_password: confirmPassword }) });
      setNotice(`Created directory ${target}.`);
      setNewDir("");
      await files.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Directory creation failed");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1fr,1fr]">
      <Panel title="Files" subtitle="Bounded file management for common admin roots">
        <SectionHeader title="Browser" subtitle="Navigate common system paths and open text files" refresh={() => files.refetch()} />
        <div className="mb-4 flex gap-3">
          <input value={currentPath} onChange={(event) => setCurrentPath(event.target.value)} className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton type="button" onClick={() => files.refetch()}>Open</ActionButton>
        </div>
        <form onSubmit={createDirectory} className="mb-4 flex gap-3">
          <input value={newDir} onChange={(event) => setNewDir(event.target.value)} placeholder="New directory name or path" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton type="submit" className="bg-white/5 text-white hover:bg-white/10">Create Dir</ActionButton>
        </form>
        <ErrorBanner error={files.error} />
        {actionError ? <Notice message={actionError} tone="error" /> : null}
        {notice ? <Notice message={notice} /> : null}
        <div className="max-h-[36rem] overflow-auto rounded-[1.75rem] border border-white/10">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="sticky top-0 bg-[#11161d] text-slate-400">
              <tr><th className="px-4 py-3">Path</th><th className="px-4 py-3">Type</th><th className="px-4 py-3">Size</th><th className="px-4 py-3">Permissions</th><th className="px-4 py-3">Actions</th></tr>
            </thead>
            <tbody>
              {(files.data ?? []).map((item) => (
                <tr key={item.path} className="border-t border-white/5">
                  <td className="px-4 py-3">
                    <button type="button" onClick={() => {
                      if (item.type === "directory") {
                        setCurrentPath(item.path);
                        setSelectedFile("");
                        setEditorContent("");
                      } else {
                        setSelectedFile(item.path);
                      }
                    }} className="text-left text-white transition hover:text-ember-300">{item.path}</button>
                  </td>
                  <td className="px-4 py-3">{item.type}</td>
                  <td className="px-4 py-3">{formatBytes(item.size)}</td>
                  <td className="px-4 py-3">{item.permissions}</td>
                  <td className="px-4 py-3"><ActionButton onClick={() => deletePath(item.path)} className="bg-rose-500/15 text-rose-100 hover:bg-rose-500/25">Delete</ActionButton></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Editor" subtitle="Read and write text files with backup safety">
        <div className="mb-3 text-sm text-slate-400">{selectedFile || "Select a file from the browser"}</div>
        <ErrorBanner error={fileContents.error} />
        <textarea value={editorContent} onChange={(event) => setEditorContent(event.target.value)} className="min-h-[30rem] w-full rounded-3xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-100" />
        <div className="mt-4 flex flex-col gap-3 lg:flex-row lg:items-center">
          <ActionButton onClick={writeFile} disabled={!selectedFile}>Save File</ActionButton>
          {selectedFile ? <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">Backups are written as `*.bak` before overwrite.</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function AlertsPage() {
  const alerts = useQuery<AlertItem[]>({
    queryKey: ["alerts"],
    queryFn: () => api<AlertItem[]>("/api/alerts"),
    staleTime: 5000,
    refetchInterval: 10000,
  });
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function createTestAlert() {
    setNotice("");
    setActionError("");
    try {
      await api<{ message: string }>("/api/alerts/test", { method: "POST" });
      setNotice("Test alert created.");
      await alerts.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to create test alert");
    }
  }

  async function resolveAlert(alertId: number) {
    setNotice("");
    setActionError("");
    try {
      const response = await api<{ message: string }>(`/api/alerts/${alertId}/resolve`, { method: "POST" });
      setNotice(response.message);
      await alerts.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to resolve alert");
    }
  }

  async function clearResolvedAlerts() {
    setNotice("");
    setActionError("");
    try {
      const response = await api<{ message: string }>("/api/alerts/clear-resolved", { method: "POST" });
      setNotice(response.message);
      await alerts.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Unable to clear resolved alerts");
    }
  }

  return (
    <Panel title="Alerts" subtitle="Server monitor, update watch, and manual alert history">
      <SectionHeader title="Alert Center" subtitle="Review server health warnings, update notices, and email-triggered events" refresh={() => alerts.refetch()} />
      <ErrorBanner error={alerts.error} />
      {actionError ? <Notice message={actionError} tone="error" /> : null}
      {notice ? <Notice message={notice} /> : null}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <ActionButton onClick={createTestAlert}>Create Test Alert</ActionButton>
        <ActionButton onClick={clearResolvedAlerts} className="bg-white/5 text-white hover:bg-white/10">Clear Resolved</ActionButton>
        <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">{alerts.data?.length ?? 0} recent alerts</div>
      </div>
      <div className="space-y-3">
        {(alerts.data ?? []).map((item) => (
          <div key={item.id} className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
            <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <Pill tone={item.level === "critical" ? "danger" : item.level === "warning" ? "warning" : "success"}>{item.level}</Pill>
                  <Pill tone="neutral">{item.source}</Pill>
                  {item.resolved ? <Pill tone="success">resolved</Pill> : <Pill tone="warning">open</Pill>}
                </div>
                <p className="mt-3 text-sm leading-6 text-slate-100">{item.message}</p>
              </div>
              <div className="flex flex-col items-start gap-3 lg:items-end">
                <div className="text-xs text-slate-500">{item.created_at ? new Date(item.created_at).toLocaleString() : "Unknown time"}</div>
                {!item.resolved ? <ActionButton onClick={() => resolveAlert(item.id)} className="bg-white/5 text-white hover:bg-white/10">Resolve</ActionButton> : null}
              </div>
            </div>
          </div>
        ))}
        {!alerts.data?.length ? <div className="rounded-[1.75rem] border border-white/10 bg-white/5 p-5 text-sm text-slate-300">No alerts yet. Igris will add entries here when the monitor or repo watcher finds something.</div> : null}
      </div>
    </Panel>
  );
}

function ConsolePage() {
  const [command, setCommand] = useState("");
  const [output, setOutput] = useState("Console ready.\n");
  const [running, setRunning] = useState(false);
  const [actionError, setActionError] = useState("");
  const [consoleUnlocked, setConsoleUnlocked] = useState(false);
  const settings = useQuery<SettingsState>({
    queryKey: ["console-settings"],
    queryFn: () => api<SettingsState>("/api/settings"),
    staleTime: 60000,
  });

  async function sendCommand(event: FormEvent) {
    event.preventDefault();
    const trimmed = command.trim();
    if (!trimmed || running) return;
    setRunning(true);
    setActionError("");
    setOutput((current) => `${current}\n$ ${trimmed}\n`);
    try {
      let response: { command: string; stdout: string; stderr: string; exit_code: number };
      try {
        response = await api<{ command: string; stdout: string; stderr: string; exit_code: number }>("/api/terminal/exec", {
          method: "POST",
          body: JSON.stringify({ command: trimmed }),
        });
      } catch (error) {
        const message = error instanceof Error ? error.message : "Command execution failed";
        if (!/confirm|expired|password/i.test(message)) {
          throw error;
        }
        const confirmPassword = askForConfirmation();
        if (!confirmPassword) {
          setActionError("Command cancelled. Console remains locked until you confirm once.");
          setOutput((current) => `${current}[cancelled] confirmation required\n`);
          return;
        }
        response = await api<{ command: string; stdout: string; stderr: string; exit_code: number }>("/api/terminal/exec", {
          method: "POST",
          body: JSON.stringify({ command: trimmed, confirm_password: confirmPassword }),
        });
        setConsoleUnlocked(true);
      }
      const stdout = response.stdout || "";
      const stderr = response.stderr ? `\n[stderr]\n${response.stderr}` : "";
      setOutput((current) => `${current}${stdout}${stderr}\n[exit ${response.exit_code}]\n`);
    } catch (error) {
      const message = error instanceof Error ? error.message : "Command execution failed";
      setActionError(message);
      setOutput((current) => `${current}[error] ${message}\n`);
    } finally {
      setRunning(false);
    }
    setCommand("");
  }

  return (
    <Panel title="Console" subtitle="Authenticated audited command execution without a persistent shell session">
      <SectionHeader title="Console" subtitle="Commands run on the server and return live output when the command completes." />
      <ErrorBanner error={settings.error} />
      {actionError ? <Notice message={actionError} tone="error" /> : null}
      <div className="mb-4 flex items-center gap-3">
        <Pill tone={settings.data?.allow_terminal ? "success" : "warning"}>{settings.data?.allow_terminal ? "Enabled" : "Disabled"}</Pill>
        <Pill tone={consoleUnlocked ? "success" : "warning"}>{consoleUnlocked ? "Unlocked for 10 min" : "Locked"}</Pill>
        <div className="text-sm text-slate-400">Persistent shell mode was removed from the dashboard so opening Console can no longer wedge the whole service.</div>
      </div>
      <pre className="min-h-[26rem] overflow-auto rounded-3xl border border-white/8 bg-slate-950/90 p-4 font-mono text-xs leading-6 text-slate-200">{output}</pre>
      <form onSubmit={sendCommand} className="mt-4 flex flex-col gap-3 md:flex-row">
        <input value={command} onChange={(event) => setCommand(event.target.value)} placeholder="Enter a shell command" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" disabled={!settings.data?.allow_terminal || running} />
        <ActionButton type="submit" disabled={!settings.data?.allow_terminal || running}>{running ? "Running..." : "Run command"}</ActionButton>
      </form>
    </Panel>
  );
}

function Dashboard() {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState<ModuleKey>("overview");
  const settings = useQuery<SettingsState>({ queryKey: ["settings"], queryFn: () => api<SettingsState>("/api/settings"), staleTime: 60000 });
  const overview = useQuery<Overview>({ queryKey: ["header-overview"], queryFn: () => api<Overview>("/api/system/overview"), refetchInterval: 5000, staleTime: 2000 });
  const topStatus = useMemo(() => !overview.data ? "Syncing node state" : `${overview.data.hostname} · ${overview.data.os_version}`, [overview.data]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    await queryClient.invalidateQueries({ queryKey: ["session"] });
  }

  const content =
    current === "overview"
      ? <OverviewPage />
      : current === "services"
        ? <ServicesPage />
        : current === "packages"
          ? <PackagesPage />
          : current === "firewall"
            ? <FirewallPage />
            : current === "users"
              ? <UsersPage />
                : current === "files"
                  ? <FilesPage />
                  : current === "processes"
                    ? <ProcessesPage />
                    : current === "logs"
                      ? <LogsPage />
                      : current === "alerts"
                        ? <AlertsPage />
                        : <ConsolePage />;

  return (
    <div className="min-h-screen bg-igris-glow text-slate-100">
      <div className="mx-auto grid min-h-screen w-full max-w-[1920px] gap-6 px-3 py-3 lg:grid-cols-[260px,minmax(0,1fr)] xl:grid-cols-[280px,minmax(0,1fr)] sm:px-4 sm:py-4 lg:px-6 lg:py-6">
        <aside className="animate-igris-rise rounded-[2rem] border border-white/10 bg-black/35 p-4 shadow-panel backdrop-blur-xl sm:p-5">
          <div className="mb-8 rounded-[1.75rem] border border-white/10 bg-white/5 p-5">
            <p className="text-xs uppercase tracking-[0.35em] text-ember-300">Igris v2</p>
            <h1 className="mt-4 font-display text-3xl text-white">Server Command v2</h1>
            <p className="mt-3 text-sm text-slate-400">A sharper control surface for live Ubuntu operations.</p>
          </div>
          <nav className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-1">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = current === item.key;
              return (
                <button key={item.key} type="button" onClick={() => setCurrent(item.key)} className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${active ? "bg-ember-500/18 text-white ring-1 ring-ember-400/35" : "text-slate-300 hover:bg-white/5"}`}>
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>
        <main className="space-y-6">
          <header className="animate-igris-rise rounded-[2rem] border border-white/10 bg-black/30 p-4 shadow-panel backdrop-blur-xl sm:p-5">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-ember-300">Node Status</p>
                <h2 className="mt-3 text-3xl font-semibold text-white">{topStatus}</h2>
                <p className="mt-2 text-sm text-slate-400">Dashboard port {settings.data?.server_port ?? 2511}, terminal {settings.data?.allow_terminal ? "enabled" : "disabled"}, monitor {settings.data?.monitoring_enabled ? "enabled" : "disabled"}.</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">Secure session active</div>
                <button type="button" onClick={logout} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white transition hover:bg-white/10">Sign out</button>
              </div>
            </div>
          </header>
          {content}
        </main>
      </div>
    </div>
  );
}

export default function App() {
  const session = useSession();
  const queryClient = useQueryClient();
  if (session.isLoading) return <div className="flex min-h-screen items-center justify-center bg-igris-glow text-slate-200">Synchronizing secure session...</div>;
  if (session.isError) return <LoginPage onLogin={() => queryClient.invalidateQueries({ queryKey: ["session"] })} />;
  return <Dashboard />;
}
