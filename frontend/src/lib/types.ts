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
};
