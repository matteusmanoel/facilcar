-- Additive: sell-form photos and consignment vs direct-purchase intent.

ALTER TABLE "facilcar"."SellRequest" ADD COLUMN "saleMode" TEXT;
ALTER TABLE "facilcar"."SellRequest" ADD COLUMN "photoUrls" TEXT[] DEFAULT ARRAY[]::TEXT[] NOT NULL;
