# test_training.py
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.learning.database_manager import DatabaseManager
from src.learning.correction_collector import CorrectionCollector

# Test database
db = DatabaseManager()
print(f"Database path: {db.db_path}")

# Check statistics
stats = db.get_statistics()
print(f"Statistics: {stats}")

# Test adding a correction
correction_data = {
    "audio_hash": "test_hash_123",
    "original_text": "test original",
    "corrected_text": "test corrected",
    "confidence": 0.5,
    "language": "en",
    "file_path": "test.mp3",
    "start_time": 0,
    "end_time": 3
}

try:
    correction_id = db.add_correction(correction_data)
    print(f"✅ Added correction with ID: {correction_id}")
except Exception as e:
    print(f"❌ Error adding correction: {e}")

# Check pending corrections
pending = db.get_pending_corrections()
print(f"Pending corrections: {len(pending)}")