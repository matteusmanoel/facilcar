-- Colunas presentes em schema.prisma mas ausentes da migration inicial (drift).
-- Sem isso, Prisma P2022 em lead.findMany() e queries relacionadas na Vercel.
-- IF NOT EXISTS: tolera bancos onde alguém já tenha aplicado db push parcial.

ALTER TABLE "facilcar"."Lead" ADD COLUMN IF NOT EXISTS "internalNote" TEXT;

ALTER TABLE "facilcar"."FinancingRequest" ADD COLUMN IF NOT EXISTS "cpf" TEXT;
ALTER TABLE "facilcar"."FinancingRequest" ADD COLUMN IF NOT EXISTS "birthDate" TIMESTAMP(3);
ALTER TABLE "facilcar"."FinancingRequest" ADD COLUMN IF NOT EXISTS "vehicleYear" INTEGER;
ALTER TABLE "facilcar"."FinancingRequest" ADD COLUMN IF NOT EXISTS "vehicleModel" TEXT;
