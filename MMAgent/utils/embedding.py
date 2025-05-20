from typing import List
import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModel, AutoTokenizer

class EmbeddingScorer:
    """
    A class for performing semantic search using embeddings.
    Uses the gte-multilingual-base model from Alibaba-NLP.
    """
    
    def __init__(self, model_name='Alibaba-NLP/gte-multilingual-base'):
        """
        Initialize the EmbeddingScorer with the specified model.
        
        Args:
            model_name (str): Name of the model to use.
        """
        # Load the tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
        self.dimension = 768  # The output dimension of the embedding
    
    def score_method(self, query: str, methods: List[dict]) -> List[dict]:
        """
        Calculate similarity between a query and a list of methods.
        
        Args:
            query (str): The query sentence.
            methods (list): List of method dictionaries to compare against the query.
            
        Returns:
            list: List of similarity scores between the query and each method.
        """
        # Prepare sentences
        sentences = [f"{method['method']}: {method.get('description', '')}" for method in methods]
        texts = [query] + sentences
        
        # Tokenize the input texts
        batch_dict = self.tokenizer(texts, max_length=8192, padding=True, truncation=True, return_tensors='pt')
        
        # Get embeddings
        with torch.no_grad():
            outputs = self.model(**batch_dict)
            
        # Get embeddings from the last hidden state
        embeddings = outputs.last_hidden_state[:, 0][:self.dimension]
        
        # Normalize embeddings
        embeddings = F.normalize(embeddings, p=2, dim=1)
        
        # Calculate similarities
        query_embedding = embeddings[0].unsqueeze(0)  # Shape: [1, dimension]
        method_embeddings = embeddings[1:]  # Shape: [num_methods, dimension]
        
        # Calculate cosine similarities (scaled by 100 as in the example)
        similarities = (query_embedding @ method_embeddings.T) * 100
        similarities = similarities.squeeze().tolist()
        
        # If only one method, similarities will be a scalar
        if not isinstance(similarities, list):
            similarities = [similarities]
        
        # Format results
        result = []
        for i, similarity in enumerate(similarities, start=1):
            result.append({
                "method_index": i,
                "score": float(similarity)
            })
        
        return result

if __name__ == "__main__":
    es = EmbeddingScorer()
    print(es.score_method("How to solve the problem of the user", [{"method": "Method 1", "description": "Description 1"}, {"method": "Method 2", "description": "Description 2"}]))
