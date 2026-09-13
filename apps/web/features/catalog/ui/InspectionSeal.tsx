import Image from "next/image";
import { shouldShowInspectionSeal } from "@/features/vehicle/lib/inspection-seal";

type Props = {
  result?: string | null;
  className?: string;
};

export function InspectionSeal({ result, className }: Props) {
  if (!shouldShowInspectionSeal(result)) return null;

  return (
    <span className={className ?? "absolute right-3 top-3 z-10"}>
      <Image
        src="/selo-pericia.png"
        alt="Aprovado na perícia"
        width={72}
        height={72}
        className="h-14 w-14 object-contain drop-shadow-md sm:h-16 sm:w-16"
      />
    </span>
  );
}
