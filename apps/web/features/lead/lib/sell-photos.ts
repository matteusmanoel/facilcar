export const SELL_PHOTO_MAX_FILES = 5;
export const SELL_PHOTO_MAX_BYTES = 4 * 1024 * 1024;

const JPEG = "image/jpeg";
const PNG = "image/png";
const WEBP = "image/webp";

const TYPE_BY_EXT: Record<string, string> = {
  jpg: JPEG,
  jpeg: JPEG,
  png: PNG,
  webp: WEBP,
};

export type SellPhotoUpload = {
  size: number;
  type?: string;
  name?: string;
  arrayBuffer: () => Promise<ArrayBuffer>;
};

export function isSellPhotoUpload(value: unknown): value is SellPhotoUpload {
  if (typeof value !== "object" || value === null) return false;
  const upload = value as Partial<SellPhotoUpload>;
  return typeof upload.size === "number" && upload.size > 0 && typeof upload.arrayBuffer === "function";
}

export function collectSellPhotoUploads(formData: FormData): SellPhotoUpload[] {
  const uploads: SellPhotoUpload[] = [];
  for (const value of formData.getAll("photos")) {
    if (isSellPhotoUpload(value)) uploads.push(value);
  }
  return uploads;
}

export function sellPhotoExt(contentType: string): string {
  if (contentType === PNG) return "png";
  if (contentType === WEBP) return "webp";
  return "jpg";
}

function typeFromDeclared(raw: string | undefined): string | null {
  const type = (raw ?? "").toLowerCase().split(";")[0]?.trim();
  if (type === JPEG || type === "image/jpg" || type === "image/pjpeg") return JPEG;
  if (type === PNG) return PNG;
  if (type === WEBP) return WEBP;
  return null;
}

function typeFromFileName(name: string | undefined): string | null {
  const ext = name?.toLowerCase().split(".").pop();
  if (!ext) return null;
  return TYPE_BY_EXT[ext] ?? null;
}

function typeFromMagicBytes(bytes: Uint8Array): string | null {
  if (bytes.length >= 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff) {
    return JPEG;
  }
  if (
    bytes.length >= 8 &&
    bytes[0] === 0x89 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x4e &&
    bytes[3] === 0x47
  ) {
    return PNG;
  }
  if (
    bytes.length >= 12 &&
    bytes[0] === 0x52 &&
    bytes[1] === 0x49 &&
    bytes[2] === 0x46 &&
    bytes[3] === 0x46 &&
    bytes[8] === 0x57 &&
    bytes[9] === 0x45 &&
    bytes[10] === 0x42 &&
    bytes[11] === 0x50
  ) {
    return WEBP;
  }
  return null;
}

export function inferSellPhotoContentType(
  upload: Pick<SellPhotoUpload, "type" | "name">,
  bytes: Uint8Array,
): string | null {
  return typeFromDeclared(upload.type) ?? typeFromFileName(upload.name) ?? typeFromMagicBytes(bytes);
}

export function visibleSellPhotoUrls(urls: string[] | null | undefined): string[] {
  if (!urls?.length) return [];
  return urls.filter((url) => {
    const trimmed = url.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith("/")) return !trimmed.startsWith("//");
    try {
      const parsed = new URL(trimmed);
      return parsed.protocol === "http:" || parsed.protocol === "https:";
    } catch {
      return false;
    }
  });
}
