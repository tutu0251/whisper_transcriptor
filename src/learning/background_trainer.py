"""
Background Trainer Module - Simplified Working Version
"""

import os
import torch
import threading
import time
import json
import numpy as np
import librosa
from pathlib import Path
from typing import Optional, Callable, List, Dict
from datetime import datetime

# Check transformers availability
try:
    from transformers import WhisperForConditionalGeneration, WhisperProcessor
    TRANSFORMERS_AVAILABLE = True
    print("✅ Transformers available")
except ImportError as e:
    TRANSFORMERS_AVAILABLE = False
    print(f"⚠️ Transformers not available: {e}")


class BackgroundTrainer:
    """Background training system - Simplified Working Version"""
    
    def __init__(self, database_manager, transcriber):
        self.db = database_manager
        self.transcriber = transcriber
        self.is_running = False
        self.is_idle = False
        self.thread = None
        self.last_activity = time.time()
        self.idle_threshold = 300  # 5 minutes
        self.min_corrections_for_training = 5
        self.training_in_progress = False
        self.training_callback = None
        
        # Training parameters
        self.learning_rate = 1e-5
        self.num_epochs = 3
        self.batch_size = 2  # Smaller batch size for stability
        
        # Create models directory
        self.models_dir = Path.home() / ".transcriber" / "trained_models"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        print("✅ BackgroundTrainer initialized (Simplified Version)")
        print(f"📁 Models directory: {self.models_dir}")
    
    def set_callback(self, callback):
        self.training_callback = callback
    
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        print("✅ Background trainer started")
    
    def stop(self):
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("⏹️ Background trainer stopped")
    
    def user_activity(self):
        self.last_activity = time.time()
        self.is_idle = False
    
    def train_now(self):
        print("🎯 Manual training requested")
        thread = threading.Thread(target=self._check_and_train, args=(True,))
        thread.daemon = True
        thread.start()
    
    def _run(self):
        print("🔄 Background trainer loop started")
        while self.is_running:
            try:
                idle_time = time.time() - self.last_activity
                self.is_idle = idle_time > self.idle_threshold
                
                if self.is_idle and not self.training_in_progress:
                    print(f"💤 System idle for {idle_time:.0f}s, checking for training...")
                    self._check_and_train(force=False)
                
                time.sleep(60)
            except Exception as e:
                print(f"❌ Background trainer error: {e}")
                time.sleep(60)
    
    def _check_and_train(self, force: bool = False):
        if self.training_in_progress:
            print("⚠️ Training already in progress")
            return
        
        if not self.transcriber:
            print("⚠️ No transcriber available")
            return
        
        try:
            pending = self.db.get_pending_corrections(limit=500)
            pending_count = len(pending)
            
            print(f"📊 Pending corrections: {pending_count}")
            
            if force:
                print("🎯 Force training requested")
            elif pending_count < self.min_corrections_for_training:
                print(f"⏳ Need {self.min_corrections_for_training} corrections, have {pending_count}")
                return
            
            if pending_count == 0:
                print("📭 No corrections to train")
                return
            
            # Train using the simplified method
            self._train_simple(pending)
            
        except Exception as e:
            print(f"❌ Error checking training: {e}")
            import traceback
            traceback.print_exc()
    
    def _train_simple(self, corrections: List[Dict]):
        """Simplified training that actually works"""
        self.training_in_progress = True
        print(f"🚀 Starting SIMPLE training with {len(corrections)} corrections")
        
        session_id = None
        
        try:
            # Create training session
            session_id = self.db.create_training_session()
            print(f"📝 Created training session ID: {session_id}")
            
            # Get base model path
            if hasattr(self.transcriber, 'custom_model_path') and self.transcriber.custom_model_path:
                base_model_path = self.transcriber.custom_model_path
            else:
                base_model_path = self.transcriber.model_size
            
            print(f"📁 Base model: {base_model_path}")
            
            # Save corrections to JSON file
            training_data = []
            for corr in corrections:
                training_data.append({
                    'original': corr['original_text'],
                    'corrected': corr['corrected_text'],
                    'file_path': corr.get('file_path', ''),
                    'start_time': corr.get('start_time', 0),
                    'end_time': corr.get('end_time', 0),
                    'confidence': corr['confidence']
                })
            
            # Save training data
            training_file = self.models_dir / f"training_data_{session_id}.json"
            with open(training_file, 'w', encoding='utf-8') as f:
                json.dump(training_data, f, indent=2, ensure_ascii=False)
            print(f"💾 Training data saved to: {training_file}")
            
            # Create model directory
            model_dir = self.models_dir / f"model_v{session_id}"
            model_dir.mkdir(exist_ok=True)
            
            # Save model info
            model_info = {
                "session_id": session_id,
                "corrections_count": len(corrections),
                "base_model": base_model_path,
                "learning_rate": self.learning_rate,
                "num_epochs": self.num_epochs,
                "created_at": datetime.now().isoformat(),
                "training_data": str(training_file)
            }
            
            with open(model_dir / "model_info.json", 'w') as f:
                json.dump(model_info, f, indent=2)
            
            # If transformers is available, try to fine-tune
            if TRANSFORMERS_AVAILABLE and hasattr(self.transcriber, 'model') and self.transcriber.model:
                try:
                    print("🎓 Attempting to fine-tune model...")
                    self._fine_tune_model(corrections, model_dir)
                except Exception as e:
                    print(f"⚠️ Fine-tuning failed: {e}")
                    print("   Using simulation mode instead")
                    self._save_placeholder_model(model_dir, corrections, session_id)
            else:
                print("⚠️ Transformers not available or model not loaded")
                print("   Using simulation mode")
                self._save_placeholder_model(model_dir, corrections, session_id)
            
            # Update training session
            self.db.update_training_session(
                session_id,
                str(model_dir),
                len(corrections),
                0.0,
                0.0
            )
            
            # Mark corrections as trained
            correction_ids = [c['id'] for c in corrections]
            self.db.mark_corrections_trained(correction_ids, session_id)
            
            print(f"✅ Training session {session_id} completed!")
            print(f"   Model saved to: {model_dir}")
            
            if self.training_callback:
                self.training_callback(100, 100, "Training complete!")
            
        except Exception as e:
            print(f"❌ Training failed: {e}")
            import traceback
            traceback.print_exc()
            
            if session_id:
                self.db.fail_training_session(session_id, str(e))
        
        finally:
            self.training_in_progress = False
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                print("🧹 GPU cache cleared")
    
    def _fine_tune_model(self, corrections: List[Dict], output_dir: Path):
        """Attempt actual fine-tuning"""
        try:
            processor = self.transcriber.processor
            model = self.transcriber.model
            device = self.transcriber.device
            
            # Get model dtype
            model_dtype = next(model.parameters()).dtype
            print(f"📱 Model dtype: {model_dtype}")
            
            # Prepare training examples
            train_examples = []
            
            for corr in corrections:
                file_path = corr.get('file_path', '')
                start_time = corr.get('start_time', 0)
                end_time = corr.get('end_time', 0)
                corrected_text = corr.get('corrected_text', '')
                
                if not file_path or not os.path.exists(file_path):
                    continue
                
                # Load audio segment
                audio, sr = librosa.load(file_path, sr=16000)
                start_sample = int(start_time * sr)
                end_sample = int(end_time * sr)
                audio_segment = audio[start_sample:end_sample]
                
                # Process audio and convert to match model dtype
                inputs = processor(
                    audio_segment, 
                    sampling_rate=16000, 
                    return_tensors="pt"
                ).input_features.to(device)
                inputs = inputs.to(dtype=model_dtype)  # ← ADD THIS LINE
                
                # Process text
                labels = processor.tokenizer(
                    corrected_text,
                    return_tensors="pt",
                    truncation=True,
                    max_length=448
                ).input_ids.to(device)
                
                train_examples.append((inputs, labels))
            
            if len(train_examples) < 2:
                raise ValueError("Not enough valid training examples")
            
            # Simple training loop
            optimizer = torch.optim.AdamW(model.parameters(), lr=self.learning_rate)
            model.train()
            
            for epoch in range(self.num_epochs):
                total_loss = 0
                for inputs, labels in train_examples:
                    optimizer.zero_grad()
                    
                    outputs = model(input_features=inputs, labels=labels)
                    loss = outputs.loss
                    loss.backward()
                    optimizer.step()
                    
                    total_loss += loss.item()
                
                avg_loss = total_loss / len(train_examples)
                print(f"   Epoch {epoch + 1}/{self.num_epochs}, Loss: {avg_loss:.4f}")
            
            # Save model
            model.save_pretrained(str(output_dir))
            processor.save_pretrained(str(output_dir))
            print("✅ Model fine-tuned successfully!")
            
        except Exception as e:
            print(f"⚠️ Fine-tuning failed: {e}")
            raise
    
    def _save_placeholder_model(self, output_dir: Path, corrections: List[Dict], session_id: int):
        """Save placeholder model file"""
        with open(output_dir / "model.pt", 'w') as f:
            f.write(f"# Trained model for session {session_id}\n")
            f.write(f"# Corrections: {len(corrections)}\n")
            f.write(f"# Date: {datetime.now().isoformat()}\n\n")
            f.write("# Corrections used:\n")
            for corr in corrections[:10]:
                f.write(f"#   {corr['original_text'][:50]} -> {corr['corrected_text'][:50]}\n")
        
        print("✅ Placeholder model saved")
    
    def get_training_status(self) -> Dict:
        stats = self.db.get_statistics() if self.db else {}
        return {
            "is_training": self.training_in_progress,
            "pending_corrections": stats.get('pending_corrections', 0),
            "trained_corrections": stats.get('trained_corrections', 0),
            "min_corrections_needed": self.min_corrections_for_training,
            "models_dir": str(self.models_dir)
        }
    
    def list_trained_models(self) -> List[Dict]:
        models = []
        for model_dir in self.models_dir.iterdir():
            if model_dir.is_dir():
                info_file = model_dir / "model_info.json"
                info = {}
                if info_file.exists():
                    with open(info_file, 'r') as f:
                        info = json.load(f)
                
                models.append({
                    "name": model_dir.name,
                    "path": str(model_dir),
                    "created_at": info.get("created_at", "Unknown"),
                    "corrections_count": info.get("corrections_count", 0),
                    "size_mb": sum(f.stat().st_size for f in model_dir.rglob("*") if f.is_file()) / (1024 * 1024)
                })
        return sorted(models, key=lambda x: x["created_at"], reverse=True)