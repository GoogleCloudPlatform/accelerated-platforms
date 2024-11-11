Steps:
1. Deploy Multi modal embedding model in GKE
- cd multimodal_emb/
- Follow README.md

2. Build AlloyDB
- cd alloy_db/
- Follow README.md:
    - Creates AlloyDB cluster, instance, users, database, table; Populate the product catalog and generate embeddings, vector index on text_embeddings

3. Semantic search
- cd backend_application/semantic_search/
- Follow README.md 

4. Deploy pre-trained model in GKE
- cd pretrained_model/
- kubectl apply -f deployment.yaml -n ml-team

5. [WIP] Test Rerank with pre-trained model end point
- cd backend_application/rerank_services
- Follow README.md 

