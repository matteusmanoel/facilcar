"use server";

import { prisma } from "@/lib/db";

export async function updatePageAction(formData: FormData) {
  const id = formData.get("id") as string;
  if (!id) return { ok: false, error: "id obrigatório" };

  const slug = (formData.get("slug") as string)?.trim();
  const title = (formData.get("title") as string)?.trim();
  const excerpt = (formData.get("excerpt") as string)?.trim() || null;
  const body = (formData.get("body") as string)?.trim() || "";
  const status = (formData.get("status") as string) === "PUBLISHED" ? "PUBLISHED" : "DRAFT";
  const metaTitle = (formData.get("metaTitle") as string)?.trim() || null;
  const metaDescription = (formData.get("metaDescription") as string)?.trim() || null;

  if (!slug || !title) return { ok: false, error: "slug e título obrigatórios" };

  await prisma.page.update({
    where: { id },
    data: { slug, title, excerpt, body, status, metaTitle, metaDescription },
  });
  return { ok: true };
}

export async function updateBlogPostAction(formData: FormData) {
  const id = formData.get("id") as string;
  if (!id) return { ok: false, error: "id obrigatório" };

  const slug = (formData.get("slug") as string)?.trim();
  const title = (formData.get("title") as string)?.trim();
  const excerpt = (formData.get("excerpt") as string)?.trim() || null;
  const body = (formData.get("body") as string)?.trim() || "";
  const status = (formData.get("status") as string) === "PUBLISHED" ? "PUBLISHED" : "DRAFT";
  const coverImageUrl = (formData.get("coverImageUrl") as string)?.trim() || null;
  const metaTitle = (formData.get("metaTitle") as string)?.trim() || null;
  const metaDescription = (formData.get("metaDescription") as string)?.trim() || null;

  if (!slug || !title) return { ok: false, error: "slug e título obrigatórios" };

  const data: Parameters<typeof prisma.blogPost.update>[0]["data"] = {
    slug,
    title,
    excerpt,
    body,
    status,
    coverImageUrl,
    metaTitle,
    metaDescription,
  };
  if (status === "PUBLISHED") {
    const existing = await prisma.blogPost.findUnique({ where: { id }, select: { publishedAt: true } });
    if (!existing?.publishedAt) data.publishedAt = new Date();
  }

  await prisma.blogPost.update({
    where: { id },
    data,
  });
  return { ok: true };
}
