import Link from "next/link";
import { notFound } from "next/navigation";
import { getBlogPostById } from "@/features/content/server/queries";
import { BlogPostForm } from "../BlogPostForm";

export default async function AdminBlogPostEditPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const post = await getBlogPostById(id);
  if (!post) notFound();

  return (
    <main className="p-6">
      <Link href="/admin/blog" className="text-sm text-zinc-600 hover:underline">
        ← Voltar
      </Link>
      <h1 className="mt-4 text-2xl font-semibold">Editar: {post.title}</h1>
      <BlogPostForm post={post} />
    </main>
  );
}
