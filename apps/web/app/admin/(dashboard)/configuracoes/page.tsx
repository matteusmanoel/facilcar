import { getSiteSettings } from "@/features/settings/server/queries";
import { SettingsForm } from "./SettingsForm";

export default async function AdminConfiguracoesPage() {
  const settings = await getSiteSettings();
  if (!settings) {
    return (
      <main className="p-6">
        <h1 className="text-2xl font-semibold">Configurações</h1>
        <p className="mt-4 text-zinc-600">Nenhuma configuração encontrada. Execute o seed.</p>
      </main>
    );
  }

  return (
    <main className="p-6">
      <h1 className="text-2xl font-semibold">Configurações</h1>
      <SettingsForm settings={settings} />
    </main>
  );
}
