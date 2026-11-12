from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    database_path: Path | None = None
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    embedding_provider: str = "local"
    embedding_model: str = ""
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    max_upload_mb: int = 15
    top_k: int = 4
    min_score: float = 0.10

    @classmethod
    def from_env(cls):
        load_dotenv(ROOT.parents[1] / ".env", override=False)
        load_dotenv(ROOT / ".env", override=False)
        database = Path(os.getenv("DATABASE_PATH", str(ROOT / "data/companion.db"))).expanduser().resolve()
        raw_dir = Path(os.getenv("KNOWLEDGE_DATA_DIR", str(database.parent / "knowledge"))).expanduser()
        return cls(
            data_dir=raw_dir if raw_dir.is_absolute() else ROOT / raw_dir,
            database_path=database,
            llm_model=(os.getenv("LLM_MODEL") or (os.getenv("AGENT_MODEL", "openai:gpt-4o-mini") if os.getenv("OPENAI_API_KEY") else "")).removeprefix("openai:").strip(),
            llm_api_key=os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
            llm_base_url=os.getenv("LLM_BASE_URL") or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            embedding_provider=os.getenv("EMBEDDING_PROVIDER", "local"),
            embedding_model=os.getenv("EMBEDDING_MODEL", ""),
            embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
            embedding_base_url=os.getenv("EMBEDDING_BASE_URL", ""),
            max_upload_mb=int(os.getenv("MAX_UPLOAD_MB", "15")),
            top_k=int(os.getenv("RETRIEVAL_TOP_K", "4")),
            min_score=float(os.getenv("RETRIEVAL_MIN_SCORE", "0.10")),
        )
