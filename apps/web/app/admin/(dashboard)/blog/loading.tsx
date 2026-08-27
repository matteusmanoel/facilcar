import { AdminListPageSkeleton } from "@/components/admin/AdminListPageSkeleton";

export default function AdminBlogLoading() {
  return (
    <AdminListPageSkeleton
      titleWidth="w-24"
      subtitleWidth="w-44"
      filterCount={1}
    />
  );
}
