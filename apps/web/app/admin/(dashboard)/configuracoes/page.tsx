import { getSiteSettings } from "@/features/settings/server/queries";
import { guardAdminSection } from "@/features/auth/server/rbac";
import { SettingsForm } from "./SettingsForm";

export default async function AdminConfiguracoesPage() {
  await guardAdminSection("configuracoes");
  const settings = await getSiteSettings();
  if (!settings) {
    return (
      <div className="admin-page">
        <h1 className="text-2xl font-bold text-zinc-900">Configurações</h1>
        <p className="mt-4 text-sm text-zinc-500">Nenhuma configuração encontrada. Execute o seed.</p>
      </div>
    );
  }

  return (
    <div className="admin-page admin-section">
      <div>
        <h1 className="admin-page-title">Configurações</h1>
        <p className="admin-page-subtitle">Informações do site e contato</p>
      </div>
      <SettingsForm settings={settings} />
    </div>
  );
}
