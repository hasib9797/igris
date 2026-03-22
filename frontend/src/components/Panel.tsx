import { PropsWithChildren } from "react";

type PanelProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
}>;

export function Panel({ title, subtitle, children }: PanelProps) {
  return (
    <section className="rounded-3xl border border-white/10 bg-black/30 p-6 backdrop-blur">
      <div className="mb-5">
        <h2 className="font-display text-2xl text-white">{title}</h2>
        {subtitle ? <p className="mt-2 text-sm text-slate-400">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}
