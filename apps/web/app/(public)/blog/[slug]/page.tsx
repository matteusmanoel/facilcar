import { getBlogPostBySlug } from "@/features/content/server/queries";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) return { title: "Post" };
  return {
    title: post.metaTitle ?? post.title,
    description: post.metaDescription ?? post.excerpt ?? undefined,
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) notFound();

  return (
    <main className="min-h-screen py-12 px-4">
      <article className="mx-auto max-w-3xl">
        <Link href="/blog" className="text-sm font-medium text-facil-orange hover:underline">
          ← Blog
        </Link>
        {post.coverImageUrl && (
          <div className="mt-6 overflow-hidden rounded-2xl border border-zinc-200">
            <img
              src={post.coverImageUrl}
              alt=""
              className="aspect-video w-full object-cover"
            />
          </div>
        )}
        <h1 className="mt-8 text-3xl font-extrabold text-zinc-900 md:text-4xl">{post.title}</h1>
        {post.excerpt && <p className="mt-4 text-lg text-facil-muted">{post.excerpt}</p>}
        <div className="mt-8 prose prose-zinc max-w-none whitespace-pre-wrap leading-relaxed text-facil-muted">
          {post.body}
        </div>
      </article>
    </main>
  );
}
