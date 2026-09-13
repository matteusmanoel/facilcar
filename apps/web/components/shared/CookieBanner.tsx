"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  readCookieConsent,
  writeCookieConsent,
  type CookieConsentChoice,
} from "@/lib/cookie-consent";

function setBannerOffset(open: boolean) {
  document.documentElement.style.setProperty(
    "--cookie-banner-offset",
    open ? "7.5rem" : "0px",
  );
}

export function CookieBanner() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const existing = readCookieConsent();
    const open = existing == null;
    setVisible(open);
    setBannerOffset(open);
    return () => setBannerOffset(false);
  }, []);

  function choose(choice: CookieConsentChoice) {
    writeCookieConsent(choice);
    setVisible(false);
    setBannerOffset(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 px-3 pb-3 sm:px-4 sm:pb-4">
      <div className="mx-auto flex max-w-3xl flex-col gap-3 rounded-2xl border border-facil-border bg-facil-card/95 p-4 shadow-lg shadow-black/10 backdrop-blur-md sm:flex-row sm:items-center sm:gap-6">
        <p className="flex-1 text-sm leading-relaxed text-foreground">
          Usamos cookies essenciais para o site funcionar e, com a sua permissão, cookies de
          analytics para entender como ele é usado.{" "}
          <Link href="/politica-de-cookies" className="font-medium text-facil-orange hover:underline">
            Política de cookies
          </Link>
        </p>
        <div className="flex shrink-0 flex-col gap-2 sm:flex-row">
          <button
            type="button"
            onClick={() => choose("essential")}
            className="w-full rounded-full border border-facil-border px-4 py-2 text-sm font-medium text-foreground transition hover:bg-facil-surface sm:w-auto"
          >
            Só essenciais
          </button>
          <button
            type="button"
            onClick={() => choose("accepted")}
            className="w-full rounded-full bg-facil-orange px-4 py-2 text-sm font-semibold text-white transition hover:bg-facil-orange-hover sm:w-auto"
          >
            Aceitar
          </button>
        </div>
      </div>
    </div>
  );
}
