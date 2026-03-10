"""
PROJECT MNEMOSYNE v1.0 - The Living Memory Architecture
Primary Author: Autonomous Architect
Date: 2024-01-15
Version: 1.0.0

OVERVIEW:
A dual-layer persistent memory system with zero data loss guarantee.
Implements active learning, salience decay, and real-time synchronization.

ARCHITECTURAL PRINCIPLES:
1. Memory as Experience, Not Data
2. Active Learning from Day One
3. Durability Before Convenience
4. Query-First Architecture
"""

__version__ = "1.0.0"
__author__ = "Evolution Ecosystem - Autonomous Architect"

from .core import MemorySystem
from .models import Memory, MemoryType, EmotionalState
from .exceptions import (
    MemorySystemError,
    StorageError,
    SyncError,
    ValidationError,
    MemoryNotFoundError
)

__all__ = [
    'MemorySystem',
    'Memory',
    'MemoryType',
    'EmotionalState',
    'MemorySystemError',
    'StorageError',
    'SyncError',
    'ValidationError',
    'MemoryNotFoundError'
]