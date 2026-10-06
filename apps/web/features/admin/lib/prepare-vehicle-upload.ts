export const VEHICLE_UPLOAD_MAX_WIDTH = 1600;
const JPEG_QUALITY = 0.82;

export function shouldReencodeVehiclePhoto(type: string): boolean {
  return type.startsWith("image/") && type !== "image/gif" && type !== "image/svg+xml";
}

export function jpegUploadName(filename: string): string {
  const base = filename.replace(/\.[^.]+$/, "") || "foto";
  return `${base}.jpg`;
}

/** Shrink a photo before the presigned upload. GIF, SVG, and canvas failures keep the original file. */
export async function prepareVehicleUpload(file: File): Promise<File> {
  if (!shouldReencodeVehiclePhoto(file.type)) return file;
  try {
    const bitmap = await createImageBitmap(file);
    const scale = bitmap.width > VEHICLE_UPLOAD_MAX_WIDTH ? VEHICLE_UPLOAD_MAX_WIDTH / bitmap.width : 1;
    const width = Math.max(1, Math.round(bitmap.width * scale));
    const height = Math.max(1, Math.round(bitmap.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      bitmap.close();
      return file;
    }
    ctx.drawImage(bitmap, 0, 0, width, height);
    bitmap.close();
    const blob = await new Promise<Blob | null>((resolve) => {
      canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY);
    });
    if (!blob) return file;
    return new File([blob], jpegUploadName(file.name), { type: "image/jpeg" });
  } catch {
    return file;
  }
}
