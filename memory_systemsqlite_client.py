"""
SQLite client for local cache with immediate durability.
Implements atomic write-first strategy for zero data loss.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
import hashlib
import threading

from .models import Memory, MemoryType
from .exceptions import StorageError, ValidationError

logger = logging.getLogger(__name__)


class SQLiteMemoryStore:
    """Manages SQLite database for local memory storage."""
    
    def __init__(self, db_path: str = "./data/mnemosyne_memories.db"):
        """
        Initialize SQLite database connection.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local_lock = threading.RLock()  # For thread-safe operations
        
        logger.info(f"Initializing SQLite store at {self.db_path}")
        
        # Initialize database schema
        self._init_database()
    
    def _init_database(self) -> None:
        """Initialize database tables if they don't exist."""
        with self._local_lock:
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Main memories table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS memories (
                        id TEXT PRIMARY KEY,
                        timestamp TEXT NOT NULL,
                        session_id TEXT NOT NULL,
                        memory_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        tags TEXT,
                        salience REAL DEFAULT 1.0,
                        references TEXT,
                        contradicts TEXT,
                        superseded_by TEXT,
                        emotional_state TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        version INTEGER DEFAULT 1,
                        provenance_hash TEXT,
                        sync_status TEXT DEFAULT 'pending',
                        local_version INTEGER DEFAULT 1,
                        last_sync_attempt TEXT,
                        sync_error TEXT,
                        
                        CHECK (salience >= 0 AND salience <= 1),
                        CHECK (version >= 1)
                    )
                ''')
                
                # Indexes for faster queries
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_memories_timestamp 
                    ON memories(timestamp)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_memories_session 
                    ON memories(session_id)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_memories_sync 
                    ON memories(sync_status)
                ''')
                cursor.execute('''
                    CREATE INDEX IF NOT EXISTS idx_memories_tags 
                    ON memories(tags)
                ''')
                
                # Sync log table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS sync_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        memory_id TEXT NOT NULL,
                        action TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        status TEXT NOT NULL,
                        error_message TEXT,
                        FOREIGN KEY (memory_id) REFERENCES memories (id)
                    )
                ''')
                
                conn.commit()
                logger.info("Database schema initialized successfully")
                
            except sqlite3.Error as e:
                logger.error(f"Database initialization failed: {str(e)}")
                raise StorageError(f"Failed to initialize database: {str(e)}")
            finally:
                if 'conn' in locals():
                    conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a thread-safe database connection."""
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        return conn
    
    def save_memory(self, memory: Memory) -> str:
        """
        Save memory to SQLite with atomic write guarantee.
        
        Args:
            memory: Memory object to save
            
        Returns:
            Memory ID
            
        Raises:
            StorageError: If save operation fails
            ValidationError: If memory validation fails
        """
        with self._local_lock:
            conn = None
            try:
                # Validate memory
                if not memory.id.startswith('mem_'):
                    raise ValidationError(f"Invalid memory ID format: {memory.id}")
                
                # Calculate provenance hash
                memory.provenance_hash = memory.calculate_hash()
                
                # Prepare data for insertion
                memory_data = memory.dict()
                
                # Convert complex fields to JSON strings
                memory_data['memory_type'] = json.dumps([mt.value for mt in memory.memory_type])
                memory_data['tags'] = json.dumps(memory.tags)
                memory_data['references'] = json.dumps(memory.references)
                memory_data['contradicts'] = json.dumps(memory.contradicts)
                
                if memory.emotional_state:
                    memory_data['emotional_state'] = json.dumps(memory.emotional_state.dict())
                else:
                    memory_data['emotional_state'] = None
                
                # Convert datetime objects to ISO strings
                for field in ['timestamp', 'created_at', 'updated_at']:
                    if isinstance(memory_data[field], datetime):
                        memory_data[field] = memory_data[field].isoformat()
                
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Check if memory already exists (for versioning)
                cursor.execute(
                    "SELECT version FROM memories WHERE id = ?",
                    (memory.id,)
                )
                existing = cursor.fetchone()
                
                if existing:
                    # Update existing memory with version increment
                    new_version = existing['version'] + 1
                    memory_data['version'] = new_version
                    memory_data['updated_at'] = datetime.utcnow().isoformat()
                    
                    query = """
                        UPDATE memories SET
                            timestamp = ?,
                            session_id = ?,
                            memory_type = ?,
                            content = ?,
                            tags = ?,
                            salience = ?,
                            references = ?,
                            contradicts = ?,
                            superseded_by = ?,
                            emotional_state = ?,
                            updated_at = ?,
                            version = ?,
                            provenance_hash = ?,
                            sync_status = 'pending',
                            local_version = local_version + 1
                        WHERE id = ?
                    """
                    
                    params = (
                        memory_data['timestamp'],
                        memory_data['session_id'],
                        memory_data['memory_type'],
                        memory_data['content'],
                        memory