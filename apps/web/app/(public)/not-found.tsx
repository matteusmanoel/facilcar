import type { Metadata } from "next";
import { PublicNotFound } from "@/components/shared/PublicNotFound";

export const metadata: Metadata = {
  title: "Página não encontrada",
  robots: { index: false, follow: false },
};

export default function PublicSegmentNotFound() {
  return <PublicNotFound />;
}
