/**
 * Production seed — admin + SiteSettings + brands + institutional pages.
 * No demo vehicles / demo staff / demo leads.
 *
 * Usage:
 *   SEED_ADMIN_EMAIL=... SEED_ADMIN_PASSWORD=... SEED_ADMIN_NAME=... \
 *   DATABASE_URL="postgresql://..." npx tsx prisma/seed-prod.ts
 */
import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";
import { hashPassword } from "../features/auth/server/passwords";
import { getPgPoolSslExtras, normalizeDatabaseUrl } from "../lib/database-url";

const rawUrl =
  process.env.DATABASE_URL ?? "postgresql://postgres:postgres@127.0.0.1:5432/facilcar";
const connectionString = normalizeDatabaseUrl(rawUrl);
const pool = new Pool({
  connectionString,
  ...getPgPoolSslExtras(connectionString),
});
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

const adminEmail = process.env.SEED_ADMIN_EMAIL ?? "miltonvendas@hotmail.com";
const adminPassword = process.env.SEED_ADMIN_PASSWORD;
const adminName = process.env.SEED_ADMIN_NAME ?? "Milton Barrios";

async function main() {
  if (!adminPassword || adminPassword.length < 8) {
    throw new Error("SEED_ADMIN_PASSWORD is required (min 8 chars)");
  }

  const settingsData = {
    siteName: "FácilCar Multimarcas",
    defaultWhatsappNumber: "5545999974232",
    defaultEmail: "miltonvendas@hotmail.com",
    phoneNumber: "5545999974232",
    addressLine: "R. Ipanema, 1206 - Periolo",
    city: "Cascavel",
    state: "PR",
    zipCode: "85817-020",
    instagramUrl: "https://www.instagram.com/facilcarmultimarcas/",
    facebookUrl: null as string | null,
    youtubeUrl: null as string | null,
    seoDefaultTitle: "FácilCar Multimarcas | Seminovos e financiamento",
    seoDefaultDescription:
      "Seminovos selecionados, financiamento facilitado e venda/consignação com segurança. FácilCar Multimarcas — Cascavel/PR.",
    footerText:
      "Há anos conectando pessoas ao carro certo. Transparência, agilidade e atendimento que faz a diferença.",
    heroTitle: "Seu próximo carro, do jeito mais fácil.",
    heroSubtitle:
      "Estoque curado, financiamento com especialistas e avaliação justa do seu usado — tudo em um só lugar.",
    publicTheme: "dark",
  };

  const existingSettings = await prisma.siteSettings.findFirst();
  if (!existingSettings) {
    await prisma.siteSettings.create({ data: settingsData });
  } else {
    await prisma.siteSettings.update({
      where: { id: existingSettings.id },
      data: settingsData,
    });
  }

  const brandSlugs = [
    "chevrolet",
    "volkswagen",
    "toyota",
    "honda",
    "fiat",
    "ford",
    "jeep",
    "nissan",
    "hyundai",
    "renault",
  ];
  const brandNames: Record<string, string> = {
    chevrolet: "Chevrolet",
    volkswagen: "Volkswagen",
    toyota: "Toyota",
    honda: "Honda",
    fiat: "Fiat",
    ford: "Ford",
    jeep: "Jeep",
    nissan: "Nissan",
    hyundai: "Hyundai",
    renault: "Renault",
  };

  for (const slug of brandSlugs) {
    await prisma.brand.upsert({
      where: { slug },
      create: { name: brandNames[slug] ?? slug, slug, isActive: true },
      update: {},
    });
  }

  const pages = [
    {
      slug: "quem-somos",
      title: "Quem somos",
      excerpt: "A FácilCar nasceu para simplificar comprar e vender carro.",
      body: `A FácilCar Multimarcas é uma revenda focada em seminovos com curadoria real: cada veículo passa por conferência antes de ir para o site.

Nossa missão é oferecer transparência, agilidade e um atendimento humano — do primeiro WhatsApp até a assinatura do contrato. Trabalhamos com financiamento junto às principais financeiras e com consignação para quem quer vender com segurança.

Valores: honestidade nas condições, respeito ao tempo do cliente e compromisso com pós-venda claro.

Venha nos visitar em Cascavel/PR ou fale pelo WhatsApp.`,
      metaTitle: "Quem somos | FácilCar Multimarcas",
      metaDescription: "Conheça a FácilCar: seminovos, financiamento e consignação com transparência em Cascavel/PR.",
    },
    {
      slug: "politica-de-privacidade",
      title: "Política de privacidade",
      excerpt: "Como tratamos seus dados.",
      body: `Coletamos dados de contato e interesse em veículos apenas para atendimento comercial. Não vendemos seus dados a terceiros.

Para solicitações relacionadas a privacidade, contate miltonvendas@hotmail.com.`,
      metaTitle: "Política de privacidade | FácilCar Multimarcas",
      metaDescription: "Como a FácilCar trata dados pessoais de leads e clientes.",
    },
  ];

  for (const page of pages) {
    await prisma.page.upsert({
      where: { slug: page.slug },
      create: {
        ...page,
        status: "PUBLISHED",
      },
      update: {
        title: page.title,
        excerpt: page.excerpt,
        body: page.body,
        metaTitle: page.metaTitle,
        metaDescription: page.metaDescription,
      },
    });
  }

  const passwordHash = await hashPassword(adminPassword);
  await prisma.user.upsert({
    where: { email: adminEmail },
    create: {
      name: adminName,
      email: adminEmail,
      passwordHash,
      role: "ADMIN",
      isActive: true,
    },
    update: {
      passwordHash,
      name: adminName,
      role: "ADMIN",
      isActive: true,
    },
  });

  console.log(`Seed prod completed. Admin: ${adminEmail}`);
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
