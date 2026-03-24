DROP POLICY IF EXISTS "facilcar_vehicle_images_anon_insert" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_anon_insert"
ON storage.objects FOR INSERT
TO anon
WITH CHECK (bucket_id = 'vehicle-images');

DROP POLICY IF EXISTS "facilcar_vehicle_images_anon_update" ON storage.objects;
CREATE POLICY "facilcar_vehicle_images_anon_update"
ON storage.objects FOR UPDATE
TO anon
USING (bucket_id = 'vehicle-images')
WITH CHECK (bucket_id = 'vehicle-images');
