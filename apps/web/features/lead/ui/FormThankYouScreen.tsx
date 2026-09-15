"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { CarFront, CircleCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  FORM_THANK_YOU_REDIRECT_MS,
  queueFormThankYouToast,
  type FormThankYouIconName,
} from "@/features/lead/lib/form-thank-you";

const ICONS: Record<FormThankYouIconName, LucideIcon> = {
  check: CircleCheck,
  car: CarFront,
};

export type FormThankYouScreenProps = {
  title: string;
  description: string;
  icon?: FormThankYouIconName;
  redirectHref?: string;
  redirectLabel?: string;
  durationMs?: number;
  toastTitle: string;
  toastDescription?: string;
};

export function FormThankYouScreen({
  title,
  description,
  icon = "check",
  redirectHref = "/",
  redirectLabel = "Ir para a página inicial",
  durationMs = FORM_THANK_YOU_REDIRECT_MS,
  toastTitle,
  toastDescription = "",
}: FormThankYouScreenProps) {
  const router = useRouter();
  const redirected = useRef(false);
  const [remainingMs, setRemainingMs] = useState(durationMs);
  const Icon = ICONS[icon] ?? CircleCheck;
  const secondsLeft = Math.max(1, Math.ceil(remainingMs / 1000));
  const progress = Math.min(1, Math.max(0, remainingMs / durationMs));

  const go = useCallback(() => {
    if (redirected.current) return;
    redirected.current = true;
    router.push(redirectHref);
  }, [redirectHref, router]);

  useEffect(() => {
    queueFormThankYouToast({ title: toastTitle, description: toastDescription });
  }, [toastDescription, toastTitle]);

  useEffect(() => {
    const startedAt = Date.now();
    const tick = window.setInterval(() => {
      const left = Math.max(0, durationMs - (Date.now() - startedAt));
      setRemainingMs(left);
      if (left <= 0) {
        window.clearInterval(tick);
        go();
      }
    }, 100);
    return () => window.clearInterval(tick);
  }, [durationMs, go]);

  const radius = 38;
  const circumference = 2 * Math.PI * radius;

  return (
    <main className="flex min-h-[calc(100svh-3.5rem)] items-center justify-center px-4 py-16">
      <section
        aria-labelledby="form-thank-you-title"
        className="w-full max-w-lg rounded-3xl border border-facil-border bg-facil-card px-6 py-12 text-center shadow-lg shadow-zinc-900/5 sm:px-10"
      >
        <div className="relative mx-auto flex h-28 w-28 items-center justify-center">
          <svg
            className="absolute inset-0 -rotate-90"
            viewBox="0 0 88 88"
            aria-hidden
          >
            <circle
              cx="44"
              cy="44"
              r={radius}
              fill="none"
              className="stroke-facil-border"
              strokeWidth="6"
            />
            <circle
              cx="44"
              cy="44"
              r={radius}
              fill="none"
              className="stroke-facil-orange"
              strokeWidth="6"
              strokeLinecap="round"
              strokeDasharray={circumference}
              strokeDashoffset={circumference * (1 - progress)}
            />
          </svg>
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-facil-orange/10 text-facil-orange">
            <Icon className="h-10 w-10" strokeWidth={1.75} aria-hidden />
          </div>
        </div>

        <h1
          id="form-thank-you-title"
          className="mt-8 text-3xl font-bold tracking-tight text-foreground md:text-4xl"
        >
          {title}
        </h1>
        <p className="mx-auto mt-3 max-w-md text-base leading-relaxed text-facil-muted">
          {description}
        </p>

        <button
          type="button"
          onClick={go}
          className="btn-facil-primary mt-8 w-full px-8 py-3.5 text-base font-bold sm:w-auto"
        >
          {redirectLabel}
        </button>

        <p className="mt-4 text-sm text-facil-muted" aria-live="polite">
          Redirecionando em {secondsLeft}s…
        </p>
      </section>
    </main>
  );
}
