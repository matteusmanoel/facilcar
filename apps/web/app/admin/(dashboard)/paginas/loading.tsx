import { AdminListPageSkeleton } from "@/components/admin/AdminListPageSkeleton";

export default function AdminPaginasLoading() {
  return (
    <AdminListPageSkeleton
      titleWidth="w-28"
      subtitleWidth="w-48"
      filterCount={0}
    />
  );
}
