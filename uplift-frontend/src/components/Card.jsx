const TONES = {
  sky: "bg-sky-50 text-sky-600",
  emerald: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  rose: "bg-rose-50 text-rose-600",
  violet: "bg-violet-50 text-violet-600",
  teal: "bg-teal-50 text-teal-600",
  slate: "bg-slate-100 text-slate-500",
};

export function SectionHeading({ eyebrow, title, subtitle, titleClass = "text-sm" }) {
  return (
    <div className="min-w-0">
      {eyebrow && (
        <p className="mb-0.5 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-500">
          {eyebrow}
        </p>
      )}
      <h2 className={`${titleClass} font-bold text-slate-900`}>{title}</h2>
      {subtitle && <p className="mt-0.5 text-xs text-slate-600">{subtitle}</p>}
    </div>
  );
}

export default function SectionCard({
  ariaLabel,
  eyebrow,
  title,
  subtitle,
  icon: Icon,
  tone = "sky",
  actions,
  bodyClass = "px-5 py-5",
  footer,
  children,
}) {
  const toneClass = TONES[tone] ?? TONES.slate;
  return (
    <section
      aria-label={ariaLabel}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"
    >
      <header className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 items-center gap-3">
          {Icon && (
            <span className={`shrink-0 rounded-lg p-2.5 ${toneClass}`}>
              <Icon className="h-5 w-5" aria-hidden="true" />
            </span>
          )}
          <SectionHeading eyebrow={eyebrow} title={title} subtitle={subtitle} />
        </div>
        {actions && <div className="flex flex-wrap items-center justify-start gap-2 sm:justify-end">{actions}</div>}
      </header>
      <div className={bodyClass}>{children}</div>
      {footer}
    </section>
  );
}
