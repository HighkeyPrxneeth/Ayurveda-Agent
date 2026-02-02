"""
Dosha Trend Tracking Service

Tracks Dosha assessments over time to enable trend visualization
and long-term health pattern analysis.
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from threading import Lock

logger = logging.getLogger(__name__)

# Storage directory for Dosha history
STORAGE_DIR = Path(__file__).parent.parent.parent / "data"


@dataclass
class DoshaEntry:
    """A single Dosha assessment entry with timestamp."""
    timestamp: str
    vata: float
    pitta: float
    kapha: float
    dominant_dosha: str
    constitution_type: str
    source: str = "questionnaire"  # 'questionnaire' or 'vitals'
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "DoshaEntry":
        return cls(**data)


class DoshaTracker:
    """
    Service for tracking Dosha assessments over time.
    
    Features:
    - Persistent storage (JSON file per user)
    - Thread-safe operations
    - Trend analysis helpers
    """
    
    def __init__(self, storage_dir: Optional[Path] = None):
        self._storage_dir = storage_dir or STORAGE_DIR
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, Lock] = {}
        self._global_lock = Lock()
        logger.info("DoshaTracker initialized with storage: %s", self._storage_dir)
    
    def _get_lock(self, user_id: str) -> Lock:
        """Get or create a lock for a specific user."""
        with self._global_lock:
            if user_id not in self._locks:
                self._locks[user_id] = Lock()
            return self._locks[user_id]
    
    def _get_user_file(self, user_id: str) -> Path:
        """Get the file path for a user's Dosha history."""
        safe_id = "".join(c for c in user_id if c.isalnum() or c in "-_")[:50]
        return self._storage_dir / f"dosha_history_{safe_id}.json"
    
    def track_assessment(
        self,
        user_id: str,
        vata: float,
        pitta: float,
        kapha: float,
        dominant_dosha: str,
        constitution_type: str,
        source: str = "questionnaire"
    ) -> DoshaEntry:
        """
        Record a new Dosha assessment for a user.
        
        Returns the created entry.
        """
        entry = DoshaEntry(
            timestamp=datetime.now().isoformat(),
            vata=vata,
            pitta=pitta,
            kapha=kapha,
            dominant_dosha=dominant_dosha,
            constitution_type=constitution_type,
            source=source
        )
        
        lock = self._get_lock(user_id)
        with lock:
            file_path = self._get_user_file(user_id)
            history = self._load_history(file_path)
            history.append(entry.to_dict())
            self._save_history(file_path, history)
        
        logger.info("Tracked Dosha assessment for user %s: %s", user_id, dominant_dosha)
        return entry
    
    def get_history(
        self,
        user_id: str,
        limit: Optional[int] = None
    ) -> list[DoshaEntry]:
        """
        Get Dosha assessment history for a user.
        
        Args:
            user_id: User identifier
            limit: Maximum number of entries to return (newest first)
        """
        lock = self._get_lock(user_id)
        with lock:
            file_path = self._get_user_file(user_id)
            history = self._load_history(file_path)
        
        entries = [DoshaEntry.from_dict(h) for h in history]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        
        if limit:
            entries = entries[:limit]
        
        return entries
    
    def get_trend_data(self, user_id: str, limit: int = 30) -> dict:
        """
        Get formatted trend data for visualization.
        
        Returns data suitable for chart rendering.
        """
        entries = self.get_history(user_id, limit)
        entries.reverse()  # Oldest first for charts
        
        return {
            "labels": [e.timestamp[:10] for e in entries],  # Date only
            "vata": [e.vata for e in entries],
            "pitta": [e.pitta for e in entries],
            "kapha": [e.kapha for e in entries],
            "dominant": [e.dominant_dosha for e in entries],
            "count": len(entries)
        }
    
    def clear_history(self, user_id: str) -> int:
        """Clear all history for a user. Returns count of deleted entries."""
        lock = self._get_lock(user_id)
        with lock:
            file_path = self._get_user_file(user_id)
            history = self._load_history(file_path)
            count = len(history)
            if file_path.exists():
                file_path.unlink()
        
        logger.info("Cleared %d entries for user %s", count, user_id)
        return count
    
    def _load_history(self, file_path: Path) -> list[dict]:
        """Load history from file."""
        if not file_path.exists():
            return []
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning("Failed to load history from %s: %s", file_path, e)
            return []
    
    def _save_history(self, file_path: Path, history: list[dict]) -> None:
        """Save history to file."""
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)


# Singleton instance
_dosha_tracker: Optional[DoshaTracker] = None


def get_dosha_tracker() -> DoshaTracker:
    """Get or create the singleton tracker instance."""
    global _dosha_tracker
    if _dosha_tracker is None:
        _dosha_tracker = DoshaTracker()
    return _dosha_tracker

