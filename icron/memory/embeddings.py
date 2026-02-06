"""Embedding providers for semantic memory.

Supports multiple embedding backends with automatic provider detection.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

import httpx

# Optional sentence-transformers import
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Embed a single text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats representing the embedding vector.
        """
        ...

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch.

        Default implementation calls embed() for each text.
        Subclasses may override for more efficient batch processing.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        return [await self.embed(text) for text in texts]

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension.

        Returns:
            The dimensionality of the embedding vectors.
        """
        ...


class OpenAIEmbedding(EmbeddingProvider):
    """OpenAI embedding provider using text-embedding-3-small."""

    MODEL = "text-embedding-3-small"
    DIMENSION = 1536
    API_URL = "https://api.openai.com/v1/embeddings"
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        """Initialize OpenAI embedding provider.

        Args:
            api_key: OpenAI API key.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def _request_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Make API request with retry logic for rate limits.

        Args:
            payload: Request payload.

        Returns:
            API response as dict.

        Raises:
            httpx.HTTPStatusError: If request fails after retries.
        """
        client = await self._get_client()
        last_exception: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.post(self.API_URL, json=payload)
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                last_exception = e
                if e.response.status_code == 429:  # Rate limited
                    retry_after = float(
                        e.response.headers.get("retry-after", self.RETRY_DELAY * (attempt + 1))
                    )
                    await asyncio.sleep(retry_after)
                elif e.response.status_code >= 500:  # Server error
                    await asyncio.sleep(self.RETRY_DELAY * (attempt + 1))
                else:
                    raise

        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected retry loop exit")

    async def embed(self, text: str) -> list[float]:
        """Embed a single text using OpenAI API.

        Args:
            text: The text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        payload = {"input": text, "model": self.MODEL}
        result = await self._request_with_retry(payload)
        return result["data"][0]["embedding"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in a single API call.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        payload = {"input": texts, "model": self.MODEL}
        result = await self._request_with_retry(payload)

        # Sort by index to maintain order
        embeddings_data = sorted(result["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]

    @property
    def dimension(self) -> int:
        """Return OpenAI embedding dimension (1536)."""
        return self.DIMENSION

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class GeminiEmbedding(EmbeddingProvider):
    """Google Gemini embedding provider using text-embedding-004."""

    MODEL = "text-embedding-004"
    DIMENSION = 768
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent"

    def __init__(self, api_key: str, *, timeout: float = 30.0) -> None:
        """Initialize Gemini embedding provider.

        Args:
            api_key: Google API key.
            timeout: Request timeout in seconds.
        """
        self._api_key = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Embed a single text using Gemini API.

        Args:
            text: The text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        client = await self._get_client()
        url = self.API_URL.format(model=self.MODEL)

        payload = {"model": f"models/{self.MODEL}", "content": {"parts": [{"text": text}]}}
        response = await client.post(
            url, json=payload, params={"key": self._api_key}
        )
        response.raise_for_status()

        result = response.json()
        return result["embedding"]["values"]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts using Gemini batchEmbedContents API.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        client = await self._get_client()
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.MODEL}:batchEmbedContents"

        requests = [{"model": f"models/{self.MODEL}", "content": {"parts": [{"text": text}]}} for text in texts]
        payload = {"requests": requests}

        response = await client.post(
            url, json=payload, params={"key": self._api_key}
        )
        response.raise_for_status()

        result = response.json()
        return [emb["values"] for emb in result["embeddings"]]

    @property
    def dimension(self) -> int:
        """Return Gemini embedding dimension (768)."""
        return self.DIMENSION

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()


class OllamaEmbedding(EmbeddingProvider):
    """Ollama local embedding provider using nomic-embed-text."""

    MODEL = "nomic-embed-text"
    DIMENSION = 768  # nomic-embed-text dimension
    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        *,
        timeout: float = 60.0,
    ) -> None:
        """Initialize Ollama embedding provider.

        Args:
            model: Model name (default: nomic-embed-text).
            host: Ollama server URL (default: http://localhost:11434).
            timeout: Request timeout in seconds.
        """
        self._model = model or self.MODEL
        self._host = (host or os.getenv("OLLAMA_HOST") or self.DEFAULT_HOST).rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._dimension: int | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self._timeout),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def embed(self, text: str) -> list[float]:
        """Embed a single text using Ollama API.

        Args:
            text: The text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        client = await self._get_client()
        url = f"{self._host}/api/embeddings"

        payload = {"model": self._model, "prompt": text}
        response = await client.post(url, json=payload)
        response.raise_for_status()

        result = response.json()
        embedding = result["embedding"]

        # Cache dimension from first response
        if self._dimension is None:
            self._dimension = len(embedding)

        return embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts (sequential calls as Ollama doesn't support batch).

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        # Ollama doesn't have native batch support, but we can parallelize
        tasks = [self.embed(text) for text in texts]
        return await asyncio.gather(*tasks)

    @property
    def dimension(self) -> int:
        """Return Ollama embedding dimension.

        Note: Actual dimension depends on the model used.
        """
        return self._dimension or self.DIMENSION

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    @staticmethod
    async def is_available(host: str | None = None) -> bool:
        """Check if Ollama server is available.

        Args:
            host: Ollama server URL.

        Returns:
            True if Ollama is reachable.
        """
        host = (host or os.getenv("OLLAMA_HOST") or OllamaEmbedding.DEFAULT_HOST).rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{host}/api/tags")
                return response.status_code == 200
        except (httpx.RequestError, httpx.TimeoutException):
            return False


class LocalEmbedding(EmbeddingProvider):
    """Local embedding provider using sentence-transformers.

    Requires sentence-transformers package: pip install sentence-transformers
    """

    MODEL = "all-MiniLM-L6-v2"
    DIMENSION = 384

    def __init__(self, model: str | None = None) -> None:
        """Initialize local embedding provider.

        Args:
            model: Model name (default: all-MiniLM-L6-v2).

        Raises:
            ImportError: If sentence-transformers is not installed.
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers is required for local embeddings. "
                "Install with: pip install sentence-transformers"
            )

        self._model_name = model or self.MODEL
        self._model: SentenceTransformer | None = None

    def _get_model(self) -> SentenceTransformer:
        """Lazy load the model."""
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        """Embed a single text using sentence-transformers.

        Args:
            text: The text to embed.

        Returns:
            Embedding vector as list of floats.
        """
        model = self._get_model()
        # Run CPU-bound encoding in executor to avoid blocking
        loop = asyncio.get_running_loop()
        embedding = await loop.run_in_executor(None, model.encode, text)
        return embedding.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts efficiently with sentence-transformers.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.
        """
        if not texts:
            return []

        model = self._get_model()
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(None, model.encode, texts)
        return [emb.tolist() for emb in embeddings]

    @property
    def dimension(self) -> int:
        """Return local embedding dimension (384 for all-MiniLM-L6-v2)."""
        if self._model is not None:
            return self._model.get_sentence_embedding_dimension()
        return self.DIMENSION

    async def close(self) -> None:
        """Release model resources."""
        self._model = None


async def get_embedding_provider(config: dict[str, Any] | None = None) -> EmbeddingProvider:
    """Factory function to get an embedding provider based on config.

    Auto-detection priority:
    1. OpenAI (if API key available)
    2. Gemini (if API key available)
    3. Ollama (if server available)
    4. Local (sentence-transformers)

    Args:
        config: Configuration dict with optional keys:
            - provider: "auto", "openai", "gemini", "ollama", or "local"
            - openai_api_key: OpenAI API key
            - gemini_api_key: Google API key
            - ollama_host: Ollama server URL
            - ollama_model: Ollama model name
            - local_model: Sentence-transformers model name

    Returns:
        Configured EmbeddingProvider instance.

    Raises:
        ValueError: If no suitable provider is available.

    Example:
        >>> provider = await get_embedding_provider({"provider": "auto", "openai_api_key": "sk-..."})
        >>> embedding = await provider.embed("Hello world")
    """
    config = config or {}
    provider = config.get("provider", "auto").lower()

    # Get API keys from config or environment
    openai_api_key = config.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
    gemini_api_key = config.get("gemini_api_key") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    ollama_host = config.get("ollama_host") or os.getenv("OLLAMA_HOST")

    if provider == "openai":
        if not openai_api_key:
            raise ValueError("OpenAI API key required for OpenAI embeddings")
        return OpenAIEmbedding(openai_api_key)

    if provider == "gemini":
        if not gemini_api_key:
            raise ValueError("Gemini API key required for Gemini embeddings")
        return GeminiEmbedding(gemini_api_key)

    if provider == "ollama":
        return OllamaEmbedding(
            model=config.get("ollama_model"),
            host=ollama_host,
        )

    if provider == "local":
        return LocalEmbedding(model=config.get("local_model"))

    # Auto-detection
    if provider == "auto":
        # Try OpenAI first
        if openai_api_key:
            return OpenAIEmbedding(openai_api_key)

        # Try Gemini
        if gemini_api_key:
            return GeminiEmbedding(gemini_api_key)

        # Try Ollama
        if await OllamaEmbedding.is_available(ollama_host):
            return OllamaEmbedding(
                model=config.get("ollama_model"),
                host=ollama_host,
            )

        # Fall back to local
        if SENTENCE_TRANSFORMERS_AVAILABLE:
            return LocalEmbedding(model=config.get("local_model"))

        raise ValueError(
            "No embedding provider available. Please provide an API key "
            "(OPENAI_API_KEY or GEMINI_API_KEY), start Ollama, or install "
            "sentence-transformers for local embeddings."
        )

    raise ValueError(f"Unknown embedding provider: {provider}")


__all__ = [
    "EmbeddingProvider",
    "OpenAIEmbedding",
    "GeminiEmbedding",
    "OllamaEmbedding",
    "LocalEmbedding",
    "get_embedding_provider",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
