"use client";

import { useState } from "react";
import { createContactLead } from "../server/actions";
import {
  publicFormInputSimpleClass,
  publicFormLabelClass,
} from "@/lib/theme";

export function ContactForm() {
  const [status, setStatus] = useState<"idle" | "success" | "error">("idle");
  const [errorMessage, setErrorMessage] = useState("");

  return (
    <form
      action={async (formData) => {
        setStatus("idle");
        const result = await createContactLead(formData);
        if (result.success) {
          setStatus("success");
        } else {
          setStatus("error");
          setErrorMessage(result.error);
        }
      }}
      className="flex flex-col gap-3 max-w-md"
    >
      <label className={publicFormLabelClass}>
        Nome *
        <input name="name" required className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        Telefone *
        <input name="phone" type="tel" required className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        E-mail
        <input name="email" type="email" className={publicFormInputSimpleClass} />
      </label>
      <label className={publicFormLabelClass}>
        Mensagem
        <textarea name="message" rows={4} className={publicFormInputSimpleClass} />
      </label>
      {status === "success" && (
        <p className="text-sm text-green-600 dark:text-green-400">
          Mensagem enviada. Entraremos em contato em breve.
        </p>
      )}
      {status === "error" && (
        <p className="text-sm text-red-600 dark:text-red-400">{errorMessage}</p>
      )}
      <button
        type="submit"
        className="rounded bg-zinc-900 py-2 text-white hover:bg-zinc-800 dark:bg-facil-orange dark:hover:bg-facil-orange-hover"
      >
        Enviar
      </button>
    </form>
  );
}
