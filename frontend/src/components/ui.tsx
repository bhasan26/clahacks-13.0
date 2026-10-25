import React from "react";
import clsx from "clsx";
import { AlertTriangle, CheckCircle2, HelpCircle, Loader2, XCircle, type LucideIcon } from "lucide-react";

// Shared building blocks so every screen uses the same buttons, cards, badges and fields.

export type Tone = "ok" | "rejected" | "action" | "unknown";

export const TONE: Record<Tone, { icon: LucideIcon; badge: string; panel: string; text: string }> = {
  ok: { icon: CheckCircle2, badge: "bg-ok-soft text-ok ring-ok-line", panel: "bg-ok-soft border-ok-line", text: "text-ok" },
  rejected: { icon: XCircle, badge: "bg-bad-soft text-bad ring-bad-line", panel: "bg-bad-soft border-bad-line", text: "text-bad" },
  action: { icon: AlertTriangle, badge: "bg-warn-soft text-warn ring-warn-line", panel: "bg-warn-soft border-warn-line", text: "text-warn" },
  unknown: { icon: HelpCircle, badge: "bg-unknown-soft text-unknown ring-unknown-line", panel: "bg-unknown-soft border-unknown-line", text: "text-unknown" },
};

export function StatusBadge({ tone, children }: { tone: Tone; children: React.ReactNode }) {
  const Icon = TONE[tone].icon;
  return (
    <span className={clsx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ring-inset whitespace-nowrap", TONE[tone].badge)}>
      <Icon className="size-3.5 shrink-0" aria-hidden="true" />
      {children}
    </span>
  );
}

export function Tag({ children, tone = "demo" }: { children: React.ReactNode; tone?: "demo" | "neutral" | "brand" }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2 py-px text-[11px] font-semibold ring-1 ring-inset",
        tone === "demo" && "bg-demo-soft text-demo ring-demo-line",
        tone === "neutral" && "bg-sunken text-muted ring-line",
        tone === "brand" && "bg-brand-soft text-brand ring-brand-tint",
      )}
    >
      {children}
    </span>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost";
  size?: "sm" | "md";
  icon?: LucideIcon;
  loading?: boolean;
};

export function Button({ variant = "secondary", size = "md", icon: Icon, loading, className, children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-xl font-semibold whitespace-nowrap transition-colors duration-150 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50",
        size === "md" ? "h-10 px-4 text-sm" : "h-8 px-3 text-xs",
        variant === "primary" && "bg-cta text-white shadow-sm shadow-cta/25 hover:bg-cta-hover",
        variant === "secondary" && "bg-surface text-ink-2 ring-1 ring-inset ring-line-strong shadow-xs hover:bg-sunken",
        variant === "ghost" && "text-brand hover:bg-brand-soft",
        className,
      )}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden="true" /> : Icon && <Icon className="size-4" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLElement>) {
  return (
    <section {...rest} className={clsx("rounded-card border border-line/70 bg-surface shadow-card", className)}>
      {children}
    </section>
  );
}

export function CardHeader({ title, description, actions }: { title: React.ReactNode; description?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-6 py-5">
      <div>
        <h2 className="text-base font-bold text-ink">{title}</h2>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: React.ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-[26px] font-bold tracking-tight text-ink">{title}</h1>
        <p className="mt-1 text-sm text-muted">{description}</p>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}

export const fieldClass = (invalid = false) =>
  clsx(
    "block h-10 w-full rounded-xl bg-surface px-3.5 text-sm text-ink shadow-xs ring-1 ring-inset placeholder:text-subtle focus:outline-none focus:ring-2 focus:ring-brand",
    invalid ? "ring-warn bg-warn-soft" : "ring-line-strong",
  );

export function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-subtle">{hint}</span>}
    </label>
  );
}

export function Notice({ tone = "unknown", children, action }: { tone?: Tone | "brand"; children: React.ReactNode; action?: React.ReactNode }) {
  const style = tone === "brand" ? "bg-brand-soft border-brand-tint text-brand-ink" : clsx(TONE[tone].panel, "text-ink-2");
  const Icon = tone === "brand" ? CheckCircle2 : TONE[tone].icon;
  return (
    <div role="status" className={clsx("flex items-start gap-2.5 rounded-xl border px-4 py-3 text-sm", style)}>
      <Icon className={clsx("mt-0.5 size-4 shrink-0", tone === "brand" ? "text-brand" : TONE[tone].text)} aria-hidden="true" />
      <div className="flex-1">{children}</div>
      {action}
    </div>
  );
}
