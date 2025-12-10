"""
Quality Checker Node - Validates chunk quality before indexing.

Features:
- Content quality scoring
- Empty/low-quality chunk filtering
- Deduplication
- PII detection (optional)
"""

from typing import Any

from core.state import IngestState

try:
    from core.utils.monitor import ingest_duration
except ImportError:
    ingest_duration = None


class QualityChecker:
    """
    Validates and filters chunks based on quality metrics.
    """
    
    # Minimum content length for valid chunks
    MIN_CONTENT_LENGTH = 10
    
    # Minimum quality score threshold
    MIN_QUALITY_SCORE = 0.3
    
    async def __call__(self, state: IngestState) -> IngestState:
        """Check quality of chunks and filter out low-quality ones."""
        if ingest_duration:
            with ingest_duration.labels(stage="quality_checker").time():
                return await self._check_quality(state)
        return await self._check_quality(state)
    
    async def _check_quality(self, state: IngestState) -> IngestState:
        cfg = state.get("strategy_config", {})
        
        # Skip if quality checking disabled
        if not cfg.get("enable_cleaning", True):
            state["quality_passed"] = True
            return state
        
        chunks = state.get("chunks", [])
        if not chunks:
            state["quality_passed"] = True
            return state
        
        min_score = cfg.get("min_quality_score", self.MIN_QUALITY_SCORE)
        enable_dedup = cfg.get("enable_dedup", True)
        enable_pii = cfg.get("enable_pii_filter", False)
        
        filtered_chunks = []
        removed_count = 0
        seen_hashes = set()
        
        for chunk in chunks:
            content = chunk.get("content", "")
            
            # 1. Check minimum length
            if len(content.strip()) < self.MIN_CONTENT_LENGTH:
                removed_count += 1
                continue
            
            # 2. Calculate quality score
            quality_score = self._calculate_quality_score(content)
            chunk["metadata"]["quality_score"] = quality_score
            
            if quality_score < min_score:
                removed_count += 1
                continue
            
            # 3. Deduplication
            if enable_dedup:
                content_hash = self._content_hash(content)
                if content_hash in seen_hashes:
                    removed_count += 1
                    continue
                seen_hashes.add(content_hash)
            
            # 4. PII filtering (basic)
            if enable_pii:
                content, pii_found = self._filter_pii(content)
                chunk["content"] = content
                chunk["metadata"]["pii_filtered"] = pii_found
            
            filtered_chunks.append(chunk)
        
        state["chunks"] = filtered_chunks
        state["quality_metrics"] = {
            "original_count": len(chunks),
            "filtered_count": len(filtered_chunks),
            "removed_count": removed_count,
            "dedup_enabled": enable_dedup,
        }
        state["quality_passed"] = len(filtered_chunks) > 0
        
        # Log quality issues
        if removed_count > 0:
            if "progress" not in state:
                state["progress"] = {}
            state["progress"]["quality_filtered"] = removed_count
        
        return state
    
    def _calculate_quality_score(self, content: str) -> float:
        """Calculate content quality score (0-1)."""
        if not content:
            return 0.0
        
        score = 1.0
        
        # Penalize very short content
        if len(content) < 50:
            score *= 0.7
        
        # Penalize content with high special character ratio
        special_chars = sum(1 for c in content if not c.isalnum() and not c.isspace())
        if len(content) > 0:
            special_ratio = special_chars / len(content)
            if special_ratio > 0.3:
                score *= 0.6
        
        # Penalize content with many repeated characters
        if len(content) > 10:
            repeated = max(content.count(c * 3) for c in set(content[:100]))
            if repeated > 3:
                score *= 0.5
        
        # Penalize content with low word diversity
        words = content.split()
        if len(words) > 5:
            unique_ratio = len(set(words)) / len(words)
            if unique_ratio < 0.3:
                score *= 0.7
        
        return max(0.0, min(1.0, score))
    
    def _content_hash(self, content: str) -> str:
        """Generate hash for deduplication."""
        import hashlib
        # Normalize whitespace
        normalized = " ".join(content.split())
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]
    
    def _filter_pii(self, content: str) -> tuple[str, bool]:
        """Basic PII filtering (phone numbers, emails, ID numbers)."""
        import re
        
        pii_found = False
        
        # Email pattern
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        if re.search(email_pattern, content):
            content = re.sub(email_pattern, "[EMAIL]", content)
            pii_found = True
        
        # Phone pattern (Chinese)
        phone_pattern = r'\b1[3-9]\d{9}\b'
        if re.search(phone_pattern, content):
            content = re.sub(phone_pattern, "[PHONE]", content)
            pii_found = True
        
        # ID number pattern (Chinese 18-digit)
        id_pattern = r'\b\d{17}[\dXx]\b'
        if re.search(id_pattern, content):
            content = re.sub(id_pattern, "[ID_NUMBER]", content)
            pii_found = True
        
        return content, pii_found
