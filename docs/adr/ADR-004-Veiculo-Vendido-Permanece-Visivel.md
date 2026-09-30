# ADR-004: Veículo vendido permanece visível

**Status**: Accepted
**Date**: 2026-09-29

## Context

O estoque público só oferecia veículo publicado. Marcar um veículo como vendido tirava o anúncio do ar. A loja quer o carimbo “VENDIDO” como prova social, sem que esse anúncio continue sendo oferta de compra.

## Decision

Vendido sai do estoque disponível e continua no anúncio público, com o carimbo. Aparece na listagem depois dos disponíveis. Não entra em busca, filtro de compra, destaque da home nem nas ofertas da Júlia. A ficha antiga continua acessível.

A ficha ainda captura. O pedido é um interesse em similar: uma pessoa procura no estoque disponível algo próximo em tipo e faixa de preço. Não promete a mesma marca, o mesmo modelo, o mesmo ano, o mesmo preço nem o financiamento daquela unidade. O aviso é evidente na ficha, no formulário e no WhatsApp. O lead fica ligado ao anúncio de origem.

Preço, parcela estimada e título de simulação permanecem como dado ilustrativo. Não são cotação nem oferta da unidade vendida.

## Consequences

- Estoque disponível e anúncio visível deixam de ser a mesma coisa.
- A Júlia não oferece vendido como opção de compra.
- A captura não é bloqueada na ficha vendida.
- Arquivar continua sendo outra ação: o veículo some do site e o registro fica recuperável.

## Alternatives Considered

- **Tirar o anúncio do ar ao vender.** Rejeitado. Perde a prova social.
- **Manter o status de publicado e só sobrepor o carimbo.** Rejeitado. Publicado seguiria significando estoque disponível para o site e para a Júlia.
- **Fechar o formulário na ficha vendida.** Rejeitado. A loja não restringe o envio de dados.
