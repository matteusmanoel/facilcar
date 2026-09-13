import { listPublishedBlogPosts } from "@/features/content/server/queries";
import { BlogCard } from "@/features/content/ui/BlogCard";

export const metadata = {
  title: "Blog",
  description: "Dicas sobre seminovos, financiamento e mercado automotivo — FácilCar.",
};

export default async function BlogPage() {
  const posts = await listPublishedBlogPosts();

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-3xl font-extrabold text-foreground">Blog</h1>
        <p className="mt-2 text-facil-muted">
          Conteúdo para quem quer comprar ou vender com segurança.
        </p>
        {posts.length === 0 ? (
          <p className="mt-8 text-facil-muted">Nenhum post publicado.</p>
        ) : (
          <div className="mt-10 grid items-stretch gap-3 sm:grid-cols-2 sm:gap-4 lg:grid-cols-3">
            {posts.map((post) => (
              <BlogCard key={post.id} post={post} />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
