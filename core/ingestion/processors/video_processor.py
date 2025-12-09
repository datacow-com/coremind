"""
Video Processor - Video understanding and content extraction.

Features:
- Keyframe extraction at configurable intervals
- Speech-to-text using Whisper
- VLM-based frame description
- Content summarization
"""

import asyncio
import logging
import os
import tempfile
from typing import Any

from core.state import IngestState
from core.utils.monitor import ingest_duration

logger = logging.getLogger(__name__)


class VideoProcessor:
    """
    Processes video files for knowledge base ingestion.

    This capability is part of the professional tier and supports:
    - MP4, AVI, MOV, MKV, WebM formats
    - Keyframe extraction
    - Audio transcription (Whisper)
    - Frame content description (VLM)
    - Video summarization

    Configuration:
        keyframe_interval: int - Seconds between keyframes
        transcription: bool - Enable speech-to-text
        whisper_model: "tiny" | "base" | "small" | "medium" | "large"
        frame_description: bool - Describe keyframes with VLM
        summarize: bool - Generate video summary
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.keyframe_interval = self.config.get("keyframe_interval", 10)
        self.transcription = self.config.get("transcription", True)
        self.whisper_model = self.config.get("whisper_model", "base")
        self.frame_description = self.config.get("frame_description", False)
        self.summarize = self.config.get("summarize", False)
        self._semaphore = asyncio.Semaphore(1)  # Video processing is heavy

    async def __call__(self, state: IngestState) -> IngestState:
        """Process video file from state."""
        with ingest_duration.labels(stage="video_processor").time():
            return await self.process(state)

    async def process(self, state: IngestState) -> IngestState:
        """Process video file and extract content."""
        file_type = state.get("file_type", "").lower()

        if file_type not in ("mp4", "avi", "mov", "mkv", "webm"):
            logger.debug(f"VideoProcessor skipping non-video file: {file_type}")
            return state

        async with self._semaphore:
            try:
                # Get video content
                raw_content = state.get("raw_content")
                if not raw_content:
                    file_path = state.get("file_path", "")
                    from core.storage.blob_store import get_blob_store

                    blob = get_blob_store()
                    raw_content = await blob.get(file_path)

                # Create temp file for processing
                with tempfile.NamedTemporaryFile(suffix=f".{file_type}", delete=False) as tmp:
                    tmp.write(raw_content)
                    temp_path = tmp.name

                try:
                    parsed_blocks = []

                    # Extract keyframes
                    keyframes = await self._extract_keyframes(temp_path)
                    state["images"] = keyframes

                    # Transcribe audio
                    if self.transcription:
                        transcript = await self._transcribe_audio(temp_path)
                        if transcript:
                            parsed_blocks.append(
                                {
                                    "type": "text",
                                    "content": f"## Video Transcript\n\n{transcript}",
                                    "page": 0,
                                    "metadata": {
                                        "source": "whisper",
                                        "model": self.whisper_model,
                                    },
                                }
                            )

                    # Describe keyframes with VLM
                    if self.frame_description and keyframes:
                        descriptions = await self._describe_frames(keyframes)
                        parsed_blocks.append(
                            {
                                "type": "text",
                                "content": f"## Keyframe Descriptions\n\n{descriptions}",
                                "page": 0,
                                "metadata": {"source": "vlm"},
                            }
                        )

                    # Generate summary
                    if self.summarize:
                        summary = await self._generate_summary(parsed_blocks, keyframes)
                        if summary:
                            parsed_blocks.insert(
                                0,
                                {
                                    "type": "text",
                                    "content": f"## Video Summary\n\n{summary}",
                                    "page": 0,
                                    "metadata": {"source": "llm_summary"},
                                },
                            )

                    # Add video metadata
                    metadata_block = await self._get_video_metadata(temp_path)
                    if metadata_block:
                        parsed_blocks.append(metadata_block)

                    state["parsed_blocks"] = parsed_blocks
                    state["extracted_text"] = "\n\n".join(
                        b["content"] for b in parsed_blocks if b.get("content")
                    )

                finally:
                    # Cleanup temp file
                    try:
                        os.unlink(temp_path)
                    except Exception:
                        pass

            except Exception as e:
                logger.error(f"Video processing failed: {e}")
                state["error_log"].append(
                    {
                        "stage": "video_processor",
                        "error": str(e),
                    }
                )

        return state

    async def _extract_keyframes(self, video_path: str) -> list[dict[str, Any]]:
        """Extract keyframes from video at configured interval."""
        try:
            import cv2
            import numpy as np

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                raise ValueError(f"Cannot open video: {video_path}")

            fps = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = total_frames / fps if fps > 0 else 0

            logger.info(
                f"Video: {duration:.1f}s duration, {fps:.1f} fps, "
                f"extracting every {self.keyframe_interval}s"
            )

            keyframes = []
            frame_interval = int(fps * self.keyframe_interval)
            current_frame = 0

            while True:
                cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                ret, frame = cap.read()

                if not ret:
                    break

                timestamp = current_frame / fps if fps > 0 else 0

                # Convert to JPEG bytes
                _, buffer = cv2.imencode(".jpg", frame)
                image_data = buffer.tobytes()

                keyframes.append(
                    {
                        "data": image_data,
                        "page": len(keyframes),
                        "timestamp": timestamp,
                        "frame_number": current_frame,
                        "metadata": {
                            "type": "keyframe",
                            "timestamp_str": self._format_timestamp(timestamp),
                        },
                    }
                )

                current_frame += frame_interval
                if current_frame >= total_frames:
                    break

            cap.release()
            logger.info(f"Extracted {len(keyframes)} keyframes")
            return keyframes

        except ImportError:
            logger.warning("OpenCV not installed, keyframe extraction unavailable")
            return []
        except Exception as e:
            logger.error(f"Keyframe extraction failed: {e}")
            return []

    async def _transcribe_audio(self, video_path: str) -> str:
        """Transcribe audio track using Whisper."""
        try:
            import whisper

            # Load model
            model = whisper.load_model(self.whisper_model)

            # Transcribe
            logger.info(f"Transcribing audio with Whisper ({self.whisper_model})")
            result = model.transcribe(video_path, fp16=False)

            # Format with timestamps
            segments = result.get("segments", [])
            lines = []

            for seg in segments:
                start = self._format_timestamp(seg["start"])
                end = self._format_timestamp(seg["end"])
                text = seg["text"].strip()
                lines.append(f"[{start} → {end}] {text}")

            return "\n".join(lines)

        except ImportError:
            logger.warning("Whisper not installed, transcription unavailable")
            return ""
        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return ""

    async def _describe_frames(self, keyframes: list[dict[str, Any]]) -> str:
        """Generate descriptions for keyframes using VLM."""
        try:
            from core.ingestion.nodes.image_captioner import ImageCaptioner

            captioner = ImageCaptioner()
            descriptions = []

            for i, frame in enumerate(keyframes[:10]):  # Limit to first 10 frames
                timestamp = frame.get("metadata", {}).get("timestamp_str", f"Frame {i}")

                # Create a mini-state for the captioner
                temp_state = {
                    "images": [frame],
                    "parsed_blocks": [],
                    "strategy_config": {"vlm_provider": "auto"},
                    "error_log": [],
                }

                try:
                    result_state = await captioner(temp_state)
                    blocks = result_state.get("parsed_blocks", [])
                    if blocks:
                        description = blocks[0].get("content", "")
                        descriptions.append(f"**{timestamp}**: {description}")
                except Exception as e:
                    logger.warning(f"Failed to describe frame {i}: {e}")
                    descriptions.append(f"**{timestamp}**: [Description unavailable]")

            return "\n\n".join(descriptions)

        except Exception as e:
            logger.error(f"Frame description failed: {e}")
            return ""

    async def _generate_summary(
        self, blocks: list[dict[str, Any]], keyframes: list[dict[str, Any]]
    ) -> str:
        """Generate a summary of the video content."""
        try:
            from core.llm.gateway import get_llm

            # Compile content for summarization
            content_parts = []

            for block in blocks:
                if block.get("type") == "text":
                    content_parts.append(block.get("content", ""))

            if not content_parts:
                return ""

            content = "\n\n".join(content_parts)

            # Prepare prompt
            prompt = f"""Based on the following video content (transcript and keyframe descriptions),
provide a comprehensive summary of the video:

{content[:8000]}

Summary:"""

            llm = get_llm()
            response = await llm.ainvoke(prompt)

            return response.content if hasattr(response, "content") else str(response)

        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return ""

    async def _get_video_metadata(self, video_path: str) -> dict[str, Any] | None:
        """Extract video metadata."""
        try:
            import cv2

            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            fps = cap.get(cv2.CAP_PROP_FPS)
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            duration = frame_count / fps if fps > 0 else 0

            cap.release()

            metadata_text = f"""## Video Metadata

- **Duration**: {self._format_timestamp(duration)}
- **Resolution**: {width} x {height}
- **Frame Rate**: {fps:.2f} fps
- **Total Frames**: {frame_count}
"""

            return {
                "type": "metadata",
                "content": metadata_text,
                "page": 0,
                "metadata": {
                    "duration_seconds": duration,
                    "width": width,
                    "height": height,
                    "fps": fps,
                    "frame_count": frame_count,
                },
            }

        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"Failed to get video metadata: {e}")
            return None

    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"


# Factory function for capability loading
def create_video_processor(config: dict[str, Any] | None = None) -> VideoProcessor:
    """Factory function for creating VideoProcessor instances."""
    return VideoProcessor(config)
