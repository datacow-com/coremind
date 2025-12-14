"""Performance metrics collection and calculation.

Provides utilities for collecting timing data and calculating
performance metrics like QPS, P95 latency, and throughput.
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PerformanceMetrics:
    """Performance test metrics.
    
    Attributes:
        qps: Queries per second.
        p95_latency_ms: 95th percentile latency in milliseconds.
        peak_memory_mb: Peak memory usage in MB.
        duration_s: Total duration in seconds.
        cache_hit_rate: Cache hit rate (0.0-1.0), if applicable.
        throughput_mb_s: Throughput in MB/s, if applicable.
        total_requests: Total number of requests processed.
        successful_requests: Number of successful requests.
        failed_requests: Number of failed requests.
    """
    qps: float
    p95_latency_ms: float
    peak_memory_mb: float
    duration_s: float
    cache_hit_rate: Optional[float] = None
    throughput_mb_s: Optional[float] = None
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


@dataclass
class MetricsCollector:
    """Collect and calculate performance metrics.
    
    Records individual operation latencies and calculates
    aggregate statistics like QPS and percentile latencies.
    
    Example:
        collector = MetricsCollector()
        collector.start()
        for _ in range(100):
            with collector.measure():
                # ... perform operation ...
        metrics = collector.get_metrics(peak_memory_mb=150.0)
    """
    
    _latencies: List[float] = field(default_factory=list)
    _start_time: Optional[float] = None
    _end_time: Optional[float] = None
    _cache_hits: int = 0
    _cache_misses: int = 0
    _bytes_processed: int = 0
    _successful: int = 0
    _failed: int = 0

    def start(self) -> None:
        """Start metrics collection."""
        self._start_time = time.perf_counter()
        self._latencies = []
        self._cache_hits = 0
        self._cache_misses = 0
        self._bytes_processed = 0
        self._successful = 0
        self._failed = 0

    def stop(self) -> None:
        """Stop metrics collection."""
        self._end_time = time.perf_counter()

    def record_latency(self, latency_s: float, success: bool = True) -> None:
        """Record a single operation latency.
        
        Args:
            latency_s: Operation latency in seconds.
            success: Whether the operation succeeded.
        """
        self._latencies.append(latency_s)
        if success:
            self._successful += 1
        else:
            self._failed += 1

    def record_cache_access(self, hit: bool) -> None:
        """Record a cache access.
        
        Args:
            hit: Whether the cache was hit.
        """
        if hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def record_bytes(self, bytes_count: int) -> None:
        """Record bytes processed.
        
        Args:
            bytes_count: Number of bytes processed.
        """
        self._bytes_processed += bytes_count

    class _LatencyContext:
        """Context manager for measuring operation latency."""
        
        def __init__(self, collector: "MetricsCollector") -> None:
            self._collector = collector
            self._start: float = 0.0
            self._success = True

        def __enter__(self) -> "_LatencyContext":
            self._start = time.perf_counter()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb) -> None:
            latency = time.perf_counter() - self._start
            self._success = exc_type is None
            self._collector.record_latency(latency, self._success)

        def mark_failed(self) -> None:
            """Mark this operation as failed."""
            self._success = False

    def measure(self) -> _LatencyContext:
        """Context manager for measuring operation latency.
        
        Returns:
            Context manager that records latency on exit.
        """
        return self._LatencyContext(self)

    def calculate_qps(self) -> float:
        """Calculate queries per second.
        
        Returns:
            QPS based on total requests and duration.
        """
        if self._start_time is None:
            return 0.0
        
        end = self._end_time or time.perf_counter()
        duration = end - self._start_time
        
        if duration <= 0:
            return 0.0
        
        return len(self._latencies) / duration

    def calculate_p95_latency_ms(self) -> float:
        """Calculate 95th percentile latency in milliseconds.
        
        Returns:
            P95 latency in ms, or 0.0 if no data.
        """
        if not self._latencies:
            return 0.0
        
        sorted_latencies = sorted(self._latencies)
        idx = int(len(sorted_latencies) * 0.95)
        idx = min(idx, len(sorted_latencies) - 1)
        
        return sorted_latencies[idx] * 1000  # Convert to ms

    def calculate_throughput_mb_s(self) -> Optional[float]:
        """Calculate throughput in MB/s.
        
        Returns:
            Throughput in MB/s, or None if no bytes recorded.
        """
        if self._bytes_processed == 0:
            return None
        
        if self._start_time is None:
            return None
        
        end = self._end_time or time.perf_counter()
        duration = end - self._start_time
        
        if duration <= 0:
            return None
        
        return (self._bytes_processed / (1024 * 1024)) / duration

    def calculate_cache_hit_rate(self) -> Optional[float]:
        """Calculate cache hit rate.
        
        Returns:
            Hit rate (0.0-1.0), or None if no cache accesses.
        """
        total = self._cache_hits + self._cache_misses
        if total == 0:
            return None
        return self._cache_hits / total

    def get_duration(self) -> float:
        """Get total collection duration in seconds.
        
        Returns:
            Duration in seconds.
        """
        if self._start_time is None:
            return 0.0
        
        end = self._end_time or time.perf_counter()
        return end - self._start_time

    def get_metrics(self, peak_memory_mb: float = 0.0) -> PerformanceMetrics:
        """Get aggregated performance metrics.
        
        Args:
            peak_memory_mb: Peak memory usage to include in metrics.
            
        Returns:
            PerformanceMetrics with all calculated values.
        """
        return PerformanceMetrics(
            qps=self.calculate_qps(),
            p95_latency_ms=self.calculate_p95_latency_ms(),
            peak_memory_mb=peak_memory_mb,
            duration_s=self.get_duration(),
            cache_hit_rate=self.calculate_cache_hit_rate(),
            throughput_mb_s=self.calculate_throughput_mb_s(),
            total_requests=len(self._latencies),
            successful_requests=self._successful,
            failed_requests=self._failed,
        )

    def get_latency_stats(self) -> dict:
        """Get detailed latency statistics.
        
        Returns:
            Dictionary with min, max, mean, median, p50, p90, p95, p99 latencies.
        """
        if not self._latencies:
            return {}
        
        sorted_latencies = sorted(self._latencies)
        n = len(sorted_latencies)
        
        def percentile(p: float) -> float:
            idx = int(n * p)
            idx = min(idx, n - 1)
            return sorted_latencies[idx] * 1000  # ms
        
        return {
            "min_ms": min(self._latencies) * 1000,
            "max_ms": max(self._latencies) * 1000,
            "mean_ms": statistics.mean(self._latencies) * 1000,
            "median_ms": statistics.median(self._latencies) * 1000,
            "p50_ms": percentile(0.50),
            "p90_ms": percentile(0.90),
            "p95_ms": percentile(0.95),
            "p99_ms": percentile(0.99),
        }
