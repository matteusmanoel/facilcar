import { guardAdminSection } from "@/features/auth/server/rbac";
import { prisma } from "@/lib/db";
import { TestimonialsClient } from "./TestimonialsClient";

export default async function AdminDepoimentosPage() {
  await guardAdminSection("depoimentos");

  const testimonials = await prisma.testimonial.findMany({
    orderBy: [{ sortOrder: "asc" }, { createdAt: "desc" }],
  });

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Depoimentos</h1>
        <p className="mt-0.5 text-sm text-facil-muted">
          Gerencie os depoimentos exibidos na página inicial
        </p>
      </div>
      <TestimonialsClient testimonials={testimonials} />
    </div>
  );
}
