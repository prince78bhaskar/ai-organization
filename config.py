"""Saari settings yahin hain. Model badalna ho to sirf yahan badlo."""

ORCHESTRATOR_MODEL = "qwen3.5:2b"
STUDY_MODEL = "qwen3.5:2b"
RESEARCH_MODEL = "qwen3.5:2b"
CODING_MODEL = "qwen2.5-coder:3b"
VISION_MODEL = "qwen3-vl:2b"   # scanned / handwritten / images
EMBED_MODEL = "bge-m3"         # RAG embeddings

CHROMA_DIR = "memory/chroma"
CODE_TIMEOUT_SECONDS = 20
MAX_FIX_ATTEMPTS = 3
RAG_TOP_K = 4
