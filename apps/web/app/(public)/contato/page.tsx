import { ContactForm } from "@/features/lead/ui/ContactForm";

export default function ContatoPage() {
  return (
    <main className="min-h-screen py-12 px-4">
      <div className="mx-auto max-w-6xl">
        <h1 className="text-2xl font-semibold">Contato</h1>
        <p className="mt-2 text-zinc-600">
          Preencha o formulário e retornaremos em breve.
        </p>
        <div className="mt-8">
          <ContactForm />
        </div>
      </div>
    </main>
  );
}
