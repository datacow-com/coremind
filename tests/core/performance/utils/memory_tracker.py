"""Memory tracking utility for performance testing.

Uses psutil to track process memory usage during test execution,
providing peak memory measurements for validating memory constraints.
"""

import threading
import time
from typing import Optional

import psutil


class MemoryTracker:
    """Track memory usage during test execution.
    
    Uses a background thread to sample memory usage at regular intervals,
    tracking both current and peak memory consumption.
    
    Example:
        tracker = MemoryTracker()
        tracker.start()
        # ... perform operations ...
        peak_mb = tracker.stop()
        print(f"Peak memory: {peak_mb:.2f} MB")
    """

    def __init__(self, sample_interval: float = 0.1) -> None:
        """Initialize MemoryTracker.
        
        Args:
            sample_interval: Time between memory samples in seconds.
        """
        self._sample_interval = sample_interval
        self._process = psutil.Process()
        self._peak_memory: float = 0.0
        self._baseline_memory: float = 0.0
        self._tracking = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def _get_memory_mb(self) -> float:
        """Get current process memory usage in MB."""
        return self._process.memory_info().rss / (1024 * 1024)

    def _tracking_loop(self) -> None:
        """Background thread loop for sampling memory."""
        while self._tracking:
            current = self._get_memory_mb()
            with self._lock:
                if current > self._peak_memory:
                    self._peak_memory = current
            time.sleep(self._sample_interval)

    def start(self) -> None:
        """Start memory tracking.
        
        Records baseline memory and starts background sampling thread.
        """
        self._baseline_memory = self._get_memory_mb()
        self._peak_memory = self._baseline_memory
        self._tracking = True
        self._thread = threading.Thread(target=self._tracking_loop, daemon=True)
        self._thread.start()

    def stop(self) -> float:
        """Stop tracking and return peak memory (MB).
        
        Returns:
            Peak memory usage in MB during tracking period.
        """
        self._tracking = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        
        # Final sample
        current = self._get_memory_mb()
        with self._lock:
            if current > self._peak_memory:
                self._peak_memory = current
        
        return self._peak_memory

    def get_current(self) -> float:
        """Get current memory usage (MB).
        
        Returns:
            Current memory usage in MB.
        """
        return self._get_memory_mb()

    def get_peak(self) -> float:
        """Get peak memory usage (MB).
        
        Returns:
            Peak memory usage in MB since tracking started.
        """
        with self._lock:
            return self._peak_memory

    def get_delta(self) -> float:
        """Get memory increase from baseline (MB).
        
        Returns:
            Memory increase from baseline in MB.
        """
        with self._lock:
            return self._peak_memory - self._baseline_memory

    def reset(self) -> None:
        """Reset tracker state."""
        if self._tracking:
            self.stop()
        self._peak_memory = 0.0
        self._baseline_memory = 0.0
