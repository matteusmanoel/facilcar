import { listAdminBlogPosts } from "@/features/content/server/queries";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { BlogClient } from "./BlogClient";

export default async function AdminBlogPage() {
  await guardAdminSection("blog");
  const posts = await listAdminBlogPosts();

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="text-2xl font-bold text-foreground">Blog</h1>
        <p className="mt-0.5 text-sm text-facil-muted">Gerencie posts e publicações do site</p>
      </div>

      <BlogClient posts={posts} />
    </div>
  );
}
