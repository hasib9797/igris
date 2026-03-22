import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AuthUser } from "../lib/types";

export function useSession() {
  return useQuery<AuthUser>({
    queryKey: ["session"],
    queryFn: () => api<AuthUser>("/api/auth/me"),
    retry: false,
  });
}
