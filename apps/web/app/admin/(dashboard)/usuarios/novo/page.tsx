import { redirect } from "next/navigation";

export default function AdminUsuarioNovoRedirect() {
  redirect("/admin/usuarios?novo=1");
}
