"""
Data models for PROJECT MNEMOSYNE memory system.
Uses Pydantic for validation and type safety.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
from pydantic import BaseModel, Field, validator, confloat
import uuid
import hashlib
import json


class MemoryType(str, Enum):
    """Types of memories the system can store."""
    STRATEGIC = "strategic"
    EMOTIONAL = "emotional"
    OUTCOME = "outcome"
    OBSERVATION = "observation"
    INSIGHT = "insight"
    FAILURE = "failure"
    SUCCESS = "success"


class EmotionalState(BaseModel):
    """Emotional context for memories."""
    valence: confloat(ge=-1.0, le=1.0) = Field(
        default=0.0,
        description="Emotional valence from -1 (negative) to 1 (positive)"
    )
    arousal: confloat(ge=0.0, le=1.0) = Field(
        default=0.5,
        description="Arousal level from 0 (calm) to 1 (excited)"
    )
    dominant_emotion: str = Field(
        default="neutral",
        description="Primary emotional state"
    )
    
    @validator('dominant_emotion')
    def validate_emotion(cls, v):
        valid_emotions = [
            'curiosity', 'frustration', 'satisfaction', 'confusion',
            'excitement', 'neutral', 'determination', 'surprise'
        ]
        if v.lower() not in valid_emotions:
            raise ValueError(f"Emotion must be one of {valid_emotions}")
        return v.lower()


class Memory(BaseModel):
    """Primary memory model following Firestore document structure."""
    id: str = Field(
        default_factory=lambda: f"mem_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    session_id: str = Field(
        ...,
        description="ID of the session that generated this memory",
        min_length=10
    )
    memory_type: List[MemoryType] = Field(
        ...,
        description="One or more memory types",
        min_items=1
    )
    content: str = Field(
        ...,
        description="The memory content",
        min_length=10,
        max_length=5000
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Searchable tags for retrieval"
    )
    
    # Dynamic learning fields
    salience: confloat(ge=0.0, le=1.0) = Field(
        default=1.0,
        description="Importance weight that decays over time"
    )
    references: List[str] = Field(
        default_factory=list,
        description="Links to related memory IDs"
    )
    contradicts: List[str] = Field(
        default_factory=list,
        description="Contradictory memory IDs"
    )
    superseded_by: Optional[str] = Field(
        default=None,
        description="If this memory is outdated by a newer one"
    )
    
    # Emotional context
    emotional_state: Optional[EmotionalState] = Field(
        default=None,
        description="Emotional state at memory creation"
    )
    
    # Provenance
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    version: int = Field(default=1)
    provenance_hash: Optional[str] = Field(
        default=None,
        description="SHA-256 hash for integrity verification"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            MemoryType: lambda v: v.value
        }
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of memory content for integrity."""
        hash_data = {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'content': self.content,
            'version': self.version
        }
        return hashlib.sha256(
            json.dumps(hash_data, sort_keys=True).encode()
        ).hexdigest()
    
    @validator('references', 'contradicts')
    def validate_memory_ids(cls, v):
        """Validate that referenced memory IDs follow our format."""
        for memory_id in v:
            if not memory_id.startswith('mem_'):
                raise ValueError(f"Invalid memory ID format: {memory_id}")
        return v
    
    @validator('tags')
    def normalize_tags(cls, v):
        """Normalize tags to lowercase and remove duplicates."""
        normalized = [tag.strip().lower() for tag in v if tag.strip()]
        return list(set(normalized))