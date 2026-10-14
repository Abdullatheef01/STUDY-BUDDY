import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

def env(key, default=None, required=False):
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(f"Missing env var: {key}")
    return value

ENV = env("ENV", "development")
DEBUG = env("DEBUG", "false").lower() == "true"

GROQ_API_KEY = env("GROQ_API_KEY")

LANGCHAIN_API_KEY = env("LANGCHAIN_API_KEY", "")
LANGCHAIN_PROJECT = env("LANGCHAIN_PROJECT", "ResearchPaper-Assistant")

CHROMA_PERSIST_DIR = Path(env("CHROMA_PERSIST_DIR", BASE_DIR / "data/chroma"))
FAISS_CACHE_DIR = Path(env("FAISS_CACHE_DIR", BASE_DIR / "data/faiss_cache"))

EMBEDDING_MODEL_NAME = env("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")

DATABASE_URL = env("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data/sessions.db'}")

CHROMA_PERSIST_DIR.mkdir(parents=True, exist_ok=True)
FAISS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
