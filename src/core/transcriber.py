"""
Transcriber Module - Fixed with proper attention mask handling
"""

import torch
import numpy as np
from pathlib import Path
from typing import Optional, Callable, List

try:
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("⚠️ transformers not installed")


class Transcriber:
    """Manages Whisper model for transcription with proper attention mask"""
    
    def __init__(self, model_size: str = "base", device: str = "auto", 
                 compute_type: str = "float32", language: str = "en",
                 custom_model_path: str = None):
        
        self.model_size = model_size
        self.language = language
        self.custom_model_path = custom_model_path
        self.model = None
        self.processor = None
        self.is_loaded = False
        self.target_dtype = None
        
        # Resolve device
        self.device = self._resolve_device(device)
        
        # Determine target dtype
        if self.device == "cuda":
            if compute_type == "float16":
                self.target_dtype = torch.float16
            else:
                self.target_dtype = torch.float32
        else:
            self.target_dtype = torch.float32
        
        print(f"📊 Transcriber Config:")
        print(f"   Device: {self.device}")
        print(f"   Target dtype: {self.target_dtype}")
        print(f"   Custom Model: {custom_model_path}")
    
    def _resolve_device(self, device: str) -> str:
        """Resolve device string to valid PyTorch device"""
        if device is None:
            return "cpu"
        
        device = str(device).strip().lower()
        
        if "cuda" in device:
            return "cuda"
        
        if device == "auto":
            return "cuda" if torch.cuda.is_available() else "cpu"
        
        if device == "cpu":
            return "cpu"
        
        return "cpu"
    
    def load_model(self) -> bool:
        """Load the custom Whisper model"""
        if self.is_loaded:
            return True
        
        if not TRANSFORMERS_AVAILABLE:
            print("❌ transformers not installed. Run: pip install transformers")
            return False
        
        if not self.custom_model_path:
            print("❌ No custom model path provided")
            return False
        
        model_path = Path(self.custom_model_path)
        if not model_path.exists():
            print(f"❌ Model path does not exist: {model_path}")
            return False
        
        try:
            print(f"📥 Loading processor from: {model_path}")
            self.processor = WhisperProcessor.from_pretrained(str(model_path))
            
            print(f"📥 Loading model from: {model_path}")
            # Load in float32 first
            self.model = WhisperForConditionalGeneration.from_pretrained(
                str(model_path),
                torch_dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            
            print(f"   Model loaded with dtype: {self.model.dtype}")
            
            # Convert to target dtype if needed
            if self.target_dtype != torch.float32:
                print(f"   Converting model to {self.target_dtype}...")
                if self.target_dtype == torch.float16:
                    self.model = self.model.half()
            
            # Move to device
            print(f"   Moving model to device: {self.device}")
            self.model.to(self.device)
            self.model.eval()
            
            # Set generation config
            self.model.generation_config.forced_decoder_ids = None
            # Clear suppress tokens to avoid duplicate processor warnings
            self.model.generation_config.suppress_tokens = None
            self.model.generation_config.begin_suppress_tokens = None
            
            # Set language if specified
            if self.language != "auto":
                self.model.generation_config.language = self.language
                self.model.generation_config.task = "transcribe"
            
            self.is_loaded = True
            print(f"✅ Model loaded successfully on {self.device}")
            
            if self.device == "cuda":
                allocated = torch.cuda.memory_allocated() / 1024**3
                print(f"   GPU Memory used: {allocated:.2f} GB")
            
            return True
            
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def transcribe_chunk(self, audio_chunk, language: str = None) -> str:
        """Transcribe a single audio chunk with proper attention mask"""
        if not self.is_loaded:
            print("❌ Model not loaded")
            return ""
        
        if not self.processor or not self.model:
            print("❌ Processor or model not initialized")
            return ""
        
        lang = language or self.language
        
        try:
            # Ensure audio is float32
            if isinstance(audio_chunk, np.ndarray):
                audio_chunk = audio_chunk.astype(np.float32)
            elif isinstance(audio_chunk, torch.Tensor):
                audio_chunk = audio_chunk.float().cpu().numpy()
            
            # Prepare input features with attention mask
            inputs = self.processor(
                audio_chunk, 
                sampling_rate=16000, 
                return_tensors="pt"
            )
            
            input_features = inputs.input_features
            attention_mask = inputs.get("attention_mask", None)
            
            # Create attention mask if not provided (Whisper doesn't generate it)
            if attention_mask is None:
                # For Whisper, create attention mask of all 1s since input is padded to fixed length
                attention_mask = torch.ones_like(input_features[:, 0, :], dtype=torch.long)
            
            # Convert to match model dtype
            model_dtype = next(self.model.parameters()).dtype
            input_features = input_features.to(dtype=model_dtype)
            input_features = input_features.to(self.device)
            
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.device)
            
            # Prepare generation kwargs
            gen_kwargs = {
                "input_features": input_features,
                "max_length": 448,
                "num_beams": 3,
                "early_stopping": True,
                "return_timestamps": False,
            }
            
            if attention_mask is not None:
                gen_kwargs["attention_mask"] = attention_mask
            
            # Add language if specified
            if lang != "auto":
                gen_kwargs["language"] = lang
                gen_kwargs["task"] = "transcribe"
            
            # Generate with no forced decoder ids to avoid warnings
            with torch.no_grad():
                predicted_ids = self.model.generate(**gen_kwargs)
            
            # Decode
            transcription = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            
            return transcription.strip()
            
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""
    
    def transcribe_file(self, file_path: str, callback: Callable) -> None:
        """Transcribe entire file"""
        import librosa
        
        try:
            print(f"🎵 Loading audio: {file_path}")
            audio, sr = librosa.load(file_path, sr=16000)
            print(f"   Audio duration: {len(audio)/16000:.1f} seconds")
            
            # Transcribe in chunks
            chunk_duration = 30
            chunk_samples = chunk_duration * 16000
            
            for i in range(0, len(audio), chunk_samples):
                chunk = audio[i:i + chunk_samples]
                if len(chunk) < 16000:
                    continue
                
                text = self.transcribe_chunk(chunk)
                start_time = i / 16000
                end_time = (i + len(chunk)) / 16000
                
                if text:
                    print(f"   [{start_time:.1f}s] {text[:50]}...")
                    callback(text, start_time, end_time)
                
        except Exception as e:
            print(f"❌ File transcription error: {e}")
    
    def set_language(self, language: str):
        """Set transcription language"""
        self.language = language
        if self.model and self.language != "auto":
            self.model.generation_config.language = language
            self.model.generation_config.task = "transcribe"
    
    def is_model_loaded(self) -> bool:
        return self.is_loaded