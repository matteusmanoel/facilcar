# FácilCar

Glossário do domínio da FácilCar: seminovos, estoque e jornada comercial.

## Language

**Tipo de veículo**:
Natureza do veículo no estoque: carro, moto, utilitário ou outro.
_Avoid_: recorte de carroceria, sedan, hatch, SUV neste conceito

**Recorte de carroceria**:
Silhueta de um carro: sedan, hatch ou SUV. Só existe quando o tipo de veículo é carro. É opcional. Aparece no cadastro, como chip no card se preenchido, e como filtro do estoque público.
_Avoid_: tipo de veículo, categoria (no sentido de carro vs moto), utilitário neste conceito

**Arquivar (veículo)**:
Tira o veículo do estoque público sem apagar o registro. Permanece recuperável. Na listagem admin, esta é a ação pedida como “Excluir”.
_Avoid_: exclusão permanente, apagar do banco, remover histórico de leads e fotos

**Resultado da perícia**:
Estado da perícia do veículo: não informado, aprovado ou reprovado. Independente do histórico comercial. Ausência de dado não é reprovação.
_Avoid_: histórico comercial, checkbox único, tratado como verdadeiro ou falso sem estado vazio

**Selo de perícia**:
Marca visual pública de que o veículo foi aprovado na perícia. Aparece só quando o resultado é aprovado, no canto superior direito da foto: cards da listagem, destaques e página do veículo. Não informado e reprovado não exibem selo nem o texto “reprovado” no anúncio.
_Avoid_: selo em veículo sem aprovação, selo para reprovado, ocultar veículo reprovado do estoque só por causa da perícia

**Cookie essencial**:
Cookie necessário para o site funcionar, como a sessão de login do admin. Não depende de consentimento de marketing.
_Avoid_: cookie de analytics tratado como essencial

**Consentimento de cookies**:
Escolha salva no navegador: aceitar analytics ou permanecer só com cookies essenciais. Sem aceite, o PostHog não inicia. O aviso não bloqueia a navegação.
_Avoid_: banner que trava o site, analytics ligado sem permissão

**Foto do anúncio**:
Foto publicada do veículo no card e na ficha. Sem foto, o anúncio usa o placeholder padrão. Falta de foto não é um status do veículo.
_Avoid_: em preparação, em breve, status de ciclo de vida por ausência de imagem
