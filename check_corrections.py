#!/usr/bin/env python3
"""Check corrections in database"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.learning.database_manager import DatabaseManager

db = DatabaseManager()
stats = db.get_statistics()
print("=" * 50)
print("DATABASE STATISTICS")
print("=" * 50)
print(f"Total Corrections:   {stats.get('total_corrections', 0)}")
print(f"Pending Corrections: {stats.get('pending_corrections', 0)}")
print(f"Trained Corrections: {stats.get('trained_corrections', 0)}")
print(f"Vocabulary Size:     {stats.get('vocabulary_size', 0)}")
print(f"Training Sessions:   {stats.get('training_sessions', 0)}")
print("=" * 50)

# Show recent corrections
pending = db.get_pending_corrections(limit=10)
print(f"\nRecent Pending Corrections ({len(pending)}):")
for i, corr in enumerate(pending[:5]):
    print(f"  {i+1}. {corr['original_text'][:40]} -> {corr['corrected_text'][:40]}")