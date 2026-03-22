type MetricCardProps = {
  label: string;
  value: string;
  accent?: string;
};

export function MetricCard({ label, value, accent = "from-ember-500/40 to-transparent" }: MetricCardProps) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-white/5 p-5 shadow-panel">
      <div className={`absolute inset-x-0 top-0 h-24 bg-gradient-to-b ${accent}`} />
      <div className="relative">
        <p className="text-xs uppercase tracking-[0.24em] text-slate-400">{label}</p>
        <p className="mt-4 text-3xl font-semibold text-white">{value}</p>
      </div>
    </div>
  );
}
