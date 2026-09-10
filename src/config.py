import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import BaseModel

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    class BaseSettings(BaseModel):
        def __init__(self, **kwargs):
            env_kwargs = {}
            for field in self.__class__.model_fields:
                env_val = os.getenv(field.upper())
                if env_val is not None:
                    env_kwargs[field] = env_val
            env_kwargs.update(kwargs)
            super().__init__(**env_kwargs)

    def SettingsConfigDict(**kwargs):
        return kwargs

# Canonical Project Root (independent of shell CWD)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

PRICING_VERSION = "1.0.0-202608"

# Explicit Decoupled Model Pricing Schedule ($ per 1,000,000 tokens)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "gpt-4o-mini": {
        "uncached_input_cost_per_1m": 0.15,
        "cached_input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.60
    },
    "gpt-4o-mini-2024-07-18": {
        "uncached_input_cost_per_1m": 0.15,
        "cached_input_cost_per_1m": 0.075,
        "output_cost_per_1m": 0.60
    },
    "gpt-4o": {
        "uncached_input_cost_per_1m": 2.50,
        "cached_input_cost_per_1m": 1.25,
        "output_cost_per_1m": 10.00
    },
    "gemini-1.5-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini/gemini-1.5-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini-2.5-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini/gemini-2.5-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini-3.5-flash-lite": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini/gemini-3.5-flash-lite": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini-3.6-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini/gemini-3.6-flash": {
        "uncached_input_cost_per_1m": 0.075,
        "cached_input_cost_per_1m": 0.01875,
        "output_cost_per_1m": 0.30
    },
    "gemini-embedding-001": {
        "uncached_input_cost_per_1m": 0.00,
        "cached_input_cost_per_1m": 0.00,
        "output_cost_per_1m": 0.00
    },
    "gemini/gemini-embedding-001": {
        "uncached_input_cost_per_1m": 0.00,
        "cached_input_cost_per_1m": 0.00,
        "output_cost_per_1m": 0.00
    },
    "text-embedding-004": {
        "uncached_input_cost_per_1m": 0.00,
        "cached_input_cost_per_1m": 0.00,
        "output_cost_per_1m": 0.00
    },
    "gemini/text-embedding-004": {
        "uncached_input_cost_per_1m": 0.00,
        "cached_input_cost_per_1m": 0.00,
        "output_cost_per_1m": 0.00
    }
}

class AppConfig(BaseModel):
    name: str = "Enterprise Procurement LLMOps Prototype"
    version: str = "1.0.0"
    environment: str = "development"

class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    timeout_seconds: int = 30

class LLMConfig(BaseModel):
    provider: str = "openai"
    default_model: str = "gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    temperature: float = 0.0
    max_tokens: int = 1000
    max_agent_iterations: int = 5

class RAGConfig(BaseModel):
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3

class GuardrailsConfig(BaseModel):
    po_approval_threshold_usd: float = 5000.0
    allowed_roles_above_threshold: list = ["manager", "admin"]
    enable_strict_output_schema: bool = True

class Settings(BaseSettings):
    llm_provider: str = "openai"
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    model_snapshot: str = "2024-07-18"
    api_endpoint: str = "https://api.openai.com/v1"
    embedding_model: str = "text-embedding-3-small"
    max_agent_iterations: int = 5
    temperature: float = 0.0
    
    # Explicit Seed Capability Metadata
    seed_requested: Optional[int] = 2026
    seed_supported: bool = False
    seed_applied: Optional[int] = None
    
    app_env: str = "development"
    log_level: str = "INFO"
    
    db_path: str = "data/processed/procurement.db"
    faiss_index_path: str = "data/vector_store/index.faiss"
    faiss_metadata_path: str = "data/vector_store/metadata.json"
    config_path: str = "configs/app_config.yaml"
    experiments_config_path: str = "configs/experiments_config.yaml"
    
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def model_post_init(self, __context: Any) -> None:
        if self.llm_provider == "gemini":
            if self.embedding_model == "text-embedding-3-small":
                self.embedding_model = "gemini-embedding-001"
            if self.api_endpoint == "https://api.openai.com/v1":
                self.api_endpoint = "https://generativelanguage.googleapis.com/v1beta"

    def get_db_path(self) -> Path:
        p = Path(self.db_path)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    def get_faiss_index_path(self) -> Path:
        p = Path(self.faiss_index_path)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    def get_faiss_metadata_path(self) -> Path:
        p = Path(self.faiss_metadata_path)
        return p if p.is_absolute() else (PROJECT_ROOT / p).resolve()

    def get_raw_policies_dir(self) -> Path:
        return (PROJECT_ROOT / "data" / "raw" / "policies").resolve()

    def get_eval_dataset_path(self) -> Path:
        return (PROJECT_ROOT / "data" / "eval_dataset.json").resolve()

    def get_output_dir(self) -> Path:
        return (PROJECT_ROOT / "experiments" / "outputs").resolve()

def load_yaml_config(filepath: str) -> Dict[str, Any]:
    path = Path(filepath)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def get_settings() -> Settings:
    return Settings()

def get_app_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    settings = get_settings()
    target_path = config_path or settings.config_path
    return load_yaml_config(target_path)

def get_experiments_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    settings = get_settings()
    target_path = config_path or settings.experiments_config_path
    return load_yaml_config(target_path)

def is_valid_api_key(api_key: Optional[str]) -> bool:
    """Provider-agnostic API key validation check."""
    if not api_key:
        return False
    k = api_key.strip()
    if not k:
        return False
    k_lower = k.lower()
    if k_lower in ["your_api_key_here", "your_api_key", "placeholder", "none", "null"]:
        return False
    if k_lower.startswith("your_api_key"):
        return False
    return True
