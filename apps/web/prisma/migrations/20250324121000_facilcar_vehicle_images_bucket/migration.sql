INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
  'vehicle-images',
  'vehicle-images',
  true,
  52428800,
  ARRAY['image/jpeg', 'image/png', 'image/webp', 'image/gif']::text[]
)
ON CONFLICT (id) DO UPDATE SET
  public = EXCLUDED.public,
  file_size_limit = EXCLUDED.file_size_limit,
  allowed_mime_types = EXCLUDED.allowed_mime_types;

DROP POLICY IF EXISTS "facilcar_vehicle_images_public_read" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_public_read"
ON storage.objects FOR SELECT
TO public
USING (bucket_id = 'vehicle-images');

DROP POLICY IF EXISTS "facilcar_vehicle_images_authenticated_insert" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_authenticated_insert"
ON storage.objects FOR INSERT
TO authenticated
WITH CHECK (bucket_id = 'vehicle-images');

DROP POLICY IF EXISTS "facilcar_vehicle_images_authenticated_update" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_authenticated_update"
ON storage.objects FOR UPDATE
TO authenticated
USING (bucket_id = 'vehicle-images')
WITH CHECK (bucket_id = 'vehicle-images');

DROP POLICY IF EXISTS "facilcar_vehicle_images_authenticated_delete" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_authenticated_delete"
ON storage.objects FOR DELETE
TO authenticated
USING (bucket_id = 'vehicle-images');
