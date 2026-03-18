import { prisma } from "@/lib/db";

export async function getPageBySlug(slug: string) {
  return prisma.page.findUnique({
    where: { slug, status: "PUBLISHED" },
  });
}

export async function listPublishedBlogPosts(limit = 50) {
  return prisma.blogPost.findMany({
    where: { status: "PUBLISHED" },
    orderBy: { publishedAt: "desc" },
    take: limit,
  });
}

export async function getBlogPostBySlug(slug: string) {
  return prisma.blogPost.findUnique({
    where: { slug, status: "PUBLISHED" },
  });
}

export async function listAdminPages() {
  return prisma.page.findMany({
    orderBy: { updatedAt: "desc" },
  });
}

export async function getPageById(id: string) {
  return prisma.page.findUnique({ where: { id } });
}

export async function listAdminBlogPosts() {
  return prisma.blogPost.findMany({
    orderBy: { updatedAt: "desc" },
  });
}

export async function getBlogPostById(id: string) {
  return prisma.blogPost.findUnique({ where: { id } });
}
