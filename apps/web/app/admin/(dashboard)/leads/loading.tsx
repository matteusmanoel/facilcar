import { AdminListPageSkeleton } from "@/components/admin/AdminListPageSkeleton";

export default function AdminLeadsLoading() {
  return (
    <AdminListPageSkeleton
      titleWidth="w-32"
      subtitleWidth="w-64"
      filterCount={1}
      showAction
    />
  );
}
