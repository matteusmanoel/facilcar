# Fase 12 — matriz de cobertura

Os 17 cenários comerciais permanecem em `tests/golden/scenarios/`.
Os contratos 18–31 são comprovados pelos goldens das Fases 9–11 já existentes.
Nenhum arquivo extra foi criado só para chegar a 31.

| Contrato | O que comprova | Golden |
| --- | --- | --- |
| 01 | compra à vista | `compra_avista` |
| 02 | compra financiada com entrada | `compra_financiada_com_entrada` |
| 03 | compra financiada sem entrada | `compra_financiada_sem_entrada` |
| 04 | troca quitada | `troca_quitada` |
| 05 | troca financiada | `troca_financiada` |
| 06 | troca com débitos | `troca_com_debitos` |
| 07 | venda direta | `venda_direta` |
| 08 | consignação | `consignacao` |
| 09 | refinanciamento | `refinanciamento` |
| 10 | civic vendido + foto | `civic_vendido_foto` |
| 11 | gol não encontrado | `gol_nao_encontrado` |
| 12 | fox + peugeot troca | `fox_peugeot_troca` |
| 13 | pedido de vendedor | `pedido_de_vendedor` + `p9_11_vendedor_durante_documentos` |
| 14 | agendamento semana | `agendamento_semana` |
| 15 | agendamento sábado | `agendamento_sabado` |
| 16 | fox texto+imagem+financiamento burst | `whatsapp_fox_image_financing_burst_visit` |
| 17 | reply Strada 2018 + financiamento | `whatsapp_strada_quoted_primary_financing_visit` |
| 18 | financiamento só com CNH | `p9_07_somente_cnh` |
| 19 | documentos adiados sem callback | `p9_09_documentos_indisponiveis` |
| 20 | callback explícito para documentos | `g1_documents_tomorrow_14h` |
| 21 | pacote documental completo | `p9_10_todos_documentos` |
| 22 | visita durante coleta documental | `p9_12_visita_durante_documentos` |
| 23 | pedido de vendedor durante documentos | `p9_11_vendedor_durante_documentos` |
| 24 | decisão com cônjuge + follow-up | `g2_spouse_without_time` |
| 25 | silêncio depois da parcela | `p9_06_parcela_informada` + `g9_dormant_after_followup` |
| 26 | follow-up cancelado por resposta | `g3_reply_before_due` |
| 27 | follow-up cancelado por humano | `g4_human_assume` |
| 28 | nova informação depois do handoff | `g1_document_after_handoff` + `g10_post_handoff_before_human` |
| 29 | opt-out com tarefa pendente | `g5_opt_out` |
| 30 | veículo vendido antes do follow-up | `g8_vehicle_sold` |
| 31 | assume/resume só para futuros inbounds | `p10_02_assume_resume` |

Gate de alto risco (3 repetições, LLM real, depois do freeze):

1. HR1 fox burst
2. HR2 Strada quoted
3. HR3 CNH parcial
4. HR4 documentos + callback
5. HR5 cônjuge
6. HR6 pergunta sem informação segura
7. HR7 pós-handoff
8. HR8 cancelamento por humano
9. HR9 opt-out
10. HR10 veículo vendido antes do follow-up
