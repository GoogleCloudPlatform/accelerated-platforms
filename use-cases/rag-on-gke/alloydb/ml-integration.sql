-- set google_ml_integration.enable_model_support = 'on';
call google_ml.drop_model('gke-vllm-finetuned');
CALL
    google_ml.create_model(
      model_id => 'gke-vllm-finetuned',
      model_request_url => 'http://10.150.0.32:8000/v1/completions',
      model_provider => 'custom',
      model_type => 'generic',
      model_qualified_name => '/data/models/model-gemma2-a100/experiment-a2aa2c3it1',
      model_auth_type => null,
      model_auth_id => null,
      generate_headers_fn => null,
      model_in_transform_fn => null,
      model_out_transform_fn => null);

create or replace function vllm_completion(input_text text)
returns TEXT AS $$
SELECT json_extract_path_text(google_ml.predict_row('gke-vllm-finetuned',
   json_build_object('prompt', input_text,
   'model', '/data/models/model-gemma2-a100/experiment-a2aa2c3it1',
   'max_tokens', 1024))::json, 'choices','0','text');
$$ LANGUAGE sql IMMUTABLE;


-- 10.150.15.227
call google_ml.drop_model('multimodal-blip2');
CALL
    google_ml.create_model(
      model_id => 'multimodal-blip2',
      model_request_url => 'http://10.150.15.227/embeddings',
      model_provider => 'custom',
      model_type => 'generic',
      model_auth_type => null,
      model_auth_id => null,
      generate_headers_fn => null,
      model_in_transform_fn => null,
      model_out_transform_fn => null);

create or replace function google_ml.multimodal_embedding(model_id varchar, input_text text, image_uri text)
returns JSON AS $$
SELECT google_ml.predict_row('multimodal-blip2', json_build_object('caption', input_text, 'image_uri', image_uri));
$$ LANGUAGE sql IMMUTABLE;



create or replace function google_ml.blip2_embedding_text_input(model_id varchar, input_text text)
returns json as $$
DECLARE
  transformed_input JSON;
BEGIN
  SELECT json_build_object('caption', input_text)::JSON INTO transformed_input;
  RETURN transformed_input;
END;
$$
LANGUAGE plpgsql IMMUTABLE;


create or replace function google_ml.blip2_embedding_text_output(model_id varchar, response_json json)
returns REAL[] as $$
DECLARE
  transformed_output REAL[];
BEGIN
  SELECT ARRAY(SELECT json_array_elements_text(response_json->'text_embeds'))::REAL[]
  INTO transformed_output;
  RETURN transformed_output;
END;

$$
LANGUAGE plpgsql IMMUTABLE;

call google_ml.drop_model('blip2-text');
call google_ml.create_model(
     model_id => 'blip2-text',
     model_request_url => 'http://10.150.15.227/embeddings',
     model_provider => 'custom',
     model_type => 'text_embedding',
     model_in_transform_fn => 'google_ml.blip2_embedding_text_input',
     model_out_transform_fn => 'google_ml.blip2_embedding_text_output');
