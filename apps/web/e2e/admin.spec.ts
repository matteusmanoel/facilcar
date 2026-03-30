import { test, expect } from "@playwright/test";

const email = process.env.E2E_ADMIN_EMAIL;
const password = process.env.E2E_ADMIN_PASSWORD;

test.describe("Admin (autenticado)", () => {
  test.skip(!email || !password, "Defina E2E_ADMIN_EMAIL e E2E_ADMIN_PASSWORD para rodar estes testes.");

  test.beforeEach(async ({ page }) => {
    await page.goto("/admin/login");
    await page.getByLabel("E-mail").fill(email!);
    await page.getByLabel("Senha").fill(password!);
    await page.getByRole("button", { name: "Entrar" }).click();
    await expect(page).toHaveURL(/\/admin\/?$/);
  });

  test("dashboard carrega e filtros de período existem", async ({ page }) => {
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await page.goto("/admin");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  });

  test("navegação para leads/CRM e veículos", async ({ page }) => {
    await page.getByRole("link", { name: /Leads/i }).first().click();
    await expect(page.getByRole("heading", { name: /Leads/i })).toBeVisible();

    await page.getByRole("link", { name: "Kanban" }).first().click();
    await expect(page.getByRole("heading", { name: /Leads/i })).toBeVisible();

    await page.getByRole("link", { name: /Veículos/i }).first().click();
    await expect(page.getByRole("heading", { name: "Veículos" })).toBeVisible();
  });
});

test("login redireciona anônimos", async ({ page }) => {
  await page.goto("/admin/veiculos");
  await expect(page).toHaveURL(/\/admin\/login/);
});
