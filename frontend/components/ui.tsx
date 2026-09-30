"use client";

import { useState, type ReactNode } from "react";
import type { SignaalSoort } from "@/lib/types";

/** Eén kengetal in het raster bovenin het paneel. */
export function Kengetal({ label, waarde, toelichting }: { label: string; waarde: ReactNode; toelichting?: ReactNode }) {
  return (
    <div className="rounded-xl border border-env-200/70 bg-white p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-env-900/55">{label}</div>
      <div className="mt-0.5 text-lg font-semibold leading-tight text-env-900">{waarde}</div>
      {toelichting && <div className="mt-0.5 text-[11px] leading-snug text-env-900/55">{toelichting}</div>}
    </div>
  );
}

/** Inklapbare sectie met titel, optionele bron en een klein getal rechts. */
export function Sectie({
  titel,
  bron,
  badge,
  open = true,
  children,
}: {
  titel: string;
  bron?: string;
  badge?: ReactNode;
  open?: boolean;
  children: ReactNode;
}) {
  const [isOpen, setOpen] = useState(open);
  return (
    <section className="rounded-xl border border-env-200/70 bg-white">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-2 px-4 py-3 text-left"
        aria-expanded={isOpen}
      >
        <svg
          className={`h-3.5 w-3.5 shrink-0 text-env-900/50 transition-transform ${isOpen ? "rotate-90" : ""}`}
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden
        >
          <path d="M7 5l6 5-6 5V5z" />
        </svg>
        <span className="text-sm font-semibold text-env-900">{titel}</span>
        {bron && <span className="text-[11px] text-env-900/45">· {bron}</span>}
        <span className="ml-auto text-xs text-env-900/60">{badge}</span>
      </button>
      {isOpen && <div className="border-t border-env-200/60 px-4 py-3">{children}</div>}
    </section>
  );
}

export function Chip({ children, kleur = "groen" }: { children: ReactNode; kleur?: "groen" | "grijs" | "amber" }) {
  const stijl = {
    groen: "bg-env-700 text-white",
    grijs: "bg-env-100 text-env-900",
    amber: "bg-amber-100 text-amber-900",
  }[kleur];
  return <span className={`inline-block rounded-full px-2 py-0.5 text-[11px] font-medium ${stijl}`}>{children}</span>;
}

/** Een signaal: kans (groen), let-op (amber) of info (grijs), met de bron erbij. */
export function SignaalKaart({ soort, tekst, bron }: { soort: SignaalSoort; tekst: string; bron: string }) {
  const stijl = {
    kans: { rand: "border-env-700/40 bg-env-100/60", stip: "bg-env-700", label: "Kans" },
    "let-op": { rand: "border-amber-300 bg-amber-50", stip: "bg-amber-500", label: "Let op" },
    info: { rand: "border-env-200 bg-white", stip: "bg-env-900/40", label: "Info" },
  }[soort];
  return (
    <div className={`flex gap-2.5 rounded-lg border px-3 py-2 text-[13px] leading-snug text-env-900 ${stijl.rand}`}>
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${stijl.stip}`} />
      <div>
        <span className="font-semibold">{stijl.label}: </span>
        {tekst} <span className="whitespace-nowrap text-[11px] text-env-900/50">({bron})</span>
      </div>
    </div>
  );
}

/** Regel "label ..... waarde" voor lijstjes met cijfers. */
export function Regel({ label, waarde }: { label: string; waarde: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1 text-[13px]">
      <span className="text-env-900/65">{label}</span>
      <span className="font-medium text-env-900">{waarde}</span>
    </div>
  );
}

export function Statusstip({ ok }: { ok: boolean }) {
  return <span className={`inline-block h-2 w-2 rounded-full ${ok ? "bg-env-700" : "bg-red-500"}`} aria-label={ok ? "ok" : "fout"} />;
}

/** Placeholder-blokken terwijl er geladen wordt. */
export function Skelet() {
  return (
    <div className="animate-pulse space-y-3" aria-hidden>
      <div className="h-7 w-2/3 rounded bg-env-200/70" />
      <div className="h-4 w-1/2 rounded bg-env-200/50" />
      <div className="grid grid-cols-2 gap-2 pt-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="h-16 rounded-xl bg-env-200/40" />
        ))}
      </div>
      <div className="h-24 rounded-xl bg-env-200/30" />
      <div className="h-24 rounded-xl bg-env-200/30" />
    </div>
  );
}
