import { getBlogPostBySlug } from "@/features/content/server/queries";
import { notFound } from "next/navigation";

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) notFound();

  return (
    <main className="min-h-screen py-12 px-4">
      <article className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-semibold">{post.title}</h1>
        {post.excerpt && <p className="mt-2 text-zinc-600">{post.excerpt}</p>}
        <div className="mt-6 prose prose-zinc max-w-none whitespace-pre-wrap">
          {post.body}
        </div>
      </article>
    </main>
  );
}
