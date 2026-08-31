import { test, expect } from "@playwright/test";

test("404 público mostra ícone e volta ao estoque", async ({ page }) => {
  const res = await page.goto("/pagina-que-nao-existe");
  expect(res?.status()).toBe(404);
  await expect(page.getByRole("heading", { name: "Página não encontrada" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Ver estoque" })).toBeVisible();
  await page.getByRole("link", { name: "Ver estoque" }).click();
  await expect(page).toHaveURL(/\/estoque/);
});
