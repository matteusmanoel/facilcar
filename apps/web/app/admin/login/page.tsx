import { auth, signIn } from "@/features/auth/server/auth";
import { redirect } from "next/navigation";

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ callbackUrl?: string; error?: string }>;
}) {
  const session = await auth();
  const params = await searchParams;
  if (session?.user) {
    redirect(params.callbackUrl ?? "/admin");
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-zinc-100 p-4 dark:bg-zinc-950">
      <div className="w-full max-w-sm rounded-lg border border-zinc-200 bg-white p-6 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="mb-4 text-xl font-semibold text-zinc-900 dark:text-zinc-100">
          Login Admin
        </h1>
        {params.error === "CredentialsSignin" && (
          <p className="mb-2 text-sm text-red-600 dark:text-red-400">
            E-mail ou senha inválidos.
          </p>
        )}
        <form
          action={async (formData: FormData) => {
            "use server";
            await signIn("credentials", {
              email: formData.get("email") as string,
              password: formData.get("password") as string,
              redirectTo: params.callbackUrl ?? "/admin",
            });
          }}
          className="flex flex-col gap-3"
        >
          <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            E-mail
            <input
              name="email"
              type="email"
              required
              className="mt-1 w-full rounded border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </label>
          <label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            Senha
            <input
              name="password"
              type="password"
              required
              className="mt-1 w-full rounded border border-zinc-300 bg-white px-3 py-2 text-zinc-900 dark:border-zinc-700 dark:bg-zinc-950 dark:text-zinc-100"
            />
          </label>
          <button
            type="submit"
            className="rounded bg-zinc-900 py-2 text-white hover:bg-zinc-800 dark:bg-facil-orange dark:hover:bg-facil-orange-hover"
          >
            Entrar
          </button>
        </form>
      </div>
    </main>
  );
}
