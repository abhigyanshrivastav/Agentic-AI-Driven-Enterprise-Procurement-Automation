import os
import numpy as np
from typing import List, Optional
from src.config import get_settings, is_valid_api_key
from src.observability import logger

class EmbeddingClient:
    """Wrapper for text embedding generation with LiteLLM / OpenAI API and deterministic offline fallback."""

    def __init__(self, model_name: Optional[str] = None, require_live_api: Optional[bool] = None, force_mock: bool = False):
        settings = get_settings()
        self.provider = settings.llm_provider
        self.model_name = model_name or settings.embedding_model
        self.api_key = settings.llm_api_key
        self.require_live_api = require_live_api
        self.force_mock = force_mock

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        # Attempt API call if API key exists and LIVE_API is required
        if is_valid_api_key(self.api_key) and not self.force_mock and self.require_live_api is True:
            try:
                import litellm
                model_param = self.model_name
                if (self.provider == "gemini" or model_param.startswith("gemini-") or "gemini" in model_param) and not model_param.startswith("gemini/"):
                    model_param = f"gemini/{model_param}"
                elif not model_param.startswith("gemini/") and not model_param.startswith("openai/") and "/" not in model_param:
                    if self.provider:
                        model_param = f"{self.provider}/{model_param}"

                kwargs = {
                    "model": model_param,
                    "input": texts,
                    "api_key": self.api_key
                }
                if self.provider == "gemini":
                    kwargs["gemini_api_key"] = self.api_key

                response = litellm.embedding(**kwargs)
                return [data["embedding"] for data in response["data"]]
            except Exception as e:
                logger.error(f"Embedding API call failed: {e}")
                if self.require_live_api or True:
                    raise RuntimeError(f"PROVIDER_EMBEDDING_ERROR: Embedding API call failed: {e}")

        if self.require_live_api:
            raise ValueError("FAIL-FAST: Live embedding requested but API key is missing or invalid.")

        # Fallback offline embedding generation for local reproducibility without API key
        return self._generate_fallback_embeddings(texts)

    def _generate_fallback_embeddings(self, texts: List[str], dim: int = 1536) -> List[List[float]]:
        embeddings = []
        for text in texts:
            seed = sum(ord(c) for c in text) % 10000
            rng = np.random.RandomState(seed)
            vec = rng.randn(dim)
            norm = np.linalg.norm(vec)
            vec = vec / norm if norm > 0 else vec
            embeddings.append(vec.tolist())
        return embeddings
