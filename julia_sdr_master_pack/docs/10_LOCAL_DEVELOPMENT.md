# 10 — Local Development

## Colima
```bash
colima start --cpu 4 --memory 8 --vm-type=vz --vz-rosetta
```

## Supabase local
Usar Supabase CLI e `supabase start --exclude ...` conforme versão instalada para subir apenas recursos necessários e economizar RAM.

## Evolution
Container local obrigatório para smoke tests. Número reservado: `5545988432998`.

## OpenAI
API externa permitida. Secrets em `.env.local`, nunca commitados.

## Serviços locais sugeridos
- sdr-api;
- sdr-worker;
- redis;
- supabase local;
- evolution;
- app web apenas quando necessário.

## Perfis
Separar `core`, `integration` e `full` para não subir observabilidade pesada por padrão.

## Seeds
Catálogo público e dados sintéticos podem ser usados. Nunca copiar dados pessoais/documentos reais de produção.
