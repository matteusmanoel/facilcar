"use client";

import { useRef, useState, useCallback, useEffect } from "react";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const AUDIO_MAX_BYTES = 8 * 1024 * 1024; // 8 MB
const AUDIO_MAX_MS = 2 * 60 * 1000;       // 2 min

type RecordState = "idle" | "recording" | "done" | "no-mic";

type Props = {
  disabled?: boolean;
  placeholder?: string;
};

/**
 * Relato: textarea opcional + gravação de áudio direta no microfone.
 * Ambos podem ir vazios. O blob gravado entra em name="audio" para o servidor.
 */
export function RelatoFields({ disabled, placeholder }: Props) {
  const [recordState, setRecordState] = useState<RecordState>("idle");
  const [elapsed, setElapsed] = useState(0); // segundos
  const [audioUrl, setAudioUrl] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const audioFileInputRef = useRef<HTMLInputElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const defaultPlaceholder =
    placeholder ??
    "Conte o que quiser: o veículo, o uso, o que já sabe ou o que ainda está em dúvida. " +
    "Não precisa de CPF nem de documentos agora — esses detalhes conversamos depois.";

  // Limpar timer e URL de objeto ao desmontar
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      streamRef.current?.getTracks().forEach((t) => t.stop());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const startRecording = useCallback(async () => {
    if (disabled) return;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];

      // Detectar o melhor formato disponível
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/mp4"]
        .find((m) => MediaRecorder.isTypeSupported(m)) ?? "";

      const mr = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      mediaRecorderRef.current = mr;

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: mr.mimeType || "audio/webm" });
        if (blob.size > AUDIO_MAX_BYTES) {
          alert("O áudio ultrapassou o limite de 8 MB. Tente um relato mais curto.");
          setRecordState("idle");
          setElapsed(0);
          return;
        }
        // Injetar no input oculto como File para o FormData capturar
        const ext = (mr.mimeType || "audio/webm").split(";")[0].split("/")[1] ?? "webm";
        const file = new File([blob], `relato.${ext}`, { type: mr.mimeType || "audio/webm" });
        const dt = new DataTransfer();
        dt.items.add(file);
        if (audioFileInputRef.current) {
          audioFileInputRef.current.files = dt.files;
        }
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        setAudioUrl(URL.createObjectURL(blob));
        setRecordState("done");
      };

      mr.start(200);
      setElapsed(0);
      setRecordState("recording");
      timerRef.current = setInterval(() => {
        setElapsed((s) => {
          if (s + 1 >= AUDIO_MAX_MS / 1000) {
            stopRecording();
            return s + 1;
          }
          return s + 1;
        });
      }, 1000);
    } catch {
      setRecordState("no-mic");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [disabled]);

  const stopRecording = useCallback(() => {
    stopTimer();
    mediaRecorderRef.current?.stop();
  }, [stopTimer]);

  const resetRecording = useCallback(() => {
    stopTimer();
    mediaRecorderRef.current?.stop();
    streamRef.current?.getTracks().forEach((t) => t.stop());
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    setAudioUrl(null);
    setElapsed(0);
    setRecordState("idle");
    // Limpar input oculto
    if (audioFileInputRef.current) {
      const dt = new DataTransfer();
      audioFileInputRef.current.files = dt.files;
    }
  }, [stopTimer, audioUrl]);

  const fmtTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  return (
    <div className="space-y-3">
      {/* Textarea de relato */}
      <div>
        <div className={`${publicFormLabelClass} flex items-center gap-1.5`}>
          <span>Mensagem</span>
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="Dica sobre a mensagem"
                  className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-facil-muted/20 text-[10px] font-bold text-facil-muted hover:bg-facil-muted/30 focus:outline-none"
                >
                  i
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[260px] text-center leading-relaxed">
                Conte o veículo de interesse, faixa de preço, uso pretendido ou o que já sabe.
                CPF e documentos não são necessários agora — isso fica para depois da conversa.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>
        <textarea
          name="relato"
          rows={4}
          className={`${publicFormInputClass} mt-1 resize-none`}
          placeholder={defaultPlaceholder}
          disabled={disabled}
        />
        <span className="mt-1 block text-xs font-normal text-facil-muted">
          Pode deixar em branco. Quanto mais contexto, mais rápido o encaminhamento.
        </span>
      </div>

      {/* Gravador de áudio */}
      <div>
        <div className={`${publicFormLabelClass} flex items-center gap-1.5`}>
          <span>Áudio (opcional)</span>
          <TooltipProvider delayDuration={100}>
            <Tooltip>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  aria-label="Dica sobre o áudio"
                  className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-facil-muted/20 text-[10px] font-bold text-facil-muted hover:bg-facil-muted/30 focus:outline-none"
                >
                  i
                </button>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[260px] text-center leading-relaxed">
                Prefere falar? Grave direto aqui — sem precisar de app. O áudio fica salvo até o
                envio. Limite de 2 minutos.
              </TooltipContent>
            </Tooltip>
          </TooltipProvider>
        </div>

        {/* Input oculto que carrega o File para o FormData */}
        <input
          ref={audioFileInputRef}
          name="audio"
          type="file"
          accept="audio/*"
          className="hidden"
          disabled={disabled}
          aria-hidden
        />

        {recordState === "no-mic" && (
          <p className="mt-1 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-700">
            Não foi possível acessar o microfone. Verifique a permissão no navegador.
          </p>
        )}

        {recordState === "idle" && (
          <button
            type="button"
            disabled={disabled}
            onClick={startRecording}
            className="mt-1 flex items-center gap-2 rounded-xl border border-facil-border bg-facil-surface px-4 py-2.5 text-sm font-medium text-foreground transition hover:border-facil-orange hover:text-facil-orange disabled:opacity-50"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden>
              <path d="M12 1a4 4 0 0 1 4 4v6a4 4 0 0 1-8 0V5a4 4 0 0 1 4-4zm0 2a2 2 0 0 0-2 2v6a2 2 0 0 0 4 0V5a2 2 0 0 0-2-2zm7 8a1 1 0 0 1 1 1 8 8 0 0 1-7 7.938V22h-2v-2.062A8 8 0 0 1 4 12a1 1 0 0 1 2 0 6 6 0 0 0 12 0 1 1 0 0 1 1-1z"/>
            </svg>
            Gravar áudio
          </button>
        )}

        {recordState === "recording" && (
          <div className="mt-1 flex items-center gap-3">
            <span className="flex items-center gap-1.5 text-sm text-red-600">
              <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-red-500" />
              Gravando {fmtTime(elapsed)}
            </span>
            <button
              type="button"
              onClick={stopRecording}
              className="rounded-xl border border-red-300 px-4 py-2 text-sm font-medium text-red-600 transition hover:bg-red-50"
            >
              Parar
            </button>
          </div>
        )}

        {recordState === "done" && audioUrl && (
          <div className="mt-1 flex flex-col gap-2">
            <audio src={audioUrl} controls className="h-9 w-full" />
            <div className="flex gap-2 text-xs">
              <button
                type="button"
                onClick={startRecording}
                disabled={disabled}
                className="text-facil-orange underline underline-offset-2 hover:opacity-80"
              >
                Gravar novamente
              </button>
              <span className="text-facil-muted">·</span>
              <button
                type="button"
                onClick={resetRecording}
                className="text-facil-muted underline underline-offset-2 hover:opacity-80"
              >
                Remover
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
