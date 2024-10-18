/*This script uses alloyDB google_ml_integration.enable_model_support 
This is database flag in AlloyDB for PostgreSQL. 
It is a crucial setting that allows you to use the google_ml_integration extension to access and utilize machine learning models directly within your AlloyDB environment.*/


-- set google_ml_integration.enable_model_support = 'on';
/*Create function to call the fine-tuned-model*/
call google_ml.drop_model('gke-vllm-finetuned');
CALL
    google_ml.create_model(
      model_id => 'gke-vllm-finetuned',
      model_request_url => :'finetune_model_ep',
      model_provider => 'custom',
      model_type => 'generic',
      model_qualified_name => '/data/models/model-gemma2-a100/experiment-a2aa2c3it1',
      model_auth_type => null,
      model_auth_id => null,
      generate_headers_fn => null,
      model_in_transform_fn => null,
      model_out_transform_fn => null);

/* Function to send prompts to the completion api for fine-tuned-model*/
create or replace function vllm_completion(input_text text)
returns TEXT AS $$
SELECT json_extract_path_text(google_ml.predict_row('gke-vllm-finetuned',
   json_build_object('prompt', input_text,
   'model', '/data/models/model-gemma2-a100/experiment-a2aa2c3it1',
   'max_tokens', 1024))::json, 'choices','0','text');
$$ LANGUAGE sql IMMUTABLE;


/*Create function to call the pre-trained gemma model*/
call google_ml.drop_model('gke-vllm-gemma2');
CALL
    google_ml.create_model(
      model_id => 'gke-vllm-gemma2',
      model_request_url => :'pretrained_model_ep',
      model_provider => 'custom',
      model_type => 'generic',
      model_qualified_name => 'google/gemma-2-2b',
      model_auth_type => null,
      model_auth_id => null,
      generate_headers_fn => null,
      model_in_transform_fn => null,
      model_out_transform_fn => null);

/* Function to send prompts to the completion api for gemma model*/
create or replace function gemma2_completion(input_text text)
returns TEXT AS $$
SELECT json_extract_path_text(google_ml.predict_row('gke-vllm-gemma2',
   json_build_object('prompt', input_text,
   'model', 'google/gemma-2-2b',
   'max_tokens', 1024))::json, 'choices','0','text');
$$ LANGUAGE sql IMMUTABLE;


/*Create function to call the multimodal-blip2 multimodal model*/
call google_ml.drop_model('multimodal-blip2');
CALL
    google_ml.create_model(
      model_id => 'multimodal-blip2',
      model_request_url => :'embedding_endpoint',
      model_provider => 'custom',
      model_type => 'generic',
      model_auth_type => null,
      model_auth_id => null,
      generate_headers_fn => null,
      model_in_transform_fn => null,
      model_out_transform_fn => null);

/* Function to generate text embeddings only from multimodal blip2 model*/
create or replace function google_ml.multimodal_embedding(model_id varchar, input_text text, image_uri text)
returns JSON AS $$
SELECT google_ml.predict_row('multimodal-blip2', json_build_object('caption', input_text, 'image_uri', image_uri));
$$ LANGUAGE sql IMMUTABLE;


/* Function to generate text embeddings only from multimodal blip2 model*/
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

/*Create function to call the multimodal-blip2 model for text embeddings*/
call google_ml.drop_model('blip2-text');
call google_ml.create_model(
     model_id => 'blip2-text',
     model_request_url => :'embedding_endpoint',
     model_provider => 'custom',
     model_type => 'text_embedding',
     model_in_transform_fn => 'google_ml.blip2_embedding_text_input',
     model_out_transform_fn => 'google_ml.blip2_embedding_text_output');


create or replace function google_ml.embedding_text(input_text text)
returns vector as $$
SELECT google_ml.embedding('blip2-text', input_text);
$$
LANGUAGE sql IMMUTABLE;
