import { test, expect, type Page } from "@playwright/test";

/**
 * Credenciais demo (prisma/seed.ts):
 * - admin@facilcar.demo / ChangeMe123! (SUPER_ADMIN)
 * - vendedor@facilcar.demo / ChangeMe123! (LEAD_MANAGER)
 * - editor@facilcar.demo / ChangeMe123! (EDITOR)
 *
 * Variáveis opcionais sobrescrevem os defaults demo.
 */
const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@facilcar.demo";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "ChangeMe123!";
const leadManagerEmail = process.env.E2E_LEAD_MANAGER_EMAIL ?? "vendedor@facilcar.demo";
const leadManagerPassword = process.env.E2E_LEAD_MANAGER_PASSWORD ?? "ChangeMe123!";

async function loginAs(page: Page, email: string, password: string) {
  await page.goto("/admin/login");
  await page.getByLabel("E-mail").fill(email);
  await page.getByLabel("Senha").fill(password);
  await page.getByRole("button", { name: "Entrar" }).click();
  await expect(page).toHaveURL(/\/admin\/?$/);
}

test.describe("RBAC — perfil admin (SUPER_ADMIN)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, adminEmail, adminPassword);
  });

  test("acessa gestão de usuários", async ({ page }) => {
    await page.goto("/admin/usuarios");
    await expect(page.getByRole("heading", { name: "Usuários" })).toBeVisible();
  });

  test("acessa cadastro de veículo", async ({ page }) => {
    await page.goto("/admin/veiculos/novo");
    await expect(page.getByRole("heading", { name: "Novo veículo" })).toBeVisible();
  });
});

test.describe("RBAC — perfil vendedor (LEAD_MANAGER)", () => {
  test.beforeEach(async ({ page }) => {
    await loginAs(page, leadManagerEmail, leadManagerPassword);
  });

  test("usuários redireciona com forbidden", async ({ page }) => {
    await page.goto("/admin/usuarios");
    await expect(page).toHaveURL(/\/admin\/?(\?forbidden=1)?$/);
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("acessa lista de leads", async ({ page }) => {
    await page.goto("/admin/leads");
    await expect(page.getByRole("heading", { name: /Leads/i })).toBeVisible();
  });
});
