import { getBlogPostBySlug } from "@/features/content/server/queries";
import { getSiteSettings } from "@/features/settings/server/queries";
import { notFound } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import { BRAND } from "@/lib/brand";
import { SITE_URL, buildBlogPostingJsonLd } from "@/lib/seo";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const post = await getBlogPostBySlug(slug);
  if (!post) return { title: "Post" };
  const title = post.metaTitle ?? post.title;
  const description = post.metaDescription ?? post.excerpt ?? undefined;
  const url = `${SITE_URL}/blog/${post.slug}`;
  return {
    title,
    description,
    alternates: { canonical: url },
    openGraph: {
      title,
      description,
      type: "article",
      locale: "pt_BR",
      url,
      ...(post.coverImageUrl ? { images: [{ url: post.coverImageUrl, alt: title }] } : {}),
      ...(post.publishedAt ? { publishedTime: post.publishedAt.toISOString() } : {}),
    },
  };
}

export default async function BlogPostPage({ params }: Props) {
  const { slug } = await params;
  const [post, settings] = await Promise.all([
    getBlogPostBySlug(slug),
    getSiteSettings(),
  ]);
  if (!post) notFound();

  const jsonLd = buildBlogPostingJsonLd(post, settings?.siteName ?? BRAND.name);

  return (
    <main className="min-h-screen py-12 px-4">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <article className="mx-auto max-w-3xl">
        <Link href="/blog" className="text-sm font-medium text-facil-orange hover:underline">
          ← Blog
        </Link>
        {post.coverImageUrl && (
          <div className="mt-6 overflow-hidden rounded-2xl border border-facil-border">
            <img
              src={post.coverImageUrl}
              alt=""
              className="aspect-video w-full object-cover"
            />
          </div>
        )}
        <h1 className="mt-8 text-3xl font-extrabold text-foreground md:text-4xl">{post.title}</h1>
        {post.excerpt && <p className="mt-4 text-lg text-facil-muted">{post.excerpt}</p>}
        <div className="mt-8 public-prose">
          {post.body}
        </div>
      </article>
    </main>
  );
}
