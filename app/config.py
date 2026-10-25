import os
from dataclasses import dataclass
from pathlib import Path


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    top_k: int = 4
    min_score: float = 0.30
    llm_timeout_s: float = 120.0
    temperature: float = 0.1
    index_dir: Path = Path("storage/index")
    docs_dir: Path = Path("data/sample_docs")
    max_upload_mb: int = 10

    @classmethod
    def from_env(cls) -> "Settings":
        defaults = cls()
        return cls(
            ollama_url=_env("OLLAMA_URL", defaults.ollama_url).rstrip("/"),
            ollama_model=_env("OLLAMA_MODEL", defaults.ollama_model),
            top_k=int(_env("TOP_K", str(defaults.top_k))),
            min_score=float(_env("MIN_SCORE", str(defaults.min_score))),
            llm_timeout_s=float(_env("LLM_TIMEOUT_S", str(defaults.llm_timeout_s))),
            temperature=float(_env("TEMPERATURE", str(defaults.temperature))),
            index_dir=Path(_env("INDEX_DIR", str(defaults.index_dir))),
            docs_dir=Path(_env("DOCS_DIR", str(defaults.docs_dir))),
            max_upload_mb=int(_env("MAX_UPLOAD_MB", str(defaults.max_upload_mb))),
        )
