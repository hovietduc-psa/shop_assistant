"""
LangGraph SQLite checkpointing for persistent state management.
Phase 3 feature: Replace memory-based checkpointing with SQLite storage.
"""

import json
import time
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path
from loguru import logger

from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.memory import MemorySaver


class SQLiteCheckpointSaver(BaseCheckpointSaver):
    """
    SQLite-based checkpoint saver for LangGraph state persistence.

    Phase 3 implementation that replaces memory-based checkpointing with
    persistent SQLite storage for production-ready state management.
    """

    def __init__(self, db_path: str = "langgraph_checkpoints.db"):
        """
        Initialize SQLite checkpoint saver.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database with required tables."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoints (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        checkpoint_data TEXT NOT NULL,
                        metadata TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(thread_id, checkpoint_id)
                    )
                """)

                conn.execute("""
                    CREATE TABLE IF NOT EXISTS checkpoint_writes (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        thread_id TEXT NOT NULL,
                        checkpoint_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create indexes for performance
                conn.execute("CREATE INDEX IF NOT EXISTS idx_thread_id ON checkpoints(thread_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread ON checkpoint_writes(thread_id)")

                conn.commit()
                logger.info(f"SQLite checkpoint database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Failed to initialize SQLite checkpoint database: {e}")
            raise

    async def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> Dict[str, Any]:
        """
        Save a checkpoint to SQLite storage.

        Args:
            config: Configuration containing thread_id
            checkpoint: Checkpoint data to save
            metadata: Checkpoint metadata

        Returns:
            Updated configuration
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = f"checkpoint_{int(time.time() * 1000000)}"

        try:
            checkpoint_data = {
                "id": checkpoint_id,
                "ts": checkpoint.ts,
                "channel_values": checkpoint.channel_values,
                "channel_versions": checkpoint.channel_versions,
                "versions_seen": checkpoint.versions_seen
            }

            metadata_data = {
                "source": metadata.get("source", "unknown"),
                "step": metadata.get("step", 0),
                "writes": metadata.get("writes", [])
            }

            await asyncio.get_event_loop().run_in_executor(
                None,
                self._save_checkpoint,
                thread_id,
                checkpoint_id,
                json.dumps(checkpoint_data),
                json.dumps(metadata_data)
            )

            logger.debug(f"Saved checkpoint {checkpoint_id} for thread {thread_id}")
            return {
                **config,
                "configurable": {
                    **config.get("configurable", {}),
                    "thread_id": thread_id,
                    "checkpoint_id": checkpoint_id
                }
            }

        except Exception as e:
            logger.error(f"Failed to save checkpoint: {e}")
            # Fallback to memory saver
            return await MemorySaver().put(config, checkpoint, metadata)

    def _save_checkpoint(self, thread_id: str, checkpoint_id: str, checkpoint_data: str, metadata_data: str):
        """Save checkpoint data to SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints
                (thread_id, checkpoint_id, checkpoint_data, metadata)
                VALUES (?, ?, ?, ?)
            """, (thread_id, checkpoint_id, checkpoint_data, metadata_data))
            conn.commit()

    async def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """
        Retrieve a checkpoint from SQLite storage.

        Args:
            config: Configuration containing thread_id and checkpoint_id

        Returns:
            Checkpoint data or None if not found
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id")

        if not checkpoint_id:
            # Get latest checkpoint for thread
            checkpoint_id = await self._get_latest_checkpoint_id(thread_id)

        if not checkpoint_id:
            return None

        try:
            checkpoint_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._load_checkpoint,
                thread_id,
                checkpoint_id
            )

            if checkpoint_data:
                data = json.loads(checkpoint_data)
                return Checkpoint(
                    ts=data["ts"],
                    channel_values=data["channel_values"],
                    channel_versions=data["channel_versions"],
                    versions_seen=data["versions_seen"]
                )
            return None

        except Exception as e:
            logger.error(f"Failed to load checkpoint: {e}")
            return None

    def _load_checkpoint(self, thread_id: str, checkpoint_id: str) -> Optional[str]:
        """Load checkpoint data from SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT checkpoint_data FROM checkpoints
                WHERE thread_id = ? AND checkpoint_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (thread_id, checkpoint_id))

            result = cursor.fetchone()
            return result[0] if result else None

    async def _get_latest_checkpoint_id(self, thread_id: str) -> Optional[str]:
        """Get the latest checkpoint ID for a thread."""
        try:
            checkpoint_id = await asyncio.get_event_loop().run_in_executor(
                None,
                self._load_latest_checkpoint_id,
                thread_id
            )
            return checkpoint_id
        except Exception as e:
            logger.error(f"Failed to get latest checkpoint ID: {e}")
            return None

    def _load_latest_checkpoint_id(self, thread_id: str) -> Optional[str]:
        """Load latest checkpoint ID from SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT checkpoint_id FROM checkpoints
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT 1
            """, (thread_id,))

            result = cursor.fetchone()
            return result[0] if result else None

    async def list(self, config: Dict[str, Any], *, limit: int = 10) -> List[Checkpoint]:
        """
        List checkpoints for a thread.

        Args:
            config: Configuration containing thread_id
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoints
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")

        try:
            checkpoints_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._list_checkpoints,
                thread_id,
                limit
            )

            checkpoints = []
            for checkpoint_data in checkpoints_data:
                data = json.loads(checkpoint_data["checkpoint_data"])
                checkpoints.append(Checkpoint(
                    ts=data["ts"],
                    channel_values=data["channel_values"],
                    channel_versions=data["channel_versions"],
                    versions_seen=data["versions_seen"]
                ))

            return checkpoints

        except Exception as e:
            logger.error(f"Failed to list checkpoints: {e}")
            return []

    def _list_checkpoints(self, thread_id: str, limit: int) -> List[Dict[str, str]]:
        """List checkpoints from SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT checkpoint_id, checkpoint_data, created_at
                FROM checkpoints
                WHERE thread_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (thread_id, limit))

            return [
                {
                    "checkpoint_id": row[0],
                    "checkpoint_data": row[1],
                    "created_at": row[2]
                }
                for row in cursor.fetchall()
            ]

    async def put_writes(self, config: Dict[str, Any], writes: List[Any], task_id: str):
        """
        Save writes to SQLite storage.

        Args:
            config: Configuration containing thread_id and checkpoint_id
            writes: List of writes to save
            task_id: Task identifier
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id", "unknown")

        try:
            for write in writes:
                write_data = json.dumps(write) if not isinstance(write, str) else write
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self._save_write,
                    thread_id,
                    checkpoint_id,
                    task_id,
                    write_data
                )

            logger.debug(f"Saved {len(writes)} writes for checkpoint {checkpoint_id}")

        except Exception as e:
            logger.error(f"Failed to save writes: {e}")

    def _save_write(self, thread_id: str, checkpoint_id: str, task_id: str, write_data: str):
        """Save write data to SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO checkpoint_writes
                (thread_id, checkpoint_id, task_id, data)
                VALUES (?, ?, ?, ?)
            """, (thread_id, checkpoint_id, task_id, write_data))
            conn.commit()

    async def get_writes(self, config: Dict[str, Any]) -> List[Any]:
        """
        Retrieve writes from SQLite storage.

        Args:
            config: Configuration containing thread_id and checkpoint_id

        Returns:
            List of writes
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        checkpoint_id = config.get("configurable", {}).get("checkpoint_id", "unknown")

        try:
            writes_data = await asyncio.get_event_loop().run_in_executor(
                None,
                self._load_writes,
                thread_id,
                checkpoint_id
            )

            writes = []
            for write_data in writes_data:
                try:
                    # Try to parse as JSON first
                    write = json.loads(write_data["data"])
                except json.JSONDecodeError:
                    # If not JSON, use as string
                    write = write_data["data"]
                writes.append(write)

            return writes

        except Exception as e:
            logger.error(f"Failed to load writes: {e}")
            return []

    def _load_writes(self, thread_id: str, checkpoint_id: str) -> List[Dict[str, str]]:
        """Load writes from SQLite (sync operation for thread pool)."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT task_id, data, created_at
                FROM checkpoint_writes
                WHERE thread_id = ? AND checkpoint_id = ?
                ORDER BY created_at ASC
            """, (thread_id, checkpoint_id))

            return [
                {
                    "task_id": row[0],
                    "data": row[1],
                    "created_at": row[2]
                }
                for row in cursor.fetchall()
            ]

    def cleanup_old_checkpoints(self, days_old: int = 30):
        """
        Clean up old checkpoints to prevent database bloat.

        Args:
            days_old: Age in days of checkpoints to delete
        """
        try:
            cutoff_date = datetime.now().timestamp() - (days_old * 24 * 60 * 60)

            with sqlite3.connect(self.db_path) as conn:
                # Delete old checkpoints
                cursor = conn.execute("""
                    DELETE FROM checkpoints
                    WHERE created_at < datetime(?, 'unixepoch')
                """, (cutoff_date,))

                deleted_checkpoints = cursor.rowcount

                # Delete associated writes
                cursor = conn.execute("""
                    DELETE FROM checkpoint_writes
                    WHERE checkpoint_id NOT IN (
                        SELECT DISTINCT checkpoint_id FROM checkpoints
                    )
                """)

                deleted_writes = cursor.rowcount
                conn.commit()

                logger.info(f"Cleaned up {deleted_checkpoints} old checkpoints and {deleted_writes} writes")

        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {e}")

    def get_database_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the checkpoint database.

        Returns:
            Database statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Get checkpoint count
                cursor = conn.execute("SELECT COUNT(*) FROM checkpoints")
                checkpoint_count = cursor.fetchone()[0]

                # Get write count
                cursor = conn.execute("SELECT COUNT(*) FROM checkpoint_writes")
                write_count = cursor.fetchone()[0]

                # Get unique threads
                cursor = conn.execute("SELECT COUNT(DISTINCT thread_id) FROM checkpoints")
                thread_count = cursor.fetchone()[0]

                # Get database size
                db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

                return {
                    "checkpoint_count": checkpoint_count,
                    "write_count": write_count,
                    "thread_count": thread_count,
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / (1024 * 1024), 2),
                    "database_path": str(self.db_path)
                }

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {
                "error": str(e),
                "checkpoint_count": 0,
                "write_count": 0,
                "thread_count": 0,
                "database_size_bytes": 0,
                "database_size_mb": 0
            }


class HybridCheckpointSaver:
    """
    Hybrid checkpoint saver that uses SQLite for persistence and memory for speed.

    Phase 3 implementation that provides the best of both worlds:
    - Fast access using in-memory cache
    - Persistent storage using SQLite
    - Automatic synchronization between cache and storage
    """

    def __init__(self, db_path: str = "langgraph_checkpoints.db", cache_size: int = 1000):
        """
        Initialize hybrid checkpoint saver.

        Args:
            db_path: Path to SQLite database file
            cache_size: Maximum number of checkpoints to keep in memory
        """
        self.sqlite_saver = SQLiteCheckpointSaver(db_path)
        self.memory_saver = MemorySaver()
        self.cache_size = cache_size
        self._cache_hits = 0
        self._cache_misses = 0

    async def put(self, config: Dict[str, Any], checkpoint: Checkpoint, metadata: CheckpointMetadata) -> Dict[str, Any]:
        """Save to both memory and SQLite."""
        # Save to memory first (fast)
        memory_config = await self.memory_saver.put(config, checkpoint, metadata)

        # Save to SQLite (persistent)
        sqlite_config = await self.sqlite_saver.put(config, checkpoint, metadata)

        return sqlite_config

    async def get(self, config: Dict[str, Any]) -> Optional[Checkpoint]:
        """Get from memory cache first, fallback to SQLite."""
        # Try memory cache first
        checkpoint = await self.memory_saver.get(config)

        if checkpoint:
            self._cache_hits += 1
            return checkpoint

        # Fallback to SQLite
        checkpoint = await self.sqlite_saver.get(config)

        if checkpoint:
            self._cache_misses += 1
            # Cache for future use
            await self.memory_saver.put(config, checkpoint, CheckpointMetadata(source="sqlite"))

        return checkpoint

    async def list(self, config: Dict[str, Any], *, limit: int = 10) -> List[Checkpoint]:
        """List from SQLite (authoritative source)."""
        return await self.sqlite_saver.list(config, limit=limit)

    async def put_writes(self, config: Dict[str, Any], writes: List[Any], task_id: str):
        """Save writes to SQLite."""
        await self.sqlite_saver.put_writes(config, writes, task_id)

    async def get_writes(self, config: Dict[str, Any]) -> List[Any]:
        """Get writes from SQLite."""
        return await self.sqlite_saver.get_writes(config)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate_percent": round(hit_rate, 2),
            "total_requests": total_requests
        }

    def cleanup_memory_cache(self):
        """Clean up memory cache to prevent memory bloat."""
        # Simple cleanup - in a production system, you might implement LRU eviction
        self.memory_saver = MemorySaver()
        logger.info("Memory cache cleaned up")