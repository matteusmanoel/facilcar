import Link from "next/link";
import type { BlogPost } from "@prisma/client";
import { cn } from "@/lib/cn";

type Props = {
  post: Pick<BlogPost, "slug" | "title" | "excerpt" | "coverImageUrl">;
  headingLevel?: "h2" | "h3";
};

export function BlogCard({ post, headingLevel = "h2" }: Props) {
  const Heading = headingLevel;

  return (
    <Link href={`/blog/${post.slug}`} className="vehicle-card group">
      <div className="relative aspect-[4/3] shrink-0 overflow-hidden bg-facil-surface">
        {post.coverImageUrl ? (
          <img
            src={post.coverImageUrl}
            alt=""
            className="h-full w-full object-cover transition duration-500 group-hover:scale-105"
          />
        ) : (
          <div className="flex h-full items-center justify-center bg-gradient-to-br from-facil-black to-zinc-800 text-sm font-bold text-facil-orange">
            FácilCar
          </div>
        )}
      </div>
      <div className="flex min-h-0 flex-1 flex-col bg-white p-5 dark:bg-zinc-900/40">
        <Heading
          className={cn(
            "line-clamp-2 text-lg font-bold leading-snug text-zinc-950 transition-colors group-hover:text-facil-orange dark:text-zinc-50",
          )}
        >
          {post.title}
        </Heading>
        {post.excerpt ? (
          <p className="mt-1 line-clamp-2 text-sm text-facil-muted">{post.excerpt}</p>
        ) : null}
        <div className="mt-auto flex items-end justify-between gap-3 pt-4">
          <p className="text-sm font-medium text-facil-muted">Artigo</p>
          <span className="shrink-0 rounded-lg border border-zinc-200 px-3 py-1.5 text-sm font-medium text-zinc-700 transition group-hover:border-facil-orange group-hover:text-facil-orange dark:border-zinc-700 dark:text-zinc-200">
            Ler artigo
          </span>
        </div>
      </div>
    </Link>
  );
}
