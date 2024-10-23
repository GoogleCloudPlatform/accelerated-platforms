insert into flipkart_multi
select
uniq_id,
(ARRAY(select json_array_elements_text(mme->'multimodal_embeds'))::REAL[])::vector as mme,
(ARRAY(select json_array_elements_text(mme->'image_embeds'))::REAL[])::vector as image_embed,
(ARRAY(select json_array_elements_text(mme->'text_embeds'))::REAL[])::vector as desc_embed
from (select uniq_id, google_ml.multimodal_embedding('multimodal-blip2', product_name, image_uri) as mme from flipkart
where image_uri like 'gs://%') t1;
