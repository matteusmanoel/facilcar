"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import { Upload, X, ImageIcon, GripVertical, Link as LinkIcon } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Preview {
  id: string;
  url: string;
  isLocal: boolean;
  file?: File;
  uploading?: boolean;
  error?: string;
}

interface ImageUploaderProps {
  value: string;
  onChange: (urlsNewlineSeparated: string) => void;
}

function urlsToList(value: string): string[] {
  return value
    .split("\n")
    .map((u) => u.trim())
    .filter(Boolean);
}

function listToUrls(list: string[]): string {
  return list.join("\n");
}

export function ImageUploader({ value, onChange }: ImageUploaderProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [manualUrl, setManualUrl] = useState("");
  const [isDraggingOver, setIsDraggingOver] = useState(false);
  const [confirmRemoveId, setConfirmRemoveId] = useState<string | null>(null);
  const isInitialMount = useRef(true);

  const existingUrls = urlsToList(value);

  const [localPreviews, setLocalPreviews] = useState<Preview[]>(() =>
    existingUrls.map((url) => ({
      id: url,
      url,
      isLocal: false,
    })),
  );

  // Sync to parent AFTER render, not inside state updater (avoids setState-in-render warning)
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    const uploaded = localPreviews
      .filter((p) => !p.uploading)
      .map((p) => p.url)
      .filter(Boolean);
    onChange(listToUrls(uploaded));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localPreviews]);

  const uploadFile = useCallback(async (file: File, previewId: string) => {
    const localUrl = URL.createObjectURL(file);

    setLocalPreviews((prev) => [
      ...prev.filter((p) => p.id !== previewId),
      { id: previewId, url: localUrl, isLocal: true, file, uploading: true },
    ]);

    try {
      const res = await fetch(
        `/api/admin/upload?filename=${encodeURIComponent(file.name)}&type=${encodeURIComponent(file.type)}`,
      );

      if (!res.ok) {
        setLocalPreviews((prev) =>
          prev.map((p) =>
            p.id === previewId
              ? { ...p, uploading: false, error: "Upload indisponível. Cole a URL abaixo." }
              : p,
          ),
        );
        return;
      }

      const { uploadUrl, publicUrl } = (await res.json()) as {
        uploadUrl: string;
        publicUrl: string;
      };

      await fetch(uploadUrl, {
        method: "PUT",
        body: file,
        headers: { "Content-Type": file.type },
      });

      URL.revokeObjectURL(localUrl);

      setLocalPreviews((prev) =>
        prev.map((p) =>
          p.id === previewId
            ? { id: previewId, url: publicUrl, isLocal: false, uploading: false }
            : p,
        ),
      );
    } catch {
      setLocalPreviews((prev) =>
        prev.map((p) =>
          p.id === previewId
            ? { ...p, uploading: false, error: "Falha no upload. Cole a URL abaixo." }
            : p,
        ),
      );
    }
  }, []);

  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return;
      Array.from(files).forEach((file) => {
        if (!file.type.startsWith("image/")) return;
        const id = `local-${Date.now()}-${Math.random()}`;
        uploadFile(file, id);
      });
    },
    [uploadFile],
  );

  const addManualUrl = useCallback(() => {
    const url = manualUrl.trim();
    if (!url) return;
    setLocalPreviews((prev) => {
      if (prev.some((p) => p.url === url)) return prev;
      return [...prev, { id: url, url, isLocal: false }];
    });
    setManualUrl("");
  }, [manualUrl]);

  const removePreview = useCallback((id: string) => {
    setLocalPreviews((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const moveUp = useCallback((index: number) => {
    if (index === 0) return;
    setLocalPreviews((prev) => {
      const updated = [...prev];
      [updated[index - 1], updated[index]] = [updated[index], updated[index - 1]];
      return updated;
    });
  }, []);

  return (
    <div className="space-y-4">
      {/* Drop zone */}
      <div
        className={cn(
          "relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer",
          isDraggingOver
            ? "border-facil-orange bg-facil-orange-light"
            : "border-zinc-300 hover:border-zinc-400 bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-500",
        )}
        onClick={() => fileInputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); setIsDraggingOver(true); }}
        onDragLeave={() => setIsDraggingOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsDraggingOver(false);
          handleFiles(e.dataTransfer.files);
        }}
      >
        <Upload className="h-8 w-8 text-zinc-400" />
        <div>
          <p className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Clique ou arraste imagens aqui
          </p>
          <p className="mt-0.5 text-xs text-zinc-400 dark:text-zinc-500">
            JPG, PNG, WebP · Múltiplos arquivos
          </p>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept="image/*"
          className="absolute inset-0 opacity-0 cursor-pointer"
          onChange={(e) => handleFiles(e.target.files)}
        />
      </div>

      {/* Image previews */}
      {localPreviews.length > 0 && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-4">
          {localPreviews.map((preview, index) => (
            <div
              key={preview.id}
              className="group relative aspect-video overflow-hidden rounded-lg border border-zinc-200 bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-800"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={preview.url}
                alt={`Imagem ${index + 1}`}
                className={cn(
                  "h-full w-full object-cover transition-opacity",
                  (preview.uploading || preview.error) && "opacity-40",
                )}
              />
              {index === 0 && !preview.uploading && !preview.error && (
                <span className="absolute left-1.5 top-1.5 rounded bg-facil-orange px-1.5 py-0.5 text-[10px] font-bold text-white">
                  Capa
                </span>
              )}
              {preview.uploading && (
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                </div>
              )}
              {preview.error && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/40 p-1">
                  <p className="text-center text-[10px] leading-tight text-white">{preview.error}</p>
                </div>
              )}
              <div className="absolute right-1 top-1 flex flex-col gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                <button
                  type="button"
                  onClick={() => setConfirmRemoveId(preview.id)}
                  className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-white hover:bg-red-600"
                >
                  <X className="h-3 w-3" />
                </button>
                {index > 0 && (
                  <button
                    type="button"
                    onClick={() => moveUp(index)}
                    title="Mover para cima (tornar capa)"
                    className="flex h-5 w-5 items-center justify-center rounded-full bg-zinc-700 text-white hover:bg-zinc-900"
                  >
                    <GripVertical className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Manual URL input */}
      <div className="flex gap-2">
        <div className="relative flex-1">
          <LinkIcon className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
          <input
            type="url"
            value={manualUrl}
            onChange={(e) => setManualUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addManualUrl())}
            placeholder="Ou cole uma URL de imagem…"
            className="flex h-9 w-full rounded-lg border border-zinc-300 bg-white pl-8 pr-3 text-sm focus:border-facil-orange focus:outline-none focus:ring-2 focus:ring-facil-orange/30 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100 dark:placeholder:text-zinc-500"
          />
        </div>
        <Button type="button" variant="outline" size="sm" onClick={addManualUrl}>
          <ImageIcon className="mr-1 h-3.5 w-3.5" />
          Adicionar
        </Button>
      </div>

      {localPreviews.length > 0 && (
        <p className="text-xs text-zinc-400 dark:text-zinc-500">
          {localPreviews.length} imagem(ns) · Hover para reordenar ou remover · Primeira é a capa
        </p>
      )}

      <Dialog open={!!confirmRemoveId} onOpenChange={(o) => !o && setConfirmRemoveId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Remover imagem?</DialogTitle>
            <DialogDescription>
              Esta ação remove a foto da lista. Você pode adicionar novamente depois.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button type="button" variant="outline" onClick={() => setConfirmRemoveId(null)}>
              Cancelar
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                if (confirmRemoveId) removePreview(confirmRemoveId);
                setConfirmRemoveId(null);
              }}
            >
              Remover
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
