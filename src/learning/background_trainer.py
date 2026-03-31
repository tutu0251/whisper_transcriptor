"""
Background Trainer Module
Train model in background while user works
"""

import threading
import time
from typing import Optional, Callable


class BackgroundTrainer:
    """Background training system"""
    
    def __init__(self, database_manager, trainer):
        self.db = database_manager
        self.trainer = trainer
        self.is_running = False
        self.is_idle = False
        self.thread = None
        self.last_activity = time.time()
        self.idle_threshold = 300  # 5 minutes
    
    def start(self):
        """Start background trainer"""
        self.is_running = True
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        """Stop background trainer"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5)
    
    def user_activity(self):
        """Notify user activity"""
        self.last_activity = time.time()
        self.is_idle = False
    
    def _run(self):
        """Main training loop"""
        while self.is_running:
            # Check if idle
            idle_time = time.time() - self.last_activity
            self.is_idle = idle_time > self.idle_threshold
            
            if self.is_idle:
                self._check_and_train()
            
            time.sleep(60)  # Check every minute
    
    def _check_and_train(self):
        """Check if training is needed"""
        pending = self.db.get_pending_corrections(limit=50)
        
        if len(pending) >= 10:
            self._train(pending)
    
    def _train(self, corrections):
        """Run training on corrections"""
        if not self.trainer:
            return
        
        # Create training session
        session_id = self.db.create_training_session()
        
        # Prepare data
        train_data = corrections
        
        # Train
        self.trainer.prepare_datasets(train_data, [])
        
        def callback(epoch, loss, val_loss):
            # Update progress
            pass
        
        self.trainer.train(epochs=5, batch_size=8, callback=callback)
        
        # Save model
        model_path = self.trainer.save_model(f"v{session_id}")
        
        # Complete session
        self.db.complete_training_session(
            session_id, 
            model_path,
            len(corrections),
            0,  # TODO: wer_before
            0   # TODO: wer_after
        )
        
        # Mark corrections as trained
        correction_ids = [c['id'] for c in corrections]
        self.db.mark_corrections_trained(correction_ids, session_id)
