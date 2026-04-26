"""
Transcriber Module - Complete with CUDA support, sentence detection, and training
"""

import os
import threading
import queue
import gc
from typing import Optional, Callable, List, Dict, Tuple
from pathlib import Path

try:
    import torch
except ImportError:
    torch = None

try:
    import numpy as np
except ImportError:
    np = None

# Check for faster-whisper availability
try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False
    print("Warning: faster-whisper not available")

# Try transformers for custom models
try:
    from transformers import WhisperProcessor, WhisperForConditionalGeneration
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Warning: transformers not available")


class Transcriber:
    """Manages Whisper model and transcription with CUDA support and sentence detection"""
    
    def __init__(self, model_size: str = "base", device: str = "auto", 
                 compute_type: str = "float32", language: str = "en",
                 custom_model_path: str = None):
        self.model_size = model_size
        self.compute_type = compute_type
        self.language = language
        self.custom_model_path = custom_model_path
        self.model = None
        self.processor = None
        self.is_loading = False
        self.is_loaded = False
        self.transcription_queue = queue.Queue()
        
        # Default to local Hugging Face model if available
        if custom_model_path is None:
            # Check for local HF models first
            local_hf_path = self._find_local_hf_model()
            if local_hf_path:
                self.custom_model_path = str(local_hf_path)
                self.model_type = "custom"
            else:
                self.model_type = "standard"  # Fallback if no local models
        else:
            self.model_type = "custom"
        
        # Resolve device
        self.device = self._resolve_device(device)
        
        # Determine target dtype
        if self.device == "cuda" and torch is not None:
            if compute_type == "float16":
                self.target_dtype = torch.float16
            else:
                self.target_dtype = torch.float32
        else:
            self.target_dtype = torch.float32 if torch is not None else None
        
        print("Transcriber Configuration:")
        print(f"   Device: {self.device}")
        print(f"   Compute Type: {self.compute_type}")
        print(f"   Target Dtype: {self.target_dtype}")
        print(f"   Model Type: {self.model_type}")
        if self.custom_model_path:
            print(f"   Custom Model: {self.custom_model_path}")
    
    def _resolve_device(self, device: str) -> str:
        """Resolve device string to valid PyTorch device"""
        if device is None:
            return "cpu"
        
        device_str = str(device).strip().lower()
        
        if "cuda" in device_str:
            return "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
        
        if device_str == "auto":
            return "cuda" if (torch is not None and torch.cuda.is_available()) else "cpu"
        if device_str == "cpu":
            return "cpu"
        
        return "cpu"
    
    def _find_default_hf_model(self) -> Optional[Path]:
        """Find a default Hugging Face Whisper model to use"""
        # Check common model directories
        model_dirs = [
            Path("./models"),  # Local models folder
            Path.home() / ".cache" / "huggingface" / "hub",  # HF cache
            Path("./src/models"),  # Alternative local path
        ]
        
        # Preferred model sizes (smallest to largest)
        preferred_sizes = ["tiny", "base", "small", "medium", "large"]
        
        for model_dir in model_dirs:
            if not model_dir.exists():
                continue
                
            # Look for whisper model folders
            for item in model_dir.iterdir():
                if item.is_dir() and "whisper" in item.name.lower():
                    # Check if it's a valid HF model (has config.json)
                    config_file = item / "config.json"
                    if config_file.exists():
                        # Check if it matches our preferred size
                        model_name = item.name.lower()
                        for size in preferred_sizes:
                            if size in model_name:
                                return item
                        
                        # If no preferred size match, return the first valid model
                        return item
        
        return None
    
    def _find_local_hf_model(self) -> Optional[Path]:
        """Find a local Hugging Face Whisper model in the models directory"""
        models_dir = Path("./models")
        if not models_dir.exists():
            return None
            
        # Look for whisper model folders with config.json
        for item in models_dir.iterdir():
            if item.is_dir() and "whisper" in item.name.lower():
                config_file = item / "config.json"
                if config_file.exists():
                    print(f"Found local HF model: {item}")
                    return item
        
        return None
    
    def load_model(self) -> bool:
        """Load the Whisper model"""
        if self.is_loaded:
            return True
        
        self.is_loading = True
        
        try:
            # Clear GPU cache if using CUDA
            if self.device == "cuda" and torch is not None:
                torch.cuda.empty_cache()
                gc.collect()
                print("Cleared GPU cache")
            
            # Use custom model when specified
            if self.custom_model_path:
                if TRANSFORMERS_AVAILABLE:
                    return self._load_custom_model()
                elif FASTER_WHISPER_AVAILABLE:
                    # Try faster-whisper for local HF models
                    print("Using faster-whisper for local HF model...")
                    return self._load_faster_whisper()
                else:
                    print("Warning: no library available for custom models.")
                    print("   Install transformers: pip install transformers")
                    print("   Or faster-whisper: pip install faster-whisper")
                    return False
            # Otherwise load standard Whisper
            return self._load_standard_whisper()
            
        except Exception as e:
            print(f"Error loading model: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.is_loading = False
    
    def _load_faster_whisper(self) -> bool:
        """Load using faster-whisper"""
        try:
            # Determine compute type
            if self.device == "cuda":
                compute = "float16"
            else:
                compute = "int8"
            
            # Use custom model path if available, otherwise use model_size
            model_to_load = self.custom_model_path if self.custom_model_path else self.model_size
            
            print(f"Loading faster-whisper: {model_to_load}")
            print(f"   Device: {self.device}, Compute: {compute}")
            
            self.model = WhisperModel(
                model_to_load,
                device=self.device,
                compute_type=compute,
                num_workers=2 if self.device == "cuda" else 1,
                cpu_threads=4 if self.device == "cpu" else 0
            )
            
            self.is_loaded = True
            print(f"Faster-whisper model loaded on {self.device.upper()}")
            return True
            
        except Exception as e:
            print(f"Faster-whisper failed: {e}")
            return False
    
    def _load_custom_model(self) -> bool:
        """Load custom Hugging Face model"""
        try:
            model_path = Path(self.custom_model_path)
            if not model_path.exists():
                print(f"Model path does not exist: {model_path}")
                return False
            
            print(f"Loading custom HF model from: {model_path}")
            
            # Check if transformers is available
            if not TRANSFORMERS_AVAILABLE:
                print("Warning: transformers library not available.")
                print("   To use Hugging Face models, install: pip install transformers")
                print("   Alternative: Use faster-whisper for better performance")
                print("   Install: pip install faster-whisper")
                return False
            
            # Load processor
            self.processor = WhisperProcessor.from_pretrained(str(model_path))
            
            # Load model
            self.model = WhisperForConditionalGeneration.from_pretrained(
                str(model_path),
                torch_dtype=torch.float32 if torch is not None else None,
                low_cpu_mem_usage=True
            )
            
            # Convert to target dtype if needed
            if self.target_dtype is not None and self.target_dtype != torch.float32:
                print(f"   Converting model to {self.target_dtype}")
                if torch is not None and self.target_dtype == torch.float16:
                    self.model = self.model.half()
            
            # Move to device
            self.model.to(self.device)
            self.model.eval()
            
            # Set language
            if self.language != "auto":
                self.model.generation_config.language = self.language
                self.model.generation_config.task = "transcribe"
            
            self.is_loaded = True
            print(f"Custom HF model loaded on {self.device.upper()}")
            
            if self.device == "cuda" and torch is not None:
                allocated = torch.cuda.memory_allocated() / 1024**3
                print(f"   GPU Memory used: {allocated:.2f} GB")
            
            return True
            
        except Exception as e:
            print(f"Custom model failed: {e}")
            print("   Try using faster-whisper instead: pip install faster-whisper")
            return False
    
    def _load_standard_whisper(self) -> bool:
        """Load standard OpenAI whisper"""
        try:
            import whisper
            
            print(f"Loading standard Whisper: {self.model_size}")
            
            self.model = whisper.load_model(
                self.model_size,
                device=self.device if self.device == "cuda" else "cpu"
            )
            
            self.is_loaded = True
            print(f"Standard Whisper loaded on {self.device.upper()}")
            return True
            
        except Exception as e:
            print(f"Standard Whisper failed: {e}")
            return False
    
    def transcribe_chunk(self, audio_chunk, language: str = None) -> str:
        """Transcribe a single audio chunk"""
        if not self.is_loaded:
            return ""
        
        lang = language or self.language
        
        try:
            if self.custom_model_path and TRANSFORMERS_AVAILABLE and hasattr(self.model, 'generate'):
                return self._transcribe_custom(audio_chunk, lang)
            
            if hasattr(self.model, 'transcribe'):
                result = self.model.transcribe(
                    audio_chunk,
                    language=lang if lang != "auto" else None,
                    fp16=(self.device == "cuda")
                )
                return result["text"]
            
            return ""

                
        except Exception as e:
            print(f"Transcription error: {e}")
            return ""
    
    def transcribe_with_sentences(self, audio_chunk, language: str = None) -> List[Dict]:
        """
        Transcribe audio and return with sentence boundaries
        
        Args:
            audio_chunk: Audio data
            language: Language code
            
        Returns:
            List of dicts with 'text', 'start', 'end', 'is_sentence_end', 'confidence'
        """
        if not self.is_loaded:
            return []
        
        lang = language or self.language
        
        try:
            if self.custom_model_path and TRANSFORMERS_AVAILABLE and hasattr(self.model, 'generate'):
                return self._transcribe_custom_with_sentences(audio_chunk, lang)
            
            if hasattr(self.model, 'transcribe'):
                result = self.model.transcribe(
                    audio_chunk,
                    language=lang if lang != "auto" else None,
                    word_timestamps=True
                )
                return self._combine_into_sentences(result)
            
            return []
                
        except Exception as e:
            print(f"Sentence transcription error: {e}")
            return []
    
    def _transcribe_custom_with_sentences(self, audio_chunk, language: str) -> List[Dict]:
        """Transcribe using custom model with sentence detection"""
        try:
            # Ensure audio is float32
            if np is not None and isinstance(audio_chunk, np.ndarray):
                audio_chunk = audio_chunk.astype(np.float32)
            
            # Prepare input features
            inputs = self.processor(
                audio_chunk, 
                sampling_rate=16000, 
                return_tensors="pt"
            )
            
            input_features = inputs.input_features
            attention_mask = inputs.get("attention_mask", None)
            
            # Convert to match model dtype
            model_dtype = next(self.model.parameters()).dtype
            input_features = input_features.to(dtype=model_dtype)
            input_features = input_features.to(self.device)
            
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.device)
            
            # Generate with timestamps
            gen_kwargs = {
                "input_features": input_features,
                "max_length": 448,
                "num_beams": 3,
                "early_stopping": True,
                "return_timestamps": True
            }
            
            if attention_mask is not None:
                gen_kwargs["attention_mask"] = attention_mask
            
            if language != "auto":
                gen_kwargs["language"] = language
                gen_kwargs["task"] = "transcribe"
            
            if torch is None:
                raise ImportError("Torch is required for custom model inference")
            with torch.no_grad():
                predicted_ids = self.model.generate(**gen_kwargs)
            
            # Decode with timestamps
            transcription = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            
            # Simple sentence splitting
            sentences = []
            for sent in transcription.split('. '):
                if sent.strip():
                    sentences.append({
                        "text": sent.strip() + ".",
                        "start": 0,  # Approximate
                        "end": 0,   # Approximate
                        "is_sentence_end": True,
                        "confidence": 0.85
                    })
            
            return sentences
            
        except Exception as e:
            print(f"Custom sentence transcription error: {e}")
            return []
    
    def _transcribe_custom(self, audio_chunk, language: str) -> str:
        """Transcribe using custom model"""
        try:
            if np is not None and isinstance(audio_chunk, np.ndarray):
                audio_chunk = audio_chunk.astype(np.float32)
            
            inputs = self.processor(
                audio_chunk, 
                sampling_rate=16000, 
                return_tensors="pt"
            )
            
            input_features = inputs.input_features
            attention_mask = inputs.get("attention_mask", None)
            
            model_dtype = next(self.model.parameters()).dtype
            input_features = input_features.to(dtype=model_dtype)
            input_features = input_features.to(self.device)
            
            if attention_mask is not None:
                attention_mask = attention_mask.to(self.device)
            
            gen_kwargs = {
                "input_features": input_features,
                "max_length": 448,
                "num_beams": 3,
                "early_stopping": True,
            }
            
            if attention_mask is not None:
                gen_kwargs["attention_mask"] = attention_mask
            
            if language != "auto":
                gen_kwargs["language"] = language
                gen_kwargs["task"] = "transcribe"
            
            if torch is None:
                raise ImportError("Torch is required for custom model inference")
            with torch.no_grad():
                predicted_ids = self.model.generate(**gen_kwargs)
            
            transcription = self.processor.batch_decode(
                predicted_ids, 
                skip_special_tokens=True
            )[0]
            
            return transcription.strip()
            
        except Exception as e:
            print(f"Custom transcription error: {e}")
            return ""
    
    def _is_sentence_end(self, text: str) -> bool:
        """Check if text ends with sentence-ending punctuation"""
        sentence_endings = {'.', '!', '?', 'ã€‚', 'ï¼', 'ï¼Ÿ'}
        return text.strip() and text.strip()[-1] in sentence_endings
    
    def _combine_into_sentences(self, result: dict) -> List[Dict]:
        """Combine word-level timestamps into sentences"""
        if "segments" not in result:
            return []
        
        sentences = []
        current_sentence = ""
        current_start = 0
        current_end = 0
        
        for segment in result["segments"]:
            if not current_sentence:
                current_start = segment["start"]
            
            current_sentence += segment["text"]
            current_end = segment["end"]
            
            if self._is_sentence_end(segment["text"]):
                sentences.append({
                    "text": current_sentence.strip(),
                    "start": current_start,
                    "end": current_end,
                    "is_sentence_end": True,
                    "confidence": segment.get("confidence", 0.85)
                })
                current_sentence = ""
        
        if current_sentence.strip():
            sentences.append({
                "text": current_sentence.strip(),
                "start": current_start,
                "end": current_end,
                "is_sentence_end": False,
                "confidence": 0.85
            })
        
        return sentences
    
    def transcribe_file(self, file_path: str, callback: Callable) -> None:
        """Transcribe entire file with progress updates"""
        def worker():
            try:
                import librosa
                
                print(f"Loading audio: {file_path}")
                audio, sr = librosa.load(file_path, sr=16000)
                print(f"   Duration: {len(audio)/sr:.1f}s")
                
                chunk_duration = 30
                chunk_samples = chunk_duration * sr
                
                for i in range(0, len(audio), chunk_samples):
                    chunk = audio[i:i + chunk_samples]
                    if len(chunk) < 16000:
                        continue
                    
                    text = self.transcribe_chunk(chunk)
                    start = i / sr
                    end = (i + len(chunk)) / sr
                    
                    if text:
                        callback(text, start, end)
                
            except Exception as e:
                print(f"File transcription error: {e}")
        
        thread = threading.Thread(target=worker)
        thread.start()
    
    def set_model_size(self, size: str):
        """Change model size (will reload)"""
        if size != self.model_size:
            self.model_size = size
            self.is_loaded = False
            self.model = None
            if self.device == "cuda" and torch is not None:
                torch.cuda.empty_cache()
    
    def set_language(self, language: str):
        """Set transcription language"""
        self.language = language
        if self.model and TRANSFORMERS_AVAILABLE and hasattr(self.model, 'generation_config'):
            if language != "auto":
                self.model.generation_config.language = language
    
    def get_available_models(self) -> List[str]:
        """Get list of available Whisper models"""
        return ["tiny", "base", "small", "medium", "large"]
    
    def is_model_loaded(self) -> bool:
        return self.is_loaded
    
    def clear_gpu_cache(self):
        """Clear GPU cache"""
        if self.device == "cuda" and torch is not None:
            torch.cuda.empty_cache()
            gc.collect()
