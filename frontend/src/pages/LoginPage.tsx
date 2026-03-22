import { FormEvent, useState } from "react";
import { api } from "../api/client";

type LoginPageProps = {
  onLogin: () => void;
};

export function LoginPage({ onLogin }: LoginPageProps) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      onLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-igris-glow p-6">
      <div className="grid w-full max-w-6xl overflow-hidden rounded-[2rem] border border-white/10 bg-black/40 shadow-panel backdrop-blur lg:grid-cols-[1.1fr,0.9fr]">
        <div className="hidden flex-col justify-between bg-gradient-to-br from-ember-700/40 via-transparent to-transparent p-10 lg:flex">
          <div>
            <p className="text-sm uppercase tracking-[0.3em] text-ember-300">Igris</p>
            <h1 className="mt-6 max-w-lg font-display text-5xl text-white">
              Ubuntu command authority with a dashboard built for production.
            </h1>
          </div>
          <div className="grid gap-4 text-sm text-slate-300">
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Secure session cookies with privileged actions audited by default.</div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">Services, packages, network, users, Docker, files, and terminal governance in one surface.</div>
          </div>
        </div>
        <div className="p-8 sm:p-12">
          <p className="text-sm uppercase tracking-[0.25em] text-ember-300">Dashboard Access</p>
          <h2 className="mt-4 font-display text-4xl text-white">Sign in to Igris</h2>
          <p className="mt-3 text-slate-400">Use the dashboard admin created during `igris --setup`.</p>
          <form className="mt-10 space-y-5" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-sm text-slate-300">Username</span>
              <input className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none ring-0 transition focus:border-ember-500" value={username} onChange={(event) => setUsername(event.target.value)} />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm text-slate-300">Password</span>
              <input type="password" className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-white outline-none ring-0 transition focus:border-ember-500" value={password} onChange={(event) => setPassword(event.target.value)} />
            </label>
            {error ? <div className="rounded-2xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">{error}</div> : null}
            <button type="submit" disabled={loading} className="w-full rounded-2xl bg-ember-500 px-4 py-3 font-medium text-white transition hover:bg-ember-400 disabled:opacity-60">
              {loading ? "Authenticating..." : "Enter Dashboard"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
