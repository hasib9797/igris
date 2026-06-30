export type AuthUser = {
  username: string;
  must_reauth: boolean;
};

export type Overview = {
  hostname: string;
  os_version: string;
  kernel_version: string;
  uptime_seconds: number;
  cpu_usage_percent: number;
  ram_usage_percent: number;
  disk_usage_percent: number;
  network_interfaces: string[];
  local_ip: string | null;
  public_ip: string | null;
  failed_services: string[];
  top_processes: Array<Record<string, unknown>>;
  pending_updates: string[];
  ai_monitor_summary: string;
  ai_monitor_findings: string[];
};

export type SecuritySummary = {
  trusted_subnets_enabled: boolean;
  trusted_subnets: string[];
  reauth_required: boolean;
  login_max_attempts: number;
  login_lockout_minutes: number;
  terminal_guard_enabled: boolean;
  security_headers_enabled: boolean;
  session_timeout_minutes: number;
  recent_audit: string[];
};
