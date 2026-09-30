"use client";

import { useRef } from "react";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";

const AUDIO_MAX_BYTES = 8 * 1024 * 1024; // 8 MB

type Props = {
  disabled?: boolean;
  placeholder?: string;
};

/**
 * Relato: textarea opcional + upload de áudio opcional.
 * Ambos podem ir vazios. Nenhum campo é obrigatório.
 * O áudio é enviado como `audio` no FormData; o texto como `relato`.
 */
export function RelatoFields({ disabled, placeholder }: Props) {
  const audioRef = useRef<HTMLInputElement>(null);

  const defaultPlaceholder =
    placeholder ??
    "Conte o que quiser: o veículo, o uso, o que já sabe ou o que ainda está em dúvida. " +
    "Não precisa de CPF nem de documentos agora — esses detalhes conversamos depois.";

  return (
    <div className="space-y-3">
      <label className={publicFormLabelClass}>
        Mensagem
        <textarea
          name="relato"
          rows={4}
          className={`${publicFormInputClass} resize-none`}
          placeholder={defaultPlaceholder}
          disabled={disabled}
        />
        <span className="mt-1 block text-xs font-normal text-facil-muted">
          Pode deixar em branco. Quanto mais contexto, mais rápido o encaminhamento.
        </span>
      </label>

      <label className={publicFormLabelClass}>
        Áudio (opcional)
        <input
          ref={audioRef}
          name="audio"
          type="file"
          accept="audio/*"
          className={`${publicFormInputClass} file:mr-3 file:rounded-md file:border-0 file:bg-facil-orange file:px-3 file:py-1.5 file:text-sm file:font-semibold file:text-white`}
          disabled={disabled}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file && file.size > AUDIO_MAX_BYTES) {
              e.target.value = "";
              alert("O áudio deve ter no máximo 8 MB.");
            }
          }}
        />
        <span className="mt-1 block text-xs font-normal text-facil-muted">
          Prefere falar? Grave um áudio e envie aqui (máx. 8 MB).
        </span>
      </label>
    </div>
  );
}
