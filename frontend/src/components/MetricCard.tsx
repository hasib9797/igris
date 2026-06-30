type MetricCardProps = {
  label: string;
  value: string;
  accent?: string;
};

export function MetricCard({ label, value, accent = "from-ember-500/40 to-transparent" }: MetricCardProps) {
  return (
    <div className="animate-igris-float relative overflow-hidden rounded-3xl border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.07),rgba(255,255,255,0.03))] p-5 shadow-panel transition duration-300 hover:-translate-y-1 hover:border-ember-400/30">
      <div className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-b ${accent}`} />
      <div className="absolute -right-8 top-6 h-20 w-20 rounded-full bg-ember-400/10 blur-3xl" />
      <div className="relative">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{label}</p>
        <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
      </div>
    </div>
  );
}
