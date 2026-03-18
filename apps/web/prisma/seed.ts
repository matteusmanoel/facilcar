import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";
import { hashPassword } from "../features/auth/server/passwords";

const connectionString = process.env.DATABASE_URL ?? "postgresql://localhost:5432/mvp?schema=public";
const pool = new Pool({ connectionString });
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

type VehicleSeed = {
  slug: string;
  brandSlug: string;
  featured: boolean;
  status: "PUBLISHED";
  type: "CAR" | "MOTORCYCLE" | "UTILITY" | "OTHER";
  title: string;
  shortDescription: string;
  description: string;
  model: string;
  version: string;
  yearManufacture: number;
  yearModel: number;
  mileage: number;
  fuelType: "GASOLINE" | "ETHANOL" | "FLEX" | "DIESEL" | "ELECTRIC" | "HYBRID" | "OTHER";
  transmission: "MANUAL" | "AUTOMATIC" | "AUTOMATED" | "CVT" | "OTHER";
  color: string;
  doors: number;
  priceCash: number;
  images: { url: string; isCover: boolean; sortOrder: number }[];
  features: string[];
};

const VEHICLE_SEEDS: VehicleSeed[] = [
  {
    slug: "toyota-corolla-xei-2022",
    brandSlug: "toyota",
    featured: true,
    status: "PUBLISHED",
    type: "CAR",
    title: "Toyota Corolla XEi 2.0 2022",
    shortDescription: "Sedã automático com excelente acabamento e baixa quilometragem.",
    description: "Veículo em ótimo estado, revisado, com multimídia, câmera de ré, bancos em couro.",
    model: "Corolla",
    version: "XEi 2.0",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 28500,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Prata",
    doors: 4,
    priceCash: 129900,
    images: [
      { url: "/mock/vehicles/corolla-1.jpg", isCover: true, sortOrder: 0 },
      { url: "/mock/vehicles/corolla-2.jpg", isCover: false, sortOrder: 1 },
    ],
    features: ["Ar-condicionado digital", "Central multimídia", "Câmera de ré", "Bancos em couro"],
  },
  {
    slug: "honda-civic-ex-2021",
    brandSlug: "honda",
    featured: true,
    status: "PUBLISHED",
    type: "CAR",
    title: "Honda Civic EX 2021",
    shortDescription: "Sedã confiável com câmbio automático.",
    description: "Ideal para quem busca conforto e economia.",
    model: "Civic",
    version: "EX",
    yearManufacture: 2021,
    yearModel: 2021,
    mileage: 41200,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Branco",
    doors: 4,
    priceCash: 117900,
    images: [
      { url: "/mock/vehicles/civic-1.jpg", isCover: true, sortOrder: 0 },
      { url: "/mock/vehicles/civic-2.jpg", isCover: false, sortOrder: 1 },
    ],
    features: ["Piloto automático", "Multimídia", "Airbags"],
  },
  {
    slug: "fiat-strada-freedom-2023",
    brandSlug: "fiat",
    featured: false,
    status: "PUBLISHED",
    type: "UTILITY",
    title: "Fiat Strada Freedom 2023",
    shortDescription: "Picape compacta prática.",
    description: "Veículo versátil, excelente custo-benefício.",
    model: "Strada",
    version: "Freedom",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 18000,
    fuelType: "FLEX",
    transmission: "MANUAL",
    color: "Cinza",
    doors: 2,
    priceCash: 103900,
    images: [{ url: "/mock/vehicles/strada-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Direção elétrica", "Ar-condicionado", "Vidros elétricos"],
  },
  {
    slug: "chevrolet-onix-lt-2023",
    brandSlug: "chevrolet",
    featured: true,
    status: "PUBLISHED",
    type: "CAR",
    title: "Chevrolet Onix LT 2023",
    shortDescription: "Hatch econômico e completo.",
    description: "Ótimo para cidade, baixo consumo, revisões acessíveis.",
    model: "Onix",
    version: "LT",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 12000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Vermelho",
    doors: 4,
    priceCash: 89900,
    images: [{ url: "/mock/vehicles/onix-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["MyLink", "Ar-condicionado", "Direção elétrica"],
  },
  {
    slug: "volkswagen-polo-highline-2022",
    brandSlug: "volkswagen",
    featured: true,
    status: "PUBLISHED",
    type: "CAR",
    title: "Volkswagen Polo Highline 2022",
    shortDescription: "Hatch premium com TSI.",
    description: "Motor turbo, acabamento superior, ótimo desempenho.",
    model: "Polo",
    version: "Highline TSI",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 35000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Azul",
    doors: 4,
    priceCash: 98900,
    images: [{ url: "/mock/vehicles/polo-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Motor turbo", "Paddle shift", "Sensor de estacionamento"],
  },
  {
    slug: "jeep-renegade-longitude-2021",
    brandSlug: "jeep",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Jeep Renegade Longitude 2021",
    shortDescription: "SUV compacta aventureira.",
    description: "Espaço interno confortável, posição de dirigir elevada.",
    model: "Renegade",
    version: "Longitude",
    yearManufacture: 2021,
    yearModel: 2021,
    mileage: 52000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Preto",
    doors: 4,
    priceCash: 112900,
    images: [{ url: "/mock/vehicles/renegade-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["4x2", "Central multimídia", "Controle de tração"],
  },
  {
    slug: "nissan-kicks-advance-2022",
    brandSlug: "nissan",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Nissan Kicks Advance 2022",
    shortDescription: "SUV urbano econômico.",
    description: "Design moderno, bom porta-malas para a categoria.",
    model: "Kicks",
    version: "Advance",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 31000,
    fuelType: "FLEX",
    transmission: "CVT",
    color: "Branco perolado",
    doors: 4,
    priceCash: 105900,
    images: [{ url: "/mock/vehicles/kicks-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Câmera 360", "Ar digital", "Keyless"],
  },
  {
    slug: "hyundai-hb20-platinum-2023",
    brandSlug: "hyundai",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Hyundai HB20 Platinum 2023",
    shortDescription: "Hatch com garantia de fábrica.",
    description: "Único dono, revisões em concessionária.",
    model: "HB20",
    version: "Platinum",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 15000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Cinza grafite",
    doors: 4,
    priceCash: 92900,
    images: [{ url: "/mock/vehicles/hb20-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Bluelink", "Wireless charger", "LED"],
  },
  {
    slug: "renault-duster-intense-2020",
    brandSlug: "renault",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Renault Duster Intense 2020",
    shortDescription: "SUV robusto para família.",
    description: "Amplo espaço interno, bom para viagens.",
    model: "Duster",
    version: "Intense",
    yearManufacture: 2020,
    yearModel: 2020,
    mileage: 68000,
    fuelType: "FLEX",
    transmission: "CVT",
    color: "Laranja",
    doors: 4,
    priceCash: 87900,
    images: [{ url: "/mock/vehicles/duster-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Multimídia", "Rack de teto", "Controle de estabilidade"],
  },
  {
    slug: "ford-ranger-xls-2022",
    brandSlug: "ford",
    featured: false,
    status: "PUBLISHED",
    type: "UTILITY",
    title: "Ford Ranger XLS 2022",
    shortDescription: "Picape média diesel.",
    description: "Motor 2.2 diesel, tração 4x4, ideal trabalho e lazer.",
    model: "Ranger",
    version: "XLS 2.2",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 45000,
    fuelType: "DIESEL",
    transmission: "MANUAL",
    color: "Branco",
    doors: 4,
    priceCash: 189900,
    images: [{ url: "/mock/vehicles/ranger-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["4x4", "Cabine dupla", "Engate"],
  },
  {
    slug: "toyota-hilux-srx-2021",
    brandSlug: "toyota",
    featured: false,
    status: "PUBLISHED",
    type: "UTILITY",
    title: "Toyota Hilux SRX 2021",
    shortDescription: "Picape topo de linha.",
    description: "Completa, revisada, histórico transparente.",
    model: "Hilux",
    version: "SRX 2.8",
    yearManufacture: 2021,
    yearModel: 2021,
    mileage: 55000,
    fuelType: "DIESEL",
    transmission: "AUTOMATIC",
    color: "Prata",
    doors: 4,
    priceCash: 249900,
    images: [{ url: "/mock/vehicles/hilux-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Teto solar", "Couro", "7 airbags"],
  },
  {
    slug: "honda-hr-v-exl-2023",
    brandSlug: "honda",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Honda HR-V EXL 2023",
    shortDescription: "SUV médio com tecnologia.",
    description: "Nova geração, painel digital, Honda Sensing.",
    model: "HR-V",
    version: "EXL",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 22000,
    fuelType: "FLEX",
    transmission: "CVT",
    color: "Preto",
    doors: 4,
    priceCash: 159900,
    images: [{ url: "/mock/vehicles/hrv-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Honda Sensing", "Teto solar", "Som premium"],
  },
  {
    slug: "fiat-toro-volcano-2022",
    brandSlug: "fiat",
    featured: false,
    status: "PUBLISHED",
    type: "UTILITY",
    title: "Fiat Toro Volcano 2022",
    shortDescription: "Picape média automática.",
    description: "Conforto de SUV com caçamba utilitária.",
    model: "Toro",
    version: "Volcano",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 48000,
    fuelType: "DIESEL",
    transmission: "AUTOMATIC",
    color: "Vermelho",
    doors: 4,
    priceCash: 149900,
    images: [{ url: "/mock/vehicles/toro-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["4x4", "Multimídia 10\"", "Bancos em couro"],
  },
  {
    slug: "chevrolet-tracker-premier-2022",
    brandSlug: "chevrolet",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Chevrolet Tracker Premier 2022",
    shortDescription: "SUV compacto turbo.",
    description: "Motor 1.0 e 1.2 turbo, ótimo torque urbano.",
    model: "Tracker",
    version: "Premier",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 39000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Branco",
    doors: 4,
    priceCash: 118900,
    images: [{ url: "/mock/vehicles/tracker-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["OnStar", "Wi-Fi", "CarPlay"],
  },
  {
    slug: "volkswagen-t-cross-comfortline-2023",
    brandSlug: "volkswagen",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Volkswagen T-Cross Comfortline 2023",
    shortDescription: "SUV entrada premium VW.",
    description: "Espaçoso, porta-malas versátil.",
    model: "T-Cross",
    version: "Comfortline",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 19000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Cinza",
    doors: 4,
    priceCash: 124900,
    images: [{ url: "/mock/vehicles/tcross-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Beats Audio", "Teto solar panorâmico", "LED"],
  },
  {
    slug: "jeep-compass-longitude-2020",
    brandSlug: "jeep",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Jeep Compass Longitude 2020",
    shortDescription: "SUV médio diesel.",
    description: "Economia em viagem, conforto em rodovia.",
    model: "Compass",
    version: "Longitude Diesel",
    yearManufacture: 2020,
    yearModel: 2020,
    mileage: 72000,
    fuelType: "DIESEL",
    transmission: "AUTOMATIC",
    color: "Verde militar",
    doors: 4,
    priceCash: 134900,
    images: [{ url: "/mock/vehicles/compass-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["4x4", "Teto solar", "Bancos aquecidos"],
  },
  {
    slug: "nissan-versa-advance-2023",
    brandSlug: "nissan",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Nissan Versa Advance 2023",
    shortDescription: "Sedã compacto espaçoso.",
    description: "Porta-malas amplo, conforto traseiro acima da média.",
    model: "Versa",
    version: "Advance",
    yearManufacture: 2023,
    yearModel: 2023,
    mileage: 8000,
    fuelType: "FLEX",
    transmission: "CVT",
    color: "Prata",
    doors: 4,
    priceCash: 99900,
    images: [{ url: "/mock/vehicles/versa-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["6 airbags", "Câmera de ré", "Ar digital"],
  },
  {
    slug: "hyundai-creta-platinum-2022",
    brandSlug: "hyundai",
    featured: false,
    status: "PUBLISHED",
    type: "CAR",
    title: "Hyundai Creta Platinum 2022",
    shortDescription: "SUV mais vendido do Brasil.",
    description: "Completo, revisado, garantia estendida opcional.",
    model: "Creta",
    version: "Platinum",
    yearManufacture: 2022,
    yearModel: 2022,
    mileage: 42000,
    fuelType: "FLEX",
    transmission: "AUTOMATIC",
    color: "Branco",
    doors: 4,
    priceCash: 128900,
    images: [{ url: "/mock/vehicles/creta-1.jpg", isCover: true, sortOrder: 0 }],
    features: ["Bluelink", "Teto solar", "Couro"],
  },
];

async function main() {
  const existingSettings = await prisma.siteSettings.findFirst();
  if (!existingSettings) {
    await prisma.siteSettings.create({
      data: {
        siteName: "Auto Dealer Demo",
        defaultWhatsappNumber: "5545999999999",
        defaultEmail: "contato@autodealerdemo.com",
        phoneNumber: "(45) 99999-9999",
        city: "Foz do Iguaçu",
        state: "PR",
        heroTitle: "Seu próximo veículo começa aqui",
        heroSubtitle: "Estoque selecionado, atendimento rápido e proposta sem complicação.",
      },
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

  for (const v of VEHICLE_SEEDS) {
    const brand = await prisma.brand.findUnique({ where: { slug: v.brandSlug } });
    if (!brand) continue;
    const existing = await prisma.vehicle.findUnique({ where: { slug: v.slug } });
    if (existing) continue;

    const { images, features, brandSlug: _b, ...vehicleData } = v;
    await prisma.vehicle.create({
      data: {
        ...vehicleData,
        brandId: brand.id,
        publishedAt: new Date(),
        images: {
          create: images.map((img) => ({
            url: img.url,
            isCover: img.isCover,
            sortOrder: img.sortOrder,
          })),
        },
        features: {
          create: features.map((label, i) => ({
            label,
            category: "OTHER" as const,
            sortOrder: i,
          })),
        },
      },
    });
  }

  const pages = [
    {
      slug: "quem-somos",
      title: "Quem Somos",
      excerpt: "Nossa história e valores.",
      body: "Somos uma revenda focada em atendimento rápido, transparência e veículos selecionados. Trabalhamos com seminovos revisados e documentação em dia.",
    },
    {
      slug: "politica-de-privacidade",
      title: "Política de Privacidade",
      excerpt: "Como tratamos seus dados.",
      body: "Coletamos apenas os dados necessários para atendimento e propostas. Não vendemos seus dados a terceiros. Você pode solicitar exclusão a qualquer momento.",
    },
    {
      slug: "termos-de-uso",
      title: "Termos de Uso",
      excerpt: "Condições de uso do site.",
      body: "O uso deste site implica aceitação destes termos. As informações dos veículos são meramente ilustrativas; confirme disponibilidade e condições na loja.",
    },
    {
      slug: "nosso-estoque",
      title: "Nosso estoque",
      excerpt: "Como funciona nossa curadoria.",
      body: "Todos os veículos passam por inspeção básica. Oferecemos opções de financiamento parceiras e avaliação do seu usado na troca.",
    },
    {
      slug: "trabalhe-conosco",
      title: "Trabalhe conosco",
      excerpt: "Envie seu currículo.",
      body: "Estamos sempre em busca de talentos. Envie seu currículo para rh@autodealerdemo.com com o assunto VAGAS.",
    },
  ];
  for (const p of pages) {
    await prisma.page.upsert({
      where: { slug: p.slug },
      create: { ...p, status: "PUBLISHED" },
      update: { body: p.body, title: p.title, excerpt: p.excerpt },
    });
  }

  const posts = [
    {
      slug: "como-escolher-seu-proximo-seminovo",
      title: "Como escolher seu próximo seminovo",
      excerpt: "Pontos práticos para avaliar um seminovo.",
      body: "Verifique histórico, laudo cautelar, estado dos pneus e revisões. Um test drive é essencial.",
    },
    {
      slug: "financiar-veiculo-sem-entrada",
      title: "Financiar veículo: é possível sem entrada?",
      excerpt: "Entenda as opções do mercado.",
      body: "Algumas instituições permitem financiamento com entrada zero, mas as parcelas tendem a ser maiores. Compare CET e prazo total.",
    },
    {
      slug: "vantagens-do-seminovo",
      title: "Vantagens de comprar um seminovo",
      excerpt: "Menos depreciação e mais equipamentos.",
      body: "O seminovo oferece melhor custo-benefício que o zero km na maioria dos casos, com desvalorização já absorvida pelo primeiro dono.",
    },
    {
      slug: "revisao-pre-compra",
      title: "Checklist antes de fechar negócio",
      excerpt: "O que conferir no dia da compra.",
      body: "Documentação, multas, gravames, chave reserva e manual do proprietário devem estar em ordem.",
    },
    {
      slug: "documentacao-para-comprar-carro",
      title: "Documentação para comprar carro usado",
      excerpt: "Lista do que você vai precisar.",
      body: "RG, CPF, comprovante de residência e comprovação de renda são os básicos para financiamento.",
    },
    {
      slug: "tendencias-mercado-automoveis-2025",
      title: "Tendências do mercado automotivo",
      excerpt: "Híbridos e elétricos em alta.",
      body: "O mercado brasileiro segue aquecido para SUVs e veículos híbridos. Seminovos premium também têm boa liquidez.",
    },
  ];
  for (const post of posts) {
    await prisma.blogPost.upsert({
      where: { slug: post.slug },
      create: { ...post, status: "PUBLISHED", publishedAt: new Date() },
      update: { body: post.body, title: post.title, excerpt: post.excerpt },
    });
  }

  const adminEmail = "admin@autodealerdemo.com";
  const existingAdmin = await prisma.user.findUnique({ where: { email: adminEmail } });
  if (!existingAdmin) {
    const passwordHash = await hashPassword("ChangeMe123!");
    await prisma.user.create({
      data: {
        name: "Admin Demo",
        email: adminEmail,
        passwordHash,
        role: "SUPER_ADMIN",
        isActive: true,
      },
    });
  }

  console.log("Seed completed.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
