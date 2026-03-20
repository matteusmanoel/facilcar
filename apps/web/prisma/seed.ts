import { PrismaClient } from "@prisma/client";
import { PrismaPg } from "@prisma/adapter-pg";
import { Pool } from "pg";
import { hashPassword } from "../features/auth/server/passwords";

const connectionString =
  process.env.DATABASE_URL ??
  "postgresql://postgres:postgres@localhost:5432/facilcar?schema=public";
const pool = new Pool({ connectionString });
const adapter = new PrismaPg(pool);
const prisma = new PrismaClient({ adapter });

/** Arquivo em `public/cars/` → URL pública `/cars/...`. */
function carAsset(file: string) {
  return `/cars/${file}`;
}

/**
 * Fotos reais em `apps/web/public/cars/` (servidas como `/cars/...`).
 * Reutilização por categoria quando não há foto específica do modelo.
 */
const SEED_CAR_IMAGES: Record<string, string[]> = {
  "toyota-corolla-xei-2022": ["versa.png", "tracker.png"],
  "honda-civic-ex-2021": ["versa.png", "hrv.png"],
  "fiat-strada-freedom-2023": ["ranger.jpg"],
  "chevrolet-onix-lt-2023": ["hb20s.webp"],
  "volkswagen-polo-highline-2022": ["hb20s.webp"],
  "jeep-renegade-longitude-2021": ["jeep-compass.jpg"],
  "nissan-kicks-advance-2022": ["creta.jpg"],
  "hyundai-hb20-platinum-2023": ["hb20s.webp"],
  "renault-duster-intense-2020": ["duster.jpg"],
  "ford-ranger-xls-2022": ["ranger.jpg"],
  "toyota-hilux-srx-2021": ["hilux-srv.png"],
  "honda-hr-v-exl-2023": ["hrv.png"],
  "fiat-toro-volcano-2022": ["toro.png"],
  "chevrolet-tracker-premier-2022": ["tracker.png"],
  "volkswagen-t-cross-comfortline-2023": ["t-cross.png"],
  "jeep-compass-longitude-2020": ["jeep-compass.jpg"],
  "nissan-versa-advance-2023": ["versa.png"],
  "hyundai-creta-platinum-2022": ["creta.jpg"],
};

function seedVehicleImages(slug: string): { url: string; isCover: boolean; sortOrder: number }[] {
  const files = SEED_CAR_IMAGES[slug];
  if (!files?.length) {
    const text = encodeURIComponent(slug.replace(/-/g, " ").slice(0, 24));
    return [
      {
        url: `https://placehold.co/1200x800/e2e8f0/64748b?text=${text}`,
        isCover: true,
        sortOrder: 0,
      },
    ];
  }
  return files.map((file, i) => ({
    url: carAsset(file),
    isCover: i === 0,
    sortOrder: i,
  }));
}

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
    images: seedVehicleImages("toyota-corolla-xei-2022"),
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
    images: seedVehicleImages("honda-civic-ex-2021"),
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
    images: seedVehicleImages("fiat-strada-freedom-2023"),
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
    images: seedVehicleImages("chevrolet-onix-lt-2023"),
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
    images: seedVehicleImages("volkswagen-polo-highline-2022"),
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
    images: seedVehicleImages("jeep-renegade-longitude-2021"),
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
    images: seedVehicleImages("nissan-kicks-advance-2022"),
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
    images: seedVehicleImages("hyundai-hb20-platinum-2023"),
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
    images: seedVehicleImages("renault-duster-intense-2020"),
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
    images: seedVehicleImages("ford-ranger-xls-2022"),
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
    images: seedVehicleImages("toyota-hilux-srx-2021"),
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
    images: seedVehicleImages("honda-hr-v-exl-2023"),
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
    images: seedVehicleImages("fiat-toro-volcano-2022"),
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
    images: seedVehicleImages("chevrolet-tracker-premier-2022"),
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
    images: seedVehicleImages("volkswagen-t-cross-comfortline-2023"),
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
    images: seedVehicleImages("jeep-compass-longitude-2020"),
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
    images: seedVehicleImages("nissan-versa-advance-2023"),
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
    images: seedVehicleImages("hyundai-creta-platinum-2022"),
    features: ["Bluelink", "Teto solar", "Couro"],
  },
];

async function main() {
  const settingsData = {
    siteName: "FácilCar Multimarcas",
    defaultWhatsappNumber: "5545999123456",
    defaultEmail: "contato@facilcarmultimarcas.com.br",
    phoneNumber: "(45) 3300-0000",
    addressLine: "Av. Exemplo, 1000 — Showroom",
    city: "Sua Cidade",
    state: "PR",
    zipCode: "85800-000",
    instagramUrl: "https://www.instagram.com/facilcarmultimarcas/",
    facebookUrl: null as string | null,
    youtubeUrl: null as string | null,
    seoDefaultTitle: "FácilCar Multimarcas | Seminovos e financiamento",
    seoDefaultDescription:
      "Seminovos selecionados, financiamento facilitado e venda/consignação com segurança. FácilCar Multimarcas.",
    footerText:
      "Há anos conectando pessoas ao carro certo. Transparência, agilidade e atendimento que faz a diferença.",
    heroTitle: "Seu próximo carro, do jeito mais fácil.",
    heroSubtitle:
      "Estoque curado, financiamento com especialistas e avaliação justa do seu usado — tudo em um só lugar.",
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

  for (const v of VEHICLE_SEEDS) {
    const brand = await prisma.brand.findUnique({ where: { slug: v.brandSlug } });
    if (!brand) continue;
    const existing = await prisma.vehicle.findUnique({ where: { slug: v.slug } });
    if (existing) continue;

    const { images, features, brandSlug, ...vehicleData } = v;
    void brandSlug;
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

  // Atualiza fotos dos veículos já existentes (re-seed com novos assets em /public/cars).
  for (const v of VEHICLE_SEEDS) {
    const existing = await prisma.vehicle.findUnique({ where: { slug: v.slug } });
    if (!existing) continue;
    await prisma.vehicleImage.deleteMany({ where: { vehicleId: existing.id } });
    await prisma.vehicleImage.createMany({
      data: v.images.map((img) => ({
        vehicleId: existing.id,
        url: img.url,
        isCover: img.isCover,
        sortOrder: img.sortOrder,
      })),
    });
  }

  const pages = [
    {
      slug: "quem-somos",
      title: "Quem somos",
      excerpt: "A FácilCar nasceu para simplificar comprar e vender carro.",
      body: `A FácilCar Multimarcas é uma revenda focada em seminovos com curadoria real: cada veículo passa por conferência antes de ir para o site.

Nossa missão é oferecer transparência, agilidade e um atendimento humano — do primeiro WhatsApp até a assinatura do contrato. Trabalhamos com financiamento junto às principais financeiras e com consignação para quem quer vender com segurança, sem expor dados pessoais em anúncios soltos na internet.

Valores: honestidade nas condições, respeito ao tempo do cliente e compromisso com pós-venda claro.

Venha nos visitar ou fale pelo site. Estamos prontos para o seu próximo carro.`,
      metaTitle: "Quem somos | FácilCar Multimarcas",
      metaDescription: "Conheça a FácilCar: seminovos, financiamento e consignação com transparência.",
    },
    {
      slug: "politica-de-privacidade",
      title: "Política de privacidade",
      excerpt: "Como tratamos seus dados.",
      body: `Coletamos nome, telefone, e-mail e dados informados em formulários apenas para contato comercial, análise de financiamento ou avaliação de veículo.

Não vendemos seus dados. Podemos usar prestadores de serviço (ex.: hospedagem, e-mail transacional) sob confidencialidade.

Você pode solicitar acesso, correção ou exclusão dos dados pelo e-mail de contato da loja.

Cookies: utilizamos cookies essenciais e, se configurado, de analytics para melhorar o site.`,
      metaTitle: "Política de privacidade | FácilCar",
      metaDescription: "Política de privacidade e tratamento de dados — FácilCar Multimarcas.",
    },
    {
      slug: "termos-de-uso",
      title: "Termos de uso",
      excerpt: "Condições de uso deste site.",
      body: `Ao usar este site você concorda com estes termos. As fotos, preços e descrições dos veículos têm caráter informativo; disponibilidade e condições finais devem ser confirmadas na loja.

A FácilCar não se responsabiliza por indisponibilidade temporária do site ou por conteúdo de sites externos linkados.

Para dúvidas, utilize os canais oficiais de contato.`,
      metaTitle: "Termos de uso | FácilCar",
      metaDescription: "Termos de uso do site FácilCar Multimarcas.",
    },
    {
      slug: "nosso-estoque",
      title: "Nosso estoque",
      excerpt: "Como selecionamos os carros que você vê aqui.",
      body: `Priorizamos veículos com histórico conferível, documentação regular e estado alinhado ao anúncio.

Antes de publicar, fazemos checagens básicas. Na loja você pode inspecionar o carro, fazer test drive quando disponível e tirar todas as dúvidas com nossa equipe.

Financiamento e troca podem ser combinados na mesma visita — agilizando sua decisão.`,
      metaTitle: "Nosso estoque | FácilCar",
      metaDescription: "Curadoria e critérios do estoque FácilCar Multimarcas.",
    },
    {
      slug: "trabalhe-conosco",
      title: "Trabalhe conosco",
      excerpt: "Faça parte do time FácilCar.",
      body: `Buscamos pessoas alinhadas com atendimento ao cliente e integridade comercial.

Envie seu currículo para o e-mail contato@facilcarmultimarcas.com.br com o assunto VAGAS — informe a área de interesse (vendas, administrativo, pós-venda).`,
      metaTitle: "Trabalhe conosco | FácilCar",
      metaDescription: "Oportunidades de carreira na FácilCar Multimarcas.",
    },
  ];
  for (const p of pages) {
    const { metaTitle, metaDescription, ...rest } = p as typeof p & {
      metaTitle?: string;
      metaDescription?: string;
    };
    await prisma.page.upsert({
      where: { slug: p.slug },
      create: { ...rest, status: "PUBLISHED", metaTitle: metaTitle ?? null, metaDescription: metaDescription ?? null },
      update: {
        body: p.body,
        title: p.title,
        excerpt: p.excerpt,
        metaTitle: metaTitle ?? null,
        metaDescription: metaDescription ?? null,
      },
    });
  }

  const posts = [
    {
      slug: "como-escolher-seu-proximo-seminovo",
      title: "Como escolher seu próximo seminovo",
      excerpt: "Pontos práticos para avaliar um seminovo.",
      body: "Verifique histórico, laudo cautelar, estado dos pneus e revisões. Um test drive é essencial.\n\nNa FácilCar você pode agendar visita e tirar dúvidas com a equipe antes de decidir.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog1/800/450",
    },
    {
      slug: "financiar-veiculo-sem-entrada",
      title: "Financiar veículo: é possível sem entrada?",
      excerpt: "Entenda as opções do mercado.",
      body: "Algumas instituições permitem financiamento com entrada zero, mas as parcelas tendem a ser maiores. Compare CET e prazo total.\n\nNossa equipe simula em várias financeiras para achar o cenário que melhor encaixa no seu orçamento.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog2/800/450",
    },
    {
      slug: "vantagens-do-seminovo",
      title: "Vantagens de comprar um seminovo",
      excerpt: "Menos depreciação e mais equipamentos.",
      body: "O seminovo oferece melhor custo-benefício que o zero km na maioria dos casos, com desvalorização já absorvida pelo primeiro dono.\n\nVocê leva mais opcionais pelo mesmo investimento.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog3/800/450",
    },
    {
      slug: "revisao-pre-compra",
      title: "Checklist antes de fechar negócio",
      excerpt: "O que conferir no dia da compra.",
      body: "Documentação, multas, gravames, chave reserva e manual do proprietário devem estar em ordem.\n\nSe tiver dúvida, peça apoio profissional ou laudo cautelar.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog4/800/450",
    },
    {
      slug: "documentacao-para-comprar-carro",
      title: "Documentação para comprar carro usado",
      excerpt: "Lista do que você vai precisar.",
      body: "RG, CPF, comprovante de residência e comprovação de renda são os básicos para financiamento.\n\nComprador PJ ou estrangeiro pode ter requisitos extras — consulte sempre a financeira.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog5/800/450",
    },
    {
      slug: "tendencias-mercado-automoveis-2025",
      title: "Tendências do mercado automotivo",
      excerpt: "SUVs, híbridos e seminovos premium.",
      body: "O mercado brasileiro segue aquecido para SUVs e veículos híbridos. Seminovos premium também têm boa liquidez.\n\nAcompanhe nosso estoque — sempre atualizado com o que há de melhor na região.",
      coverImageUrl: "https://picsum.photos/seed/facilcar-blog6/800/450",
    },
  ];
  for (const post of posts) {
    await prisma.blogPost.upsert({
      where: { slug: post.slug },
      create: {
        slug: post.slug,
        title: post.title,
        excerpt: post.excerpt,
        body: post.body,
        coverImageUrl: post.coverImageUrl,
        status: "PUBLISHED",
        publishedAt: new Date(),
      },
      update: {
        body: post.body,
        title: post.title,
        excerpt: post.excerpt,
        coverImageUrl: post.coverImageUrl,
      },
    });
  }

  const adminEmail = "admin@facilcar.demo";
  const passwordHash = await hashPassword("ChangeMe123!");
  await prisma.user.upsert({
    where: { email: adminEmail },
    create: {
      name: "Admin FácilCar",
      email: adminEmail,
      passwordHash,
      role: "SUPER_ADMIN",
      isActive: true,
    },
    update: { passwordHash, name: "Admin FácilCar" },
  });

  console.log("Seed completed.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => prisma.$disconnect());
