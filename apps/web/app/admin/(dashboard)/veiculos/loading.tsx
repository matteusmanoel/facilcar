import { AdminListPageSkeleton } from "@/components/admin/AdminListPageSkeleton";

export default function AdminVeiculosLoading() {
  return (
    <AdminListPageSkeleton
      titleWidth="w-36"
      subtitleWidth="w-56"
      filterCount={1}
      showAction
    />
  );
}
