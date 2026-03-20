import Link from "next/link";
import { listPublishedBlogPosts } from "@/features/content/server/queries";

export const metadata = {
  title: "Blog",
  description: "Dicas sobre seminovos, financiamento e mercado automotivo — FácilCar.",
};

export default async function BlogPage() {
  const posts = await listPublishedBlogPosts();

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-3xl font-extrabold text-zinc-900">Blog</h1>
        <p className="mt-2 text-facil-muted">
          Conteúdo para quem quer comprar ou vender com segurança.
        </p>
        {posts.length === 0 ? (
          <p className="mt-8 text-facil-muted">Nenhum post publicado.</p>
        ) : (
          <div className="mt-10 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {posts.map((post) => (
              <Link
                key={post.id}
                href={`/blog/${post.slug}`}
                className="group overflow-hidden rounded-2xl border border-zinc-200 bg-white shadow-sm transition hover:border-facil-orange/30 hover:shadow-lg"
              >
                <div className="aspect-video overflow-hidden bg-zinc-100">
                  {post.coverImageUrl ? (
                    <img
                      src={post.coverImageUrl}
                      alt=""
                      className="h-full w-full object-cover transition group-hover:scale-105"
                    />
                  ) : (
                    <div className="flex h-full items-center justify-center bg-gradient-to-br from-facil-black to-zinc-800 text-sm font-bold text-facil-orange">
                      FácilCar
                    </div>
                  )}
                </div>
                <div className="p-5">
                  <h2 className="font-bold text-zinc-900 group-hover:text-facil-orange line-clamp-2">
                    {post.title}
                  </h2>
                  {post.excerpt && (
                    <p className="mt-2 line-clamp-2 text-sm text-facil-muted">{post.excerpt}</p>
                  )}
                  <span className="mt-3 inline-block text-sm font-semibold text-facil-orange">
                    Ler mais →
                  </span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
