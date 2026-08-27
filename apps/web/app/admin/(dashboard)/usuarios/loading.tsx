import { AdminListPageSkeleton } from "@/components/admin/AdminListPageSkeleton";

export default function AdminUsuariosLoading() {
  return (
    <AdminListPageSkeleton
      titleWidth="w-32"
      subtitleWidth="w-52"
      filterCount={1}
    />
  );
}
