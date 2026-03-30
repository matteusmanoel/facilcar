import { getSiteSettings } from "@/features/settings/server/queries";
import { SettingsForm } from "./SettingsForm";

export default async function AdminConfiguracoesPage() {
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
        <h1 className="text-2xl font-bold text-zinc-900 dark:text-zinc-50">Configurações</h1>
        <p className="mt-0.5 text-sm text-zinc-500 dark:text-zinc-400">Informações do site e contato</p>
      </div>
      <SettingsForm settings={settings} />
    </div>
  );
}
