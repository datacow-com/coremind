"""
Multimodal Embedder - Unified embeddings for different modalities.

Supports generating embeddings for:
- Text content
- Images (via CLIP or VLM)
- Tables (via specialized encoding)
- Mixed content (combination)
"""

import asyncio
import io
import logging
import os
from typing import Any, Literal

import httpx

logger = logging.getLogger(__name__)


# Modality types
ModalityType = Literal["text", "image", "table", "mixed"]


class MultimodalEmbedder:
    """
    Generates unified embeddings for different content modalities.

    Supports multiple embedding strategies:
    - CLIP-based for image-text alignment
    - BGE-M3 for text (with image descriptions)
    - Specialized table encoding

    Configuration:
        text_model: str - Model for text embeddings
        image_model: str - Model for image embeddings (CLIP variant)
        unified_space: bool - Project all modalities to same space
        dimension: int - Embedding dimension
    """

    # Default models
    DEFAULT_TEXT_MODEL = "BAAI/bge-m3"
    DEFAULT_IMAGE_MODEL = "openai/clip-vit-large-patch14"

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.text_model = self.config.get("text_model", self.DEFAULT_TEXT_MODEL)
        self.image_model = self.config.get("image_model", self.DEFAULT_IMAGE_MODEL)
        self.unified_space = self.config.get("unified_space", True)
        self.dimension = self.config.get("dimension", 1024)
        self._text_embedder = None
        self._image_embedder = None
        self._semaphore = asyncio.Semaphore(4)

    async def embed(self, content: str | bytes, modality: ModalityType = "text") -> list[float]:
        """
        Generate embedding for content of any modality.

        Args:
            content: Text string or image bytes
            modality: Type of content

        Returns:
            Embedding vector (1024-dim by default)
        """
        async with self._semaphore:
            if modality == "text":
                return await self._embed_text(content)
            elif modality == "image":
                return await self._embed_image(content)
            elif modality == "table":
                return await self._embed_table(content)
            elif modality == "mixed":
                return await self._embed_mixed(content)
            else:
                raise ValueError(f"Unknown modality: {modality}")

    async def embed_batch(self, items: list[tuple[str | bytes, ModalityType]]) -> list[list[float]]:
        """Embed multiple items in batch."""
        tasks = [self.embed(content, modality) for content, modality in items]
        return await asyncio.gather(*tasks)

    async def _embed_text(self, text: str) -> list[float]:
        """Generate text embedding."""
        try:
            # Try local embedding first
            embedder = await self._get_text_embedder()
            if embedder:
                return await embedder.aembed_query(text)

            # Fallback to API
            return await self._embed_text_api(text)

        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            return [0.0] * self.dimension

    async def _embed_image(self, image_data: bytes) -> list[float]:
        """Generate image embedding using CLIP or similar model."""
        try:
            # Method 1: Use local CLIP model
            embedding = await self._embed_image_clip_local(image_data)
            if embedding:
                return embedding

            # Method 2: Use VLM to describe image, then embed description
            embedding = await self._embed_image_via_description(image_data)
            if embedding:
                return embedding

            # Fallback: Zero vector
            return [0.0] * self.dimension

        except Exception as e:
            logger.error(f"Image embedding failed: {e}")
            return [0.0] * self.dimension

    async def _embed_table(self, table_content: str) -> list[float]:
        """
        Generate table embedding.

        Tables are embedded as structured text with special formatting
        to preserve column/row relationships.
        """
        # Pre-process table to emphasize structure
        structured_text = self._format_table_for_embedding(table_content)
        return await self._embed_text(structured_text)

    async def _embed_mixed(self, content: Any) -> list[float]:
        """
        Generate embedding for mixed-modality content.

        For content with both text and images, we:
        1. Embed each component separately
        2. Average the embeddings (weighted by content amount)
        """
        if isinstance(content, dict):
            text = content.get("text", "")
            images = content.get("images", [])
        else:
            # Assume it's text
            return await self._embed_text(str(content))

        embeddings = []
        weights = []

        # Embed text if present
        if text:
            text_emb = await self._embed_text(text)
            embeddings.append(text_emb)
            weights.append(len(text))

        # Embed images if present
        for img_data in images[:3]:  # Limit to 3 images
            img_emb = await self._embed_image(img_data)
            embeddings.append(img_emb)
            weights.append(1000)  # Weight images as ~1000 chars

        if not embeddings:
            return [0.0] * self.dimension

        # Weighted average
        return self._weighted_average(embeddings, weights)

    async def _get_text_embedder(self):
        """Get or initialize text embedder."""
        if self._text_embedder is None:
            try:
                from core.embedding.registry import get_embedder

                self._text_embedder = get_embedder(self.text_model)
            except ImportError:
                pass
        return self._text_embedder

    async def _embed_text_api(self, text: str) -> list[float]:
        """Embed text via API (OpenAI or similar)."""
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("No OpenAI API key for text embedding")
            return [0.0] * self.dimension

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "text-embedding-3-small",
                    "input": text[:8000],  # Limit length
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            embedding = data["data"][0]["embedding"]

            # Pad or truncate to target dimension
            if len(embedding) < self.dimension:
                embedding.extend([0.0] * (self.dimension - len(embedding)))
            return embedding[: self.dimension]

    async def _embed_image_clip_local(self, image_data: bytes) -> list[float] | None:
        """Embed image using local CLIP model."""
        try:
            import torch
            from PIL import Image
            from transformers import CLIPModel, CLIPProcessor

            # Load model (will be cached)
            model = CLIPModel.from_pretrained(self.image_model)
            processor = CLIPProcessor.from_pretrained(self.image_model)

            # Process image
            image = Image.open(io.BytesIO(image_data)).convert("RGB")
            inputs = processor(images=image, return_tensors="pt")

            with torch.no_grad():
                features = model.get_image_features(**inputs)

            embedding = features[0].tolist()

            # Project to target dimension if needed
            if len(embedding) != self.dimension:
                embedding = self._project_dimension(embedding, self.dimension)

            return embedding

        except ImportError:
            logger.debug("CLIP not available locally")
            return None
        except Exception as e:
            logger.warning(f"Local CLIP embedding failed: {e}")
            return None

    async def _embed_image_via_description(self, image_data: bytes) -> list[float] | None:
        """Embed image by first generating description, then embedding text."""
        try:
            # Generate description using VLM
            description = await self._describe_image(image_data)
            if description:
                return await self._embed_text(description)
            return None
        except Exception as e:
            logger.warning(f"Image description embedding failed: {e}")
            return None

    async def _describe_image(self, image_data: bytes) -> str | None:
        """Generate image description using VLM."""
        try:
            from core.ingestion.nodes.image_captioner import ImageCaptioner

            captioner = ImageCaptioner()
            state = {
                "images": [{"data": image_data, "page": 0}],
                "parsed_blocks": [],
                "strategy_config": {"vlm_provider": "auto"},
                "error_log": [],
            }

            result = await captioner(state)
            blocks = result.get("parsed_blocks", [])

            if blocks:
                return blocks[0].get("content", "")
            return None

        except Exception as e:
            logger.warning(f"Image description failed: {e}")
            return None

    def _format_table_for_embedding(self, table_content: str) -> str:
        """Format table content for better embedding representation."""
        # Add structure markers
        lines = table_content.strip().split("\n")
        formatted_lines = []

        for i, line in enumerate(lines):
            if i == 0:
                formatted_lines.append(f"[TABLE HEADER] {line}")
            elif line.strip().startswith("|---"):
                continue  # Skip separator
            else:
                formatted_lines.append(f"[ROW {i}] {line}")

        return "\n".join(formatted_lines)

    def _project_dimension(self, embedding: list[float], target_dim: int) -> list[float]:
        """Project embedding to target dimension (simple padding/truncation)."""
        if len(embedding) >= target_dim:
            return embedding[:target_dim]
        else:
            return embedding + [0.0] * (target_dim - len(embedding))

    def _weighted_average(self, embeddings: list[list[float]], weights: list[float]) -> list[float]:
        """Compute weighted average of embeddings."""
        if not embeddings:
            return [0.0] * self.dimension

        total_weight = sum(weights)
        if total_weight == 0:
            total_weight = len(embeddings)
            weights = [1.0] * len(embeddings)

        result = [0.0] * len(embeddings[0])
        for emb, weight in zip(embeddings, weights, strict=False):
            for i, val in enumerate(emb):
                result[i] += val * (weight / total_weight)

        return result


# Factory function
def create_multimodal_embedder(config: dict[str, Any] | None = None) -> MultimodalEmbedder:
    """Factory function for creating MultimodalEmbedder instances."""
    return MultimodalEmbedder(config)
