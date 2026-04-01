"""
Database Manager Module
SQLite database for continuous learning
"""

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class DatabaseManager:
    """SQLite database manager for corrections and training data"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            home = Path.home()
            app_data = home / ".transcriber"
            app_data.mkdir(exist_ok=True)
            db_path = app_data / "learning_data.db"
        
        self.db_path = str(db_path)
        print(f"📁 Database path: {self.db_path}")
        self.init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def init_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    audio_hash TEXT NOT NULL,
                    original_text TEXT NOT NULL,
                    corrected_text TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    language TEXT DEFAULT 'en',
                    file_path TEXT,
                    start_time REAL,
                    end_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    used_for_training BOOLEAN DEFAULT 0,
                    training_session_id INTEGER
                );
                
                CREATE TABLE IF NOT EXISTS training_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    end_time TIMESTAMP,
                    corrections_count INTEGER DEFAULT 0,
                    old_model_version TEXT,
                    new_model_version TEXT,
                    wer_before REAL,
                    wer_after REAL,
                    status TEXT DEFAULT 'pending'
                );
                
                CREATE TABLE IF NOT EXISTS model_versions (
                    version TEXT PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    base_model TEXT NOT NULL,
                    corrections_trained INTEGER DEFAULT 0,
                    file_path TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 0,
                    wer_score REAL
                );
                
                CREATE TABLE IF NOT EXISTS vocabulary (
                    word TEXT PRIMARY KEY,
                    correction_count INTEGER DEFAULT 1,
                    first_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_corrections_used ON corrections(used_for_training);
                CREATE INDEX IF NOT EXISTS idx_corrections_hash ON corrections(audio_hash);
                CREATE INDEX IF NOT EXISTS idx_corrections_created ON corrections(created_at);
            """)
            
            # Check if tables are empty and add sample data for testing
            count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
            if count == 0:
                print("📝 Database initialized with empty tables")
    
    def add_correction(self, correction_data: Dict) -> int:
        """Add a new correction"""
        print(f"💾 Adding correction to database...")
        print(f"   Original: {correction_data['original_text'][:50]}")
        print(f"   Corrected: {correction_data['corrected_text'][:50]}")
        
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO corrections (
                    audio_hash, original_text, corrected_text, confidence,
                    language, file_path, start_time, end_time, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                correction_data['audio_hash'],
                correction_data['original_text'],
                correction_data['corrected_text'],
                correction_data['confidence'],
                correction_data.get('language', 'en'),
                correction_data.get('file_path', ''),
                correction_data.get('start_time', 0),
                correction_data.get('end_time', 0),
                datetime.now().isoformat()
            ))
            
            # Update vocabulary
            words = correction_data['corrected_text'].lower().split()
            for word in words:
                if len(word) > 2 and word.isalpha():
                    conn.execute("""
                        INSERT INTO vocabulary (word, last_used)
                        VALUES (?, CURRENT_TIMESTAMP)
                        ON CONFLICT(word) DO UPDATE SET
                            correction_count = correction_count + 1,
                            last_used = CURRENT_TIMESTAMP
                    """, (word,))
            
            correction_id = cursor.lastrowid
            print(f"✅ Correction added with ID: {correction_id}")
            
            # Get updated count
            count = conn.execute("SELECT COUNT(*) FROM corrections WHERE used_for_training = 0").fetchone()[0]
            print(f"   Total pending corrections now: {count}")
            
            return correction_id
    
    def get_pending_corrections(self, limit: int = 100) -> List[Dict]:
        """Get corrections not yet used for training"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM corrections 
                WHERE used_for_training = 0 
                ORDER BY created_at ASC 
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def mark_corrections_trained(self, correction_ids: List[int], session_id: int):
        """Mark corrections as used in training"""
        if not correction_ids:
            return
        
        placeholders = ','.join('?' * len(correction_ids))
        with self.get_connection() as conn:
            conn.execute(f"""
                UPDATE corrections 
                SET used_for_training = 1, training_session_id = ?
                WHERE id IN ({placeholders})
            """, [session_id] + correction_ids)
    
    def create_training_session(self, old_model: str = None) -> int:
        """Create a new training session"""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO training_sessions (old_model_version, status, start_time)
                VALUES (?, 'pending', CURRENT_TIMESTAMP)
            """, (old_model,))
            return cursor.lastrowid
    
    def update_training_session(self, session_id: int, new_model: str,
                                 corrections_count: int, wer_before: float, wer_after: float):
        """Update training session with results"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE training_sessions 
                SET end_time = CURRENT_TIMESTAMP,
                    new_model_version = ?,
                    corrections_count = ?,
                    wer_before = ?,
                    wer_after = ?,
                    status = 'completed'
                WHERE id = ?
            """, (new_model, corrections_count, wer_before, wer_after, session_id))
    
    def fail_training_session(self, session_id: int, error: str = None):
        """Mark training session as failed"""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE training_sessions 
                SET end_time = CURRENT_TIMESTAMP,
                    status = 'failed'
                WHERE id = ?
            """, (session_id,))
            
            if error:
                # Store error in a separate table or log
                print(f"Training session {session_id} failed: {error}")
    
    def get_statistics(self) -> Dict:
        """Get database statistics"""
        with self.get_connection() as conn:
            stats = {}
            
            stats['total_corrections'] = conn.execute(
                "SELECT COUNT(*) FROM corrections"
            ).fetchone()[0]
            
            stats['pending_corrections'] = conn.execute(
                "SELECT COUNT(*) FROM corrections WHERE used_for_training = 0"
            ).fetchone()[0]
            
            stats['trained_corrections'] = conn.execute(
                "SELECT COUNT(*) FROM corrections WHERE used_for_training = 1"
            ).fetchone()[0]
            
            stats['vocabulary_size'] = conn.execute(
                "SELECT COUNT(*) FROM vocabulary"
            ).fetchone()[0]
            
            stats['training_sessions'] = conn.execute(
                "SELECT COUNT(*) FROM training_sessions"
            ).fetchone()[0]
            
            stats['completed_trainings'] = conn.execute(
                "SELECT COUNT(*) FROM training_sessions WHERE status = 'completed'"
            ).fetchone()[0]
            
            return stats
    
    def get_training_history(self, limit: int = 10) -> List[Dict]:
        """Get training session history"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM training_sessions 
                ORDER BY start_time DESC 
                LIMIT ?
            """, (limit,)).fetchall()
            return [dict(row) for row in rows]
    
    def get_vocabulary(self, min_count: int = 3, limit: int = 100) -> List[Dict]:
        """Get learned vocabulary"""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM vocabulary 
                WHERE correction_count >= ?
                ORDER BY correction_count DESC 
                LIMIT ?
            """, (min_count, limit)).fetchall()
            return [dict(row) for row in rows]
    
    def clear_all_corrections(self) -> int:
        """Clear all corrections (for testing)"""
        with self.get_connection() as conn:
            count = conn.execute("DELETE FROM corrections").rowcount
            conn.execute("DELETE FROM vocabulary")
            return count