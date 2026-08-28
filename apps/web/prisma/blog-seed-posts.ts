/** Canonical blog posts for local and production seeds. Covers stay on-site. */

export type SeedBlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  body: string;
  metaTitle: string;
  metaDescription: string;
  coverImageUrl: string | null;
};

export const SEED_BLOG_POSTS: SeedBlogPost[] = [
  {
    slug: "como-escolher-seu-proximo-seminovo",
    title: "Como escolher um seminovo em Cascavel",
    excerpt: "O que conferir antes de fechar a compra de um usado na região Oeste do Paraná.",
    body: `Comprar um seminovo em Cascavel começa pela conferência do veículo, não pela pressa do anúncio.

Peça o histórico de manutenção, confira documentação, gravames e faça um test drive em percursos que você realmente usa — cidade, BR-277 e trechos urbanos.

Na FácilCar, o estoque publicado no site é o estoque real da loja. Se o modelo não estiver listado, falamos isso com transparência e, quando fizer sentido, mostramos alternativas próximas em preço e categoria.

Agende uma visita na R. Ipanema, 1206 — Periolo, Cascavel/PR, ou fale pelo WhatsApp para alinhar o que você procura.`,
    metaTitle: "Como escolher um seminovo em Cascavel | FácilCar",
    metaDescription:
      "Checklist prático para comprar seminovo em Cascavel/PR: documentação, test drive e estoque real da FácilCar Multimarcas.",
    coverImageUrl: null,
  },
  {
    slug: "financiar-veiculo-sem-entrada",
    title: "Financiamento de seminovos: o que esperar",
    excerpt: "A FácilCar prepara a pré-ficha. A análise e as condições finais são da financeira.",
    body: `Financiar um seminovo é um caminho comum, mas as condições dependem da análise de crédito e das regras da financeira — não de uma simulação automática no site.

Financiamento sem entrada pode ser possível, sujeito à análise de crédito e às condições da instituição. Não prometemos aprovação, taxa, parcela ou percentual financiado.

O que a FácilCar faz: organiza seus dados, esclarece o interesse no veículo e encaminha a pré-ficha para o time comercial seguir com as financeiras parceiras.

Se você já tem um modelo em mente, traga documentos que já tiver. Não é necessário repetir CPF, data de nascimento ou renda quando esses dados já foram extraídos com segurança.`,
    metaTitle: "Financiamento de seminovos em Cascavel | FácilCar",
    metaDescription:
      "Entenda como funciona a pré-ficha de financiamento na FácilCar Multimarcas em Cascavel/PR, sem promessa de aprovação.",
    coverImageUrl: null,
  },
  {
    slug: "vantagens-do-seminovo",
    title: "Por que considerar um seminovo",
    excerpt: "Depreciação já absorvida, mais equipamento pelo mesmo investimento e estoque curado.",
    body: `O seminovo costuma entregar melhor custo-benefício que o zero quilômetro: parte da depreciação já ocorreu e o veículo pode ter mais itens de série pelo mesmo orçamento.

Isso não substitui a inspeção. Confira pneus, freios, alinhamento e o estado geral da lataria. Um laudo cautelar ajuda quando houver dúvida.

Na FácilCar o estoque é curado — publicamos apenas veículos que passaram pela conferência da loja. Disponibilidade, km, cor e preço vêm do anúncio publicado, nunca de estimativa.`,
    metaTitle: "Vantagens de comprar um seminovo | FácilCar Cascavel",
    metaDescription:
      "Por que um seminovo pode render mais equipamento pelo mesmo investimento, com conferência na FácilCar em Cascavel/PR.",
    coverImageUrl: null,
  },
  {
    slug: "revisao-pre-compra",
    title: "Checklist antes de fechar negócio",
    excerpt: "Documentação, restrições, chave reserva e o que perguntar na visita.",
    body: `Antes de assinar, confira:

- CRLV e dados do proprietário
- restrições, gravames e eventuais débitos
- chave reserva e manual
- quilometragem compatível com o estado do veículo
- itens anunciados versus o que está no carro

Leve alguém de confiança para o test drive. Se o veículo estiver no estoque da FácilCar, a ficha do site é a referência — se algo divergir, pedimos confirmação em vez de resolver em silêncio.`,
    metaTitle: "Checklist para comprar carro usado em Cascavel | FácilCar",
    metaDescription:
      "O que conferir na visita: documentos, gravames, chaves e ficha do anúncio na FácilCar Multimarcas.",
    coverImageUrl: null,
  },
  {
    slug: "documentacao-para-comprar-carro",
    title: "Documentos para comprar um carro usado",
    excerpt: "O básico para compra à vista ou para iniciar uma pré-ficha de financiamento.",
    body: `Para compra à vista, o essencial costuma ser documento de identidade, CPF e comprovante de residência, além da documentação do veículo.

Para financiamento, a financeira pode pedir comprovação de renda e outros dados. Recusar um documento sensível não precisa encerrar um atendimento comercialmente acionável — o time avalia o que ainda dá para avançar.

Já enviou CNH ou comprovante pelo WhatsApp? Não pedimos de novo o que já extraímos com confiança suficiente. Conflitos críticos entre o texto e o documento pedem confirmação, não um “acerto” silencioso.`,
    metaTitle: "Documentos para comprar carro usado | FácilCar Cascavel",
    metaDescription:
      "Quais documentos costumam ser pedidos na compra de seminovo ou na pré-ficha de financiamento na FácilCar.",
    coverImageUrl: null,
  },
  {
    slug: "vender-ou-consignar-carro-em-cascavel",
    title: "Vender ou consignar seu carro em Cascavel",
    excerpt: "Compra direta pela loja ou consignação, com avaliação sem compromisso.",
    body: `Se você quer trocar ou apenas vender, a FácilCar avalia o usado com transparência.

Na consignação, o veículo permanece anunciado com acompanhamento da loja. Na compra direta, alinhamos uma proposta com base no estado e no mercado local.

Envie fotos nítidas (frente, traseira, laterais e interior) e os dados principais do carro. Não pedimos e-mail no formulário público — o atendimento segue pelo WhatsApp.

Visite a loja no Periolo ou chame no WhatsApp para agendar a avaliação.`,
    metaTitle: "Vender ou consignar carro em Cascavel | FácilCar",
    metaDescription:
      "Avaliação para venda ou consignação de usados na FácilCar Multimarcas, Cascavel/PR, sem compromisso.",
    coverImageUrl: null,
  },
];
