"use client";

import { useEffect, useRef, useState } from "react";
import { Info, Mic, Square, Trash2 } from "lucide-react";
import { publicFormInputClass, publicFormLabelClass } from "@/lib/theme";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

const AUDIO_MAX_BYTES = 8 * 1024 * 1024;
const AUDIO_MAX_MS = 2 * 60 * 1000;

const DEFAULT_PLACEHOLDER =
  "Conte o que quiser: o veículo, o uso, o que já sabe ou o que ainda está em dúvida. " +
  "Não precisa de CPF nem de documentos agora — esses detalhes conversamos depois.";

const DEFAULT_HINT =
  "Conte o que acelera o encaminhamento: veículo, uso e o que você já sabe. CPF e documento não são necessários agora.";

type Props = {
  disabled?: boolean;
  placeholder?: string;
  hint?: string;
};

export function InfoTip({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip open={open} onOpenChange={setOpen}>
        <TooltipTrigger asChild>
          <button
            type="button"
            className="inline-flex h-4 w-4 shrink-0 items-center justify-center text-facil-muted hover:text-foreground"
            aria-label="Mais informações"
            aria-expanded={open}
            onClick={(event) => {
              event.preventDefault();
              setOpen((value) => !value);
            }}
          >
            <Info className="h-3.5 w-3.5" aria-hidden />
          </button>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-64 text-left font-normal leading-relaxed">
          {text}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function supportedMime() {
  if (typeof MediaRecorder === "undefined") return "";
  const types = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
  return types.find((type) => MediaRecorder.isTypeSupported(type)) ?? "";
}

function extensionFor(type: string) {
  if (type.includes("mp4") || type.includes("aac") || type.includes("m4a")) return "m4a";
  return "webm";
}

function formatClock(ms: number) {
  const total = Math.floor(ms / 1000);
  const minutes = Math.floor(total / 60);
  const seconds = total % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export function RelatoFields({ disabled, placeholder, hint }: Props) {
  const fileRef = useRef<HTMLInputElement>(null);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const startedAtRef = useRef(0);
  const limitRef = useRef<number | null>(null);
  const tickRef = useRef<number | null>(null);
  const previewRef = useRef<string | null>(null);

  const [phase, setPhase] = useState<"idle" | "recording" | "ready">("idle");
  const [elapsed, setElapsed] = useState(0);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [error, setError] = useState("");

  const fieldPlaceholder = placeholder ?? DEFAULT_PLACEHOLDER;
  const fieldHint = hint ?? DEFAULT_HINT;

  function clearTimers() {
    if (limitRef.current != null) window.clearTimeout(limitRef.current);
    if (tickRef.current != null) window.clearInterval(tickRef.current);
    limitRef.current = null;
    tickRef.current = null;
  }

  function stopStream() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
  }

  function revokePreview() {
    if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    previewRef.current = null;
    setPreviewUrl(null);
  }

  function clearFile() {
    if (fileRef.current) fileRef.current.value = "";
  }

  function discardRecording() {
    clearTimers();
    recorderRef.current = null;
    chunksRef.current = [];
    stopStream();
    revokePreview();
    clearFile();
    setElapsed(0);
    setPhase("idle");
  }

  useEffect(() => {
    const form = fileRef.current?.form;
    if (!form) return;
    const onSubmit = (event: Event) => {
      const recorder = recorderRef.current;
      if (!recorder || recorder.state === "inactive") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const finish = () => {
        recorder.removeEventListener("stop", finish);
        form.requestSubmit();
      };
      recorder.addEventListener("stop", finish);
      recorder.stop();
    };
    form.addEventListener("submit", onSubmit, true);
    return () => form.removeEventListener("submit", onSubmit, true);
  }, []);

  useEffect(() => {
    return () => {
      clearTimers();
      if (recorderRef.current && recorderRef.current.state !== "inactive") {
        recorderRef.current.onstop = null;
        recorderRef.current.stop();
      }
      stopStream();
      if (previewRef.current) URL.revokeObjectURL(previewRef.current);
    };
  }, []);

  function attachFile(blob: Blob) {
    const type = blob.type || "audio/webm";
    const file = new File([blob], `relato.${extensionFor(type)}`, { type });
    const input = fileRef.current;
    if (!input) return;
    const data = new DataTransfer();
    data.items.add(file);
    input.files = data.files;
  }

  async function startRecording() {
    setError("");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Seu navegador não permite gravar áudio nesta página.");
      return;
    }
    discardRecording();
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      const mime = supportedMime();
      const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        clearTimers();
        stopStream();
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
        chunksRef.current = [];
        recorderRef.current = null;
        if (blob.size === 0) {
          setPhase("idle");
          setError("Não foi possível gravar o áudio. Tente de novo.");
          return;
        }
        if (blob.size > AUDIO_MAX_BYTES) {
          setPhase("idle");
          setError("O áudio passou de 8 MB. Grave um trecho mais curto.");
          return;
        }
        attachFile(blob);
        const url = URL.createObjectURL(blob);
        previewRef.current = url;
        setPreviewUrl(url);
        setPhase("ready");
      };
      recorderRef.current = recorder;
      startedAtRef.current = Date.now();
      setElapsed(0);
      setPhase("recording");
      recorder.start();
      tickRef.current = window.setInterval(() => {
        setElapsed(Date.now() - startedAtRef.current);
      }, 250);
      limitRef.current = window.setTimeout(() => recorder.stop(), AUDIO_MAX_MS);
    } catch {
      stopStream();
      setPhase("idle");
      setError("Não foi possível usar o microfone. Libere o acesso e tente de novo.");
    }
  }

  function stopRecording() {
    if (recorderRef.current && recorderRef.current.state !== "inactive") {
      recorderRef.current.stop();
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center gap-1.5">
          <span className={publicFormLabelClass}>Mensagem</span>
          <InfoTip text={fieldHint} />
        </div>
        <textarea
          name="relato"
          rows={4}
          className={`${publicFormInputClass} resize-none`}
          placeholder={fieldPlaceholder}
          disabled={disabled}
        />
        <span className="mt-1 block text-xs font-normal text-facil-muted">
          Pode deixar em branco. Quanto mais contexto, mais rápido o encaminhamento.
        </span>
      </div>

      <div>
        <span className={publicFormLabelClass}>Áudio (opcional)</span>
        <input ref={fileRef} type="file" name="audio" accept="audio/*" className="hidden" tabIndex={-1} />
        <div className="mt-1.5 flex flex-wrap items-center gap-2">
          {phase !== "recording" ? (
            <button
              type="button"
              onClick={startRecording}
              disabled={disabled}
              className="inline-flex items-center gap-2 rounded-lg bg-facil-orange px-3 py-2 text-sm font-semibold text-white hover:bg-facil-orange-hover disabled:opacity-60"
            >
              <Mic className="h-4 w-4" aria-hidden />
              {phase === "ready" ? "Gravar de novo" : "Gravar áudio"}
            </button>
          ) : (
            <button
              type="button"
              onClick={stopRecording}
              className="inline-flex items-center gap-2 rounded-lg bg-red-600 px-3 py-2 text-sm font-semibold text-white hover:bg-red-700"
            >
              <Square className="h-4 w-4" aria-hidden />
              Parar {formatClock(elapsed)}
            </button>
          )}
          {phase === "ready" && (
            <button
              type="button"
              onClick={discardRecording}
              disabled={disabled}
              className="inline-flex items-center gap-1.5 rounded-lg border border-facil-border px-3 py-2 text-sm text-facil-muted hover:text-foreground disabled:opacity-60"
            >
              <Trash2 className="h-4 w-4" aria-hidden />
              Apagar
            </button>
          )}
        </div>
        {phase === "recording" && (
          <p className="mt-1 text-xs text-facil-muted" aria-live="polite">
            Gravando… até 2 minutos.
          </p>
        )}
        {previewUrl && phase === "ready" && (
          <audio src={previewUrl} controls className="mt-2 w-full" />
        )}
        {error && <p className="mt-1 text-xs text-red-600">{error}</p>}
        {!error && phase === "idle" && (
          <span className="mt-1 block text-xs font-normal text-facil-muted">
            Prefere falar? Grave pelo microfone. O áudio vai junto no envio.
          </span>
        )}
      </div>
    </div>
  );
}
