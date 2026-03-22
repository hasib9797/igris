import { FormEvent, useEffect, useMemo, useState } from "react";
import type { ButtonHTMLAttributes, ReactElement } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  Blocks,
  FolderTree,
  Package2,
  RefreshCw,
  ScrollText,
  Server,
  Shield,
  Users,
} from "lucide-react";
import { api } from "./api/client";
import { MetricCard } from "./components/MetricCard";
import { Panel } from "./components/Panel";
import { useSession } from "./hooks/useSession";
import type { Overview } from "./lib/types";
import { LoginPage } from "./pages/LoginPage";

type ModuleKey =
  | "overview"
  | "services"
  | "packages"
  | "firewall"
  | "users"
  | "files"
  | "processes"
  | "logs";

type ServiceItem = {
  name: string;
  load: string;
  active: string;
  sub: string;
  description: string;
};

type PackageItem = {
  name: string;
  description: string;
};

type UserItem = {
  username: string;
  uid: number;
  gid: number;
  home: string;
  shell: string;
};

type ProcessItem = {
  pid: number;
  name: string;
  username: string;
  cpu_percent: number;
  memory_percent: number;
  status: string;
};

type FileItem = {
  path: string;
  type: "file" | "directory";
  size: number;
  owner: string | null;
  group: string | null;
  permissions: string;
  modified_at: string | null;
};

type FileReadResponse = {
  path: string;
  content: string;
  size: number;
  permissions: string;
};

type FirewallStatusResponse = {
  status: string;
};

type SettingsState = {
  server_port: number;
  bind_address: string;
  session_timeout_minutes: number;
  allow_terminal: boolean;
  docker_enabled: boolean;
  require_reauth_for_dangerous_actions: boolean;
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
];

function formatPercent(value: number) {
  return `${Number(value ?? 0).toFixed(0)}%`;
}

function formatUptime(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const days = Math.floor(hours / 24);
  return days > 0 ? `${days}d ${hours % 24}h` : `${hours}h`;
}

function JsonBlock({ value }: { value: unknown }) {
  return (
    <pre className="max-h-[24rem] overflow-auto rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-xs text-slate-300">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  if (!error) return null;
  const message = error instanceof Error ? error.message : "Request failed";
  return <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{message}</div>;
}

function NoticeBanner({ message, tone = "success" }: { message: string; tone?: "success" | "error" }) {
  const classes =
    tone === "error"
      ? "border-rose-500/40 bg-rose-500/10 text-rose-200"
      : "border-emerald-400/30 bg-emerald-500/10 text-emerald-100";
  return <div className={`rounded-2xl border px-4 py-3 text-sm ${classes}`}>{message}</div>;
}

function ActionButton(props: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`rounded-xl px-3 py-2 text-sm font-medium transition disabled:opacity-50 ${props.className ?? "bg-ember-500 text-white hover:bg-ember-400"}`}
    />
  );
}

function askForConfirmation() {
  return window.prompt("Confirm with your dashboard password");
}

function SectionHeader({ title, subtitle, refresh }: { title: string; subtitle: string; refresh?: () => void }) {
  return (
    <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 className="font-display text-2xl text-white">{title}</h2>
        <p className="mt-2 text-sm text-slate-400">{subtitle}</p>
      </div>
      {refresh ? (
        <button type="button" onClick={refresh} className="inline-flex items-center gap-2 rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white hover:bg-white/10">
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
    refetchInterval: 20000,
  });
  const data = overview.data;

  return (
    <div className="space-y-6">
      <Panel title="Overview" subtitle="Live server inventory from the running backend">
        <SectionHeader title="System State" subtitle="Real-time metrics and host identity" refresh={() => overview.refetch()} />
        <ErrorBanner error={overview.error} />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <MetricCard label="CPU Load" value={data ? formatPercent(data.cpu_usage_percent) : "--"} />
          <MetricCard label="Memory" value={data ? formatPercent(data.ram_usage_percent) : "--"} accent="from-amber-500/30 to-transparent" />
          <MetricCard label="Disk" value={data ? formatPercent(data.disk_usage_percent) : "--"} accent="from-rose-500/30 to-transparent" />
          <MetricCard label="Uptime" value={data ? formatUptime(data.uptime_seconds) : "--"} accent="from-red-500/30 to-transparent" />
        </div>
        {data ? (
          <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr,0.8fr]">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Hostname: {data.hostname}</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Kernel: {data.kernel_version}</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Local IP: {data.local_ip ?? "Unavailable"}</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Public IP: {data.public_ip ?? "Unavailable"}</div>
              <div className="rounded-2xl border border-white/10 bg-white/5 p-4 sm:col-span-2">OS: {data.os_version}</div>
            </div>
            <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
              <p className="mb-3 text-sm uppercase tracking-[0.2em] text-slate-400">Pending Updates</p>
              <div className="space-y-2 text-sm text-slate-300">
                {data.pending_updates.length ? data.pending_updates.slice(0, 10).map((item) => <div key={item}>{item}</div>) : <div>No upgradable packages reported.</div>}
              </div>
            </div>
          </div>
        ) : null}
      </Panel>
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Failed Services" subtitle="Current systemd failures">
          <JsonBlock value={data?.failed_services ?? []} />
        </Panel>
        <Panel title="Top Processes" subtitle="Highest CPU consumers">
          <JsonBlock value={data?.top_processes ?? []} />
        </Panel>
      </div>
    </div>
  );
}

function ServicesPage() {
  const services = useQuery<ServiceItem[]>({
    queryKey: ["services"],
    queryFn: () => api<ServiceItem[]>("/api/services"),
  });
  const [selected, setSelected] = useState("");
  const [filter, setFilter] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const logs = useQuery<{ logs: string }>({
    queryKey: ["service-logs", selected],
    queryFn: () => api<{ logs: string }>(`/api/services/${encodeURIComponent(selected)}/logs`),
    enabled: Boolean(selected),
  });

  async function runAction(name: string, action: string) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api(`/api/services/${encodeURIComponent(name)}/${action}`, {
        method: "POST",
        body: JSON.stringify({ confirm_password }),
      });
      setNotice(`Service ${action} completed for ${name}.`);
      await services.refetch();
      if (selected === name) await logs.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Service action failed");
    }
  }

  const filtered = (services.data ?? []).filter((item) => item.name.toLowerCase().includes(filter.toLowerCase()));

  return (
    <Panel title="Services" subtitle="Manage real systemd units">
      <SectionHeader title="Service Control" subtitle="Start, stop, restart, enable, and inspect services" refresh={() => services.refetch()} />
      <ErrorBanner error={services.error} />
      {actionError ? <NoticeBanner message={actionError} tone="error" /> : null}
      {notice ? <NoticeBanner message={notice} /> : null}
      <input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder="Filter services" className="mb-4 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
      <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
        <div className="overflow-hidden rounded-3xl border border-white/10">
          <div className="max-h-[32rem] overflow-auto">
            <table className="min-w-full text-left text-sm text-slate-200">
              <thead className="bg-white/5 text-slate-400">
                <tr>
                  <th className="px-4 py-3">Service</th>
                  <th className="px-4 py-3">State</th>
                  <th className="px-4 py-3">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((service) => (
                  <tr key={service.name} className="border-t border-white/5">
                    <td className="px-4 py-3">
                      <button type="button" onClick={() => setSelected(service.name)} className="text-left text-white hover:text-ember-300">
                        <div>{service.name}</div>
                        <div className="text-xs text-slate-400">{service.description}</div>
                      </button>
                    </td>
                    <td className="px-4 py-3">{service.active}/{service.sub}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        {["start", "stop", "restart", "enable", "disable"].map((action) => (
                          <ActionButton key={action} onClick={() => runAction(service.name, action)} className="bg-white/5 text-white hover:bg-white/10">
                            {action}
                          </ActionButton>
                        ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="rounded-3xl border border-white/10 bg-white/5 p-4">
          <p className="mb-2 text-sm uppercase tracking-[0.2em] text-slate-400">Selected Logs</p>
          <p className="mb-3 text-white">{selected || "Choose a service"}</p>
          <ErrorBanner error={logs.error} />
          <pre className="max-h-[26rem] overflow-auto rounded-2xl bg-slate-950/80 p-4 text-xs text-slate-300">{logs.data?.logs ?? "No logs loaded."}</pre>
        </div>
      </div>
    </Panel>
  );
}

function PackagesPage() {
  const upgradable = useQuery<string[]>({
    queryKey: ["packages-upgradable"],
    queryFn: () => api<string[]>("/api/packages/upgradable"),
  });
  const [query, setQuery] = useState("");
  const [searchResults, setSearchResults] = useState<PackageItem[]>([]);
  const [searchError, setSearchError] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");

  async function search(event: FormEvent) {
    event.preventDefault();
    if (query.trim().length < 2) return;
    try {
      setSearchError("");
      setSearchResults(await api<PackageItem[]>(`/api/packages/search?query=${encodeURIComponent(query.trim())}`));
    } catch (error) {
      setSearchError(error instanceof Error ? error.message : "Search failed");
    }
  }

  async function runAction(action: "install" | "remove" | "reinstall", pkg: string) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setBusy(`${action}:${pkg}`);
    setNotice("");
    try {
      await api(`/api/packages/${action}`, {
        method: "POST",
        body: JSON.stringify({ package: pkg, confirm_password }),
      });
      setNotice(`Package ${action} completed for ${pkg}.`);
      await upgradable.refetch();
    } finally {
      setBusy("");
    }
  }

  async function updateIndex() {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setBusy("update-index");
    setNotice("");
    try {
      await api("/api/packages/update-index", {
        method: "POST",
        body: JSON.stringify({ confirm_password }),
      });
      setNotice("Package index updated successfully.");
      await upgradable.refetch();
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.1fr,0.9fr]">
      <Panel title="Packages" subtitle="Search and manage APT packages">
        <SectionHeader title="Package Search" subtitle="Real apt-cache and apt-get operations" refresh={() => upgradable.refetch()} />
        <form onSubmit={search} className="mb-4 flex gap-3">
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search packages" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton type="submit">Search</ActionButton>
          <ActionButton type="button" onClick={updateIndex} className="bg-white/5 text-white hover:bg-white/10">
            {busy === "update-index" ? "Updating..." : "Update Index"}
          </ActionButton>
        </form>
        {searchError ? <ErrorBanner error={new Error(searchError)} /> : null}
        {notice ? <NoticeBanner message={notice} /> : null}
        <div className="space-y-3">
          {searchResults.map((item) => (
            <div key={item.name} className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="text-white">{item.name}</div>
                  <div className="mt-1 text-sm text-slate-400">{item.description}</div>
                </div>
                <div className="flex gap-2">
                  {["install", "remove", "reinstall"].map((action) => (
                    <ActionButton key={action} onClick={() => runAction(action as "install" | "remove" | "reinstall", item.name)} className="bg-white/5 text-white hover:bg-white/10">
                      {busy === `${action}:${item.name}` ? "..." : action}
                    </ActionButton>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Upgradable" subtitle="Current apt-reported updates">
        <ErrorBanner error={upgradable.error} />
        <div className="space-y-2 text-sm text-slate-300">
          {(upgradable.data ?? []).map((item) => (
            <div key={item} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3">
              {item}
            </div>
          ))}
          {!upgradable.data?.length ? <div>No updates reported.</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function ProcessesPage() {
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");
  const processes = useQuery<ProcessItem[]>({
    queryKey: ["processes", search],
    queryFn: () => api<ProcessItem[]>(`/api/processes${search ? `?search=${encodeURIComponent(search)}` : ""}`),
  });

  async function killProcess(pid: number) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/processes/kill", {
        method: "POST",
        body: JSON.stringify({ pid, signal: "TERM", confirm_password }),
      });
      setNotice(`Sent TERM to PID ${pid}.`);
      await processes.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Process action failed");
    }
  }

  return (
    <Panel title="Processes" subtitle="Live process inventory from psutil">
      <SectionHeader title="Process List" subtitle="Search and terminate processes" refresh={() => processes.refetch()} />
      <div className="mb-4 flex gap-3">
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search process name" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
      </div>
      <ErrorBanner error={processes.error} />
      {actionError ? <NoticeBanner message={actionError} tone="error" /> : null}
      {notice ? <NoticeBanner message={notice} /> : null}
      <div className="max-h-[38rem] overflow-auto rounded-3xl border border-white/10">
        <table className="min-w-full text-left text-sm text-slate-200">
          <thead className="bg-white/5 text-slate-400">
            <tr>
              <th className="px-4 py-3">PID</th>
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">CPU</th>
              <th className="px-4 py-3">RAM</th>
              <th className="px-4 py-3">User</th>
              <th className="px-4 py-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {(processes.data ?? []).map((item) => (
              <tr key={item.pid} className="border-t border-white/5">
                <td className="px-4 py-3">{item.pid}</td>
                <td className="px-4 py-3">{item.name}</td>
                <td className="px-4 py-3">{formatPercent(item.cpu_percent)}</td>
                <td className="px-4 py-3">{formatPercent(item.memory_percent)}</td>
                <td className="px-4 py-3">{item.username}</td>
                <td className="px-4 py-3">
                  <ActionButton onClick={() => killProcess(item.pid)} className="bg-white/5 text-white hover:bg-white/10">
                    Terminate
                  </ActionButton>
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
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [serviceName, setServiceName] = useState("");
  const systemLogs = useQuery<{ logs: string }>({
    queryKey: ["system-logs", severity, search],
    queryFn: () =>
      api<{ logs: string }>(
        `/api/logs/system?lines=200${severity ? `&severity=${encodeURIComponent(severity)}` : ""}${search ? `&query=${encodeURIComponent(search)}` : ""}`,
      ),
  });
  const serviceLogs = useQuery<{ logs: string }>({
    queryKey: ["logs-service", serviceName],
    queryFn: () => api<{ logs: string }>(`/api/logs/service/${encodeURIComponent(serviceName)}?lines=200`),
    enabled: Boolean(serviceName),
  });

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel title="System Logs" subtitle="Journalctl-backed system logs">
        <SectionHeader title="System Journal" subtitle="Filter recent entries" refresh={() => systemLogs.refetch()} />
        <div className="mb-4 grid gap-3 sm:grid-cols-[160px,1fr]">
          <input value={severity} onChange={(event) => setSeverity(event.target.value)} placeholder="Severity e.g. err" className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search text" className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
        </div>
        <ErrorBanner error={systemLogs.error} />
        <pre className="max-h-[34rem] overflow-auto rounded-2xl bg-slate-950/80 p-4 text-xs text-slate-300">{systemLogs.data?.logs ?? ""}</pre>
      </Panel>
      <Panel title="Service Logs" subtitle="Journalctl logs for a specific unit">
        <SectionHeader title="Unit Journal" subtitle="Load logs for one service" refresh={() => serviceLogs.refetch()} />
        <input value={serviceName} onChange={(event) => setServiceName(event.target.value)} placeholder="Service name, e.g. ssh.service" className="mb-4 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
        <ErrorBanner error={serviceLogs.error} />
        <pre className="max-h-[34rem] overflow-auto rounded-2xl bg-slate-950/80 p-4 text-xs text-slate-300">{serviceLogs.data?.logs ?? ""}</pre>
      </Panel>
    </div>
  );
}

function FirewallPage() {
  const firewall = useQuery<FirewallStatusResponse>({
    queryKey: ["firewall-status"],
    queryFn: () => api<FirewallStatusResponse>("/api/firewall/status"),
  });
  const [port, setPort] = useState("2511");
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function protectedPost(path: string, body: Record<string, unknown> = {}) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify({ ...body, confirm_password }),
      });
      setNotice("Firewall update applied successfully.");
      await firewall.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Firewall update failed");
    }
  }

  return (
    <Panel title="Firewall" subtitle="UFW-backed firewall management">
      <SectionHeader title="UFW Status" subtitle="Enable, disable, and manage rules" refresh={() => firewall.refetch()} />
      <ErrorBanner error={firewall.error} />
      {actionError ? <NoticeBanner message={actionError} tone="error" /> : null}
      {notice ? <NoticeBanner message={notice} /> : null}
      <pre className="mb-6 max-h-[20rem] overflow-auto rounded-2xl bg-slate-950/80 p-4 text-xs text-slate-300">{firewall.data?.status ?? ""}</pre>
      <div className="grid gap-4 xl:grid-cols-[220px,1fr]">
        <div className="flex gap-3">
          <ActionButton onClick={() => protectedPost("/api/firewall/enable")}>Enable</ActionButton>
          <ActionButton onClick={() => protectedPost("/api/firewall/disable")} className="bg-white/5 text-white hover:bg-white/10">
            Disable
          </ActionButton>
        </div>
        <div className="flex gap-3">
          <input value={port} onChange={(event) => setPort(event.target.value)} className="w-40 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton onClick={() => protectedPost("/api/firewall/allow-port", { port: Number(port), protocol: "tcp" })}>Allow Port</ActionButton>
          <ActionButton onClick={() => protectedPost("/api/firewall/deny-port", { port: Number(port), protocol: "tcp" })} className="bg-white/5 text-white hover:bg-white/10">
            Deny Port
          </ActionButton>
        </div>
      </div>
    </Panel>
  );
}

function UsersPage() {
  const users = useQuery<UserItem[]>({
    queryKey: ["users"],
    queryFn: () => api<UserItem[]>("/api/users"),
  });
  const [createForm, setCreateForm] = useState({ username: "", shell: "/bin/bash", password: "", sudo: false });
  const [notice, setNotice] = useState("");
  const [actionError, setActionError] = useState("");

  async function protectedUserAction(path: string, body: Record<string, unknown>) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api(path, {
        method: "POST",
        body: JSON.stringify({ ...body, confirm_password }),
      });
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
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.05fr,0.95fr]">
      <Panel title="Users" subtitle="Local Linux account management">
        <SectionHeader title="Accounts" subtitle="View and operate on system users" refresh={() => users.refetch()} />
        <ErrorBanner error={users.error} />
        {actionError ? <NoticeBanner message={actionError} tone="error" /> : null}
        {notice ? <NoticeBanner message={notice} /> : null}
        <div className="max-h-[38rem] overflow-auto rounded-3xl border border-white/10">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="bg-white/5 text-slate-400">
              <tr>
                <th className="px-4 py-3">User</th>
                <th className="px-4 py-3">Home</th>
                <th className="px-4 py-3">Shell</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(users.data ?? []).map((item) => (
                <tr key={item.username} className="border-t border-white/5">
                  <td className="px-4 py-3">{item.username}</td>
                  <td className="px-4 py-3">{item.home}</td>
                  <td className="px-4 py-3">{item.shell}</td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-2">
                      <ActionButton onClick={() => protectedUserAction("/api/users/lock", { username: item.username })} className="bg-white/5 text-white hover:bg-white/10" disabled={item.username === "root"}>
                        Lock
                      </ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/unlock", { username: item.username })} className="bg-white/5 text-white hover:bg-white/10">
                        Unlock
                      </ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/set-sudo", { username: item.username, enabled: true })} className="bg-white/5 text-white hover:bg-white/10">
                        Grant sudo
                      </ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/set-sudo", { username: item.username, enabled: false })} className="bg-white/5 text-white hover:bg-white/10">
                        Revoke sudo
                      </ActionButton>
                      <ActionButton onClick={() => protectedUserAction("/api/users/delete", { username: item.username })} className="bg-rose-500/20 text-rose-100 hover:bg-rose-500/30" disabled={item.username === "root"}>
                        Delete
                      </ActionButton>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Create User" subtitle="Provision a new system account">
        <form onSubmit={createUser} className="space-y-4">
          <input value={createForm.username} onChange={(event) => setCreateForm((current) => ({ ...current, username: event.target.value }))} placeholder="Username" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <input value={createForm.shell} onChange={(event) => setCreateForm((current) => ({ ...current, shell: event.target.value }))} placeholder="/bin/bash" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <input type="password" value={createForm.password} onChange={(event) => setCreateForm((current) => ({ ...current, password: event.target.value }))} placeholder="Initial password" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <label className="flex items-center gap-3 text-sm text-slate-300">
            <input type="checkbox" checked={createForm.sudo} onChange={(event) => setCreateForm((current) => ({ ...current, sudo: event.target.checked }))} />
            Grant sudo access
          </label>
          <ActionButton type="submit">Create User</ActionButton>
        </form>
      </Panel>
    </div>
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
  });
  const fileContents = useQuery<FileReadResponse>({
    queryKey: ["file-read", selectedFile],
    queryFn: () => api<FileReadResponse>(`/api/files/read?path=${encodeURIComponent(selectedFile)}`),
    enabled: Boolean(selectedFile),
  });

  useEffect(() => {
    if (fileContents.data) {
      setEditorContent(fileContents.data.content);
    }
  }, [fileContents.data]);

  async function writeFile() {
    if (!selectedFile) return;
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/write", {
        method: "POST",
        body: JSON.stringify({ path: selectedFile, content: editorContent, create_backup: true, confirm_password }),
      });
      setNotice(`Saved ${selectedFile}.`);
      await fileContents.refetch();
      await files.refetch();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "File save failed");
    }
  }

  async function deletePath(path: string) {
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/delete", {
        method: "POST",
        body: JSON.stringify({ path, confirm_password }),
      });
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
    const confirm_password = askForConfirmation();
    if (!confirm_password) return;
    const target = newDir.startsWith("/") ? newDir : `${currentPath.replace(/\/$/, "")}/${newDir}`;
    setNotice("");
    setActionError("");
    try {
      await api("/api/files/mkdir", {
        method: "POST",
        body: JSON.stringify({ path: target, confirm_password }),
      });
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
        <SectionHeader title="Browser" subtitle="Navigate and inspect files" refresh={() => files.refetch()} />
        <div className="mb-4 flex gap-3">
          <input value={currentPath} onChange={(event) => setCurrentPath(event.target.value)} className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton type="button" onClick={() => files.refetch()}>
            Open
          </ActionButton>
        </div>
        <form onSubmit={createDirectory} className="mb-4 flex gap-3">
          <input value={newDir} onChange={(event) => setNewDir(event.target.value)} placeholder="New directory name or path" className="flex-1 rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white" />
          <ActionButton type="submit" className="bg-white/5 text-white hover:bg-white/10">
            Create Dir
          </ActionButton>
        </form>
        <ErrorBanner error={files.error} />
        {actionError ? <NoticeBanner message={actionError} tone="error" /> : null}
        {notice ? <NoticeBanner message={notice} /> : null}
        <div className="max-h-[34rem] overflow-auto rounded-3xl border border-white/10">
          <table className="min-w-full text-left text-sm text-slate-200">
            <thead className="bg-white/5 text-slate-400">
              <tr>
                <th className="px-4 py-3">Path</th>
                <th className="px-4 py-3">Type</th>
                <th className="px-4 py-3">Permissions</th>
                <th className="px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {(files.data ?? []).map((item) => (
                <tr key={item.path} className="border-t border-white/5">
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => {
                        if (item.type === "directory") {
                          setCurrentPath(item.path);
                          setSelectedFile("");
                          setEditorContent("");
                        } else {
                          setSelectedFile(item.path);
                        }
                      }}
                      className="text-left text-white hover:text-ember-300"
                    >
                      {item.path}
                    </button>
                  </td>
                  <td className="px-4 py-3">{item.type}</td>
                  <td className="px-4 py-3">{item.permissions}</td>
                  <td className="px-4 py-3">
                    <ActionButton onClick={() => deletePath(item.path)} className="bg-rose-500/20 text-rose-100 hover:bg-rose-500/30">
                      Delete
                    </ActionButton>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Editor" subtitle="Read and write text files with backup safety">
        <div className="mb-3 text-sm text-slate-400">{selectedFile || "Select a file from the browser"}</div>
        <ErrorBanner error={fileContents.error} />
        <textarea value={editorContent} onChange={(event) => setEditorContent(event.target.value)} className="min-h-[28rem] w-full rounded-2xl border border-white/10 bg-slate-950/80 p-4 text-sm text-slate-100" />
        <div className="mt-4 flex gap-3">
          <ActionButton onClick={writeFile} disabled={!selectedFile}>
            Save File
          </ActionButton>
          {selectedFile ? <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-300">Backups are written as `*.bak` before overwrite.</div> : null}
        </div>
      </Panel>
    </div>
  );
}

function NetworkPage() {
  const network = useQuery<Record<string, unknown>>({
    queryKey: ["network-dns"],
    queryFn: () => api<Record<string, unknown>>("/api/network/dns"),
  });

  return (
    <Panel title="Network" subtitle="Basic network details">
      <SectionHeader title="Network State" subtitle="More advanced editing remains outside the core pass" refresh={() => network.refetch()} />
      <JsonBlock value={network.data ?? {}} />
    </Panel>
  );
}

function DockerPage() {
  const docker = useQuery<Record<string, unknown>>({
    queryKey: ["docker-status"],
    queryFn: () => api<Record<string, unknown>>("/api/docker/status"),
  });

  return (
    <Panel title="Docker" subtitle="Installed engine visibility">
      <SectionHeader title="Docker Status" subtitle="Wired to the backend Docker API" refresh={() => docker.refetch()} />
      <JsonBlock value={docker.data ?? {}} />
    </Panel>
  );
}

function SimpleJsonPage({ title, subtitle, queryKey, path }: { title: string; subtitle: string; queryKey: string[]; path: string }) {
  const data = useQuery<Record<string, unknown> | Array<Record<string, unknown>>>({
    queryKey,
    queryFn: () => api<Record<string, unknown> | Array<Record<string, unknown>>>(path),
  });

  return (
    <Panel title={title} subtitle={subtitle}>
      <SectionHeader title={title} subtitle={subtitle} refresh={() => data.refetch()} />
      <JsonBlock value={data.data ?? {}} />
    </Panel>
  );
}

function Dashboard() {
  const queryClient = useQueryClient();
  const [current, setCurrent] = useState<ModuleKey>("overview");
  const settings = useQuery<SettingsState>({
    queryKey: ["settings"],
    queryFn: () => api<SettingsState>("/api/settings"),
  });
  const overview = useQuery<Overview>({
    queryKey: ["header-overview"],
    queryFn: () => api<Overview>("/api/system/overview"),
    refetchInterval: 20000,
  });

  const topStatus = useMemo(() => {
    if (!overview.data) return "Syncing node state";
    return `${overview.data.hostname} | ${overview.data.os_version}`;
  }, [overview.data]);

  async function logout() {
    await api("/api/auth/logout", { method: "POST" });
    await queryClient.invalidateQueries({ queryKey: ["session"] });
  }

  let content: ReactElement;
  switch (current) {
    case "overview":
      content = <OverviewPage />;
      break;
    case "services":
      content = <ServicesPage />;
      break;
    case "packages":
      content = <PackagesPage />;
      break;
    case "firewall":
      content = <FirewallPage />;
      break;
    case "users":
      content = <UsersPage />;
      break;
    case "files":
      content = <FilesPage />;
      break;
    case "processes":
      content = <ProcessesPage />;
      break;
    case "logs":
      content = <LogsPage />;
      break;
    default:
      content = <OverviewPage />;
  }

  return (
    <div className="min-h-screen bg-igris-glow text-slate-100">
      <div className="mx-auto grid min-h-screen max-w-[1680px] gap-6 p-4 lg:grid-cols-[280px,1fr] lg:p-6">
        <aside className="rounded-[2rem] border border-white/10 bg-black/40 p-5 backdrop-blur">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.35em] text-ember-300">Igris</p>
            <h1 className="mt-4 font-display text-3xl text-white">Server Command</h1>
            <p className="mt-3 text-sm text-slate-400">Ubuntu operations, audit, and recovery from one dashboard.</p>
          </div>
          <nav className="space-y-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = current === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setCurrent(item.key)}
                  className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-left transition ${
                    active ? "bg-ember-500/20 text-white ring-1 ring-ember-400/40" : "text-slate-300 hover:bg-white/5"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        </aside>
        <main className="space-y-6">
          <header className="rounded-[2rem] border border-white/10 bg-black/30 p-5 backdrop-blur">
            <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.28em] text-ember-300">Node Status</p>
                <h2 className="mt-3 text-3xl font-semibold text-white">{topStatus}</h2>
                <p className="mt-2 text-sm text-slate-400">
                  Dashboard port {settings.data?.server_port ?? 2511}, terminal {settings.data?.allow_terminal ? "enabled" : "disabled"}.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
                  Secure session active
                </div>
                <button type="button" onClick={logout} className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white transition hover:bg-white/10">
                  Sign out
                </button>
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

  if (session.isLoading) {
    return <div className="flex min-h-screen items-center justify-center bg-igris-glow text-slate-200">Synchronizing secure session...</div>;
  }

  if (session.isError) {
    return <LoginPage onLogin={() => queryClient.invalidateQueries({ queryKey: ["session"] })} />;
  }

  return <Dashboard />;
}
