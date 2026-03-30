import { redirect } from "next/navigation";

export default function AdminCrmPage() {
  redirect("/admin/leads?view=kanban");
}
