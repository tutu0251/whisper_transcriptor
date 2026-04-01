#!/usr/bin/env python3
"""Test improvement by comparing before/after corrections"""

import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent))

from src.learning.database_manager import DatabaseManager

def main():
    print("=" * 60)
    print("🎯 MODEL IMPROVEMENT TEST")
    print("=" * 60)
    
    db = DatabaseManager()
    
    # Get all corrections
    from sqlite3 import connect
    conn = connect(db.db_path)
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    
    cursor = conn.execute("""
        SELECT original_text, corrected_text, confidence, created_at 
        FROM corrections 
        WHERE used_for_training = 1 
        ORDER BY created_at DESC
    """)
    corrections = cursor.fetchall()
    conn.close()
    
    if not corrections:
        print("\n❌ No trained corrections found. Make some edits first!")
        return
    
    print(f"\n📝 Found {len(corrections)} trained corrections:\n")
    
    for i, corr in enumerate(corrections[:10], 1):
        original = corr['original_text']
        corrected = corr['corrected_text']
        conf = corr['confidence']
        
        print(f"Correction {i}:")
        print(f"   Before: {original}")
        print(f"   After:  {corrected}")
        print(f"   Confidence: {conf:.2f}")
        print()
    
    print("=" * 60)
    print("💡 HOW TO MEASURE IMPROVEMENT:")
    print("=" * 60)
    print("1. Load the same audio file again")
    print("2. Play the sections where you made corrections")
    print("3. Compare new transcription to your corrected text")
    print("4. Look for the corrected words to appear correctly")
    print()
    print("Example:")
    print("   Before training: 'is category. We remain strong.'")
    print("   After training:  'This category. We remain strong.'")
    print()
    print("✅ The model should now output the corrected version!")

if __name__ == "__main__":
    main()