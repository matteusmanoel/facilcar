/** Derived age from a validated birth date using America/Sao_Paulo. */

const TZ = "America/Sao_Paulo";

function partsInZone(instant: Date, timeZone: string): { year: number; month: number; day: number } {
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const [year, month, day] = fmt.format(instant).split("-").map(Number);
  return { year, month, day };
}

export function ageFromBirthDate(
  birth: string | Date | null | undefined,
  now: Date = new Date(),
): number | null {
  if (birth == null || birth === "") return null;
  let year: number;
  let month: number;
  let day: number;
  if (birth instanceof Date) {
    if (Number.isNaN(birth.getTime())) return null;
    year = birth.getUTCFullYear();
    month = birth.getUTCMonth() + 1;
    day = birth.getUTCDate();
  } else {
    const text = String(birth).trim();
    const iso = text.match(/^(\d{4})-(\d{2})-(\d{2})/);
    const br = text.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
    if (iso) {
      year = Number(iso[1]);
      month = Number(iso[2]);
      day = Number(iso[3]);
    } else if (br) {
      day = Number(br[1]);
      month = Number(br[2]);
      year = Number(br[3]);
    } else {
      return null;
    }
  }
  const born = new Date(Date.UTC(year, month - 1, day));
  if (
    born.getUTCFullYear() !== year ||
    born.getUTCMonth() + 1 !== month ||
    born.getUTCDate() !== day
  ) {
    return null;
  }
  const today = partsInZone(now, TZ);
  const age = today.year - year - (today.month * 100 + today.day < month * 100 + day ? 1 : 0);
  if (age <= 0 || age >= 130) return null;
  return age;
}
