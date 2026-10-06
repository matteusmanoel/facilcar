export const VEHICLE_PLACEHOLDER_SRC = "/vehicle-placeholder.webp";
const LEGACY_PLACEHOLDER = "/no-image.svg";

export function isInvalidVehicleImageUrl(url: string | null | undefined): boolean {
  if (!url || !url.trim()) return true;
  const value = url.trim();
  return (
    value.startsWith("/mock/") ||
    value === VEHICLE_PLACEHOLDER_SRC ||
    value === LEGACY_PLACEHOLDER
  );
}

/** Remote storage URLs are rendered directly, outside the image optimizer. */
export function isDirectVehicleImageUrl(url: string | null | undefined): boolean {
  if (!url || isInvalidVehicleImageUrl(url)) return false;
  return /^https?:\/\//i.test(url.trim());
}
