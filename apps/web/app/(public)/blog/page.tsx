import Link from "next/link";
import { listPublishedBlogPosts } from "@/features/content/server/queries";

export default async function BlogPage() {
  const posts = await listPublishedBlogPosts();

  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-4xl">
        <h1 className="text-2xl font-semibold">Blog</h1>
        {posts.length === 0 ? (
          <p className="mt-4 text-zinc-600">Nenhum post publicado.</p>
        ) : (
          <ul className="mt-6 space-y-4">
            {posts.map((post) => (
              <li key={post.id}>
                <Link href={`/blog/${post.slug}`} className="block rounded-lg border p-4 hover:bg-zinc-50">
                  <h2 className="font-medium">{post.title}</h2>
                  {post.excerpt && <p className="mt-1 text-sm text-zinc-600">{post.excerpt}</p>}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}
