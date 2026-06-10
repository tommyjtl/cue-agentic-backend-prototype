import httpx

from cue_search.config import settings


class EmbeddingClient:
    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.embeddings_base_url).rstrip("/")
        self.model = model or settings.embeddings_model

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        with httpx.Client(timeout=120.0) as client:
            response = client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": texts},
            )
            response.raise_for_status()
            payload = response.json()

        embeddings = payload.get("embeddings")
        if not isinstance(embeddings, list):
            raise RuntimeError("Ollama /api/embed returned an unexpected payload.")
        return embeddings

    def embed_query(self, query: str) -> list[float]:
        vectors = self.embed_texts([query])
        if not vectors:
            raise RuntimeError("Failed to embed query.")
        return vectors[0]
