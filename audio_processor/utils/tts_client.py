"""
Text-to-Speech (TTS) service module with multiple backend support.
Supports gTTS (Google, free), pyttsx3 (offline), with factory pattern
for easy switching and streaming capabilities for real-time use.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Generator
from pathlib import Path
import tempfile

# TTS libraries
try:
    from gtts import gTTS
    GTTS_AVAILABLE = True
except ImportError:
    GTTS_AVAILABLE = False

try:
    import pyttsx3
    PYTTSX3_AVAILABLE = True
except ImportError:
    PYTTSX3_AVAILABLE = False


logger = logging.getLogger(__name__)


# ============================================================================
# EXCEPTIONS
# ============================================================================

class TTSError(Exception):
    """Base exception for TTS errors"""
    pass


class UnsupportedLanguageError(TTSError):
    """Raised when language is not supported"""
    pass


class SynthesisError(TTSError):
    """Raised when speech synthesis fails"""
    pass


# ============================================================================
# BASE TTS CLIENT (ABSTRACT)
# ============================================================================

class BaseTTS(ABC):
    """Abstract base class for TTS services"""
    
    def __init__(self):
        self.temp_dir = tempfile.gettempdir()
    
    @abstractmethod
    def synthesize(
        self, 
        text: str, 
        language: str, 
        output_path: str,
        **kwargs
    ) -> str:
        """
        Generate audio from text and save to file.
        
        Args:
            text: Text to convert to speech
            language: Language code (ISO 639-1)
            output_path: Path to save audio file
            **kwargs: Additional service-specific parameters
            
        Returns:
            Path to generated audio file
        """
        pass
    
    @abstractmethod
    def synthesize_streaming(
        self, 
        text: str, 
        language: str,
        **kwargs
    ) -> Generator[bytes, None, None]:
        """
        Generate audio chunks for streaming.
        
        Args:
            text: Text to convert to speech
            language: Language code
            **kwargs: Additional service-specific parameters
            
        Yields:
            Audio data chunks
        """
        pass
    
    @abstractmethod
    def list_voices(self, language: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List available voices for a language.
        
        Args:
            language: Optional language filter
            
        Returns:
            List of voice info dictionaries
        """
        pass
    
    def set_voice_parameters(
        self, 
        speed: float = 1.0, 
        pitch: float = 1.0, 
        volume: float = 1.0
    ):
        """
        Set voice parameters (if supported by service).
        
        Args:
            speed: Speech rate multiplier (1.0 = normal)
            pitch: Pitch multiplier (1.0 = normal)
            volume: Volume multiplier (1.0 = normal)
        """
        pass  # Default implementation does nothing
    
    def _chunk_text(self, text: str, max_length: int = 500) -> List[str]:
        """
        Split long text into chunks for TTS.
        Splits at sentence boundaries.
        
        Args:
            text: Text to chunk
            max_length: Maximum chunk length in characters
            
        Returns:
            List of text chunks
        """
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by sentences
        sentences = text.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= max_length:
                current_chunk += sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _cleanup_temp_file(self, filepath: str):
        """Delete temporary file if it exists"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Cleaned up temp file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {filepath}: {e}")


# ============================================================================
# GTTS CLIENT (GOOGLE TTS - FREE)
# ============================================================================

class GTTSClient(BaseTTS):
    """
    Google Text-to-Speech (free tier using gTTS library).
    
    Pros: Free, 100+ languages, easy setup, good quality
    Cons: Requires internet, limited voice control, slower
    Best for: Development, simple applications
    """
    
    def __init__(self):
        super().__init__()
        if not GTTS_AVAILABLE:
            raise ImportError(
                "gTTS library not installed. "
                "Install with: pip install gTTS==2.4.0"
            )
        logger.info("Initialized GTTSClient (Google TTS)")
    
    def synthesize(
        self, 
        text: str, 
        language: str, 
        output_path: str,
        slow: bool = False,
        **kwargs
    ) -> str:
        """
        Generate speech using gTTS.
        
        Args:
            text: Text to convert
            language: Language code (e.g., 'en', 'es', 'fr')
            output_path: Output file path
            slow: If True, use slower speech rate
            
        Returns:
            Path to generated audio file
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            tts = gTTS(text=text, lang=language, slow=slow)
            tts.save(output_path)
            
            logger.info(
                f"Generated TTS audio: {len(text)} chars, "
                f"language={language}, output={output_path}"
            )
            return output_path
            
        except Exception as e:
            logger.error(f"gTTS synthesis error: {e}")
            raise SynthesisError(f"Failed to synthesize speech: {e}")
    
    def synthesize_streaming(
        self, 
        text: str, 
        language: str,
        slow: bool = False,
        **kwargs
    ) -> Generator[bytes, None, None]:
        """
        Generate audio chunks for streaming.
        
        Note: gTTS doesn't support true streaming, so we chunk the text
        and generate separate audio files, then yield their contents.
        """
        chunks = self._chunk_text(text, max_length=500)
        
        for i, chunk in enumerate(chunks):
            # Generate audio for this chunk
            temp_file = os.path.join(
                self.temp_dir, 
                f"tts_stream_{os.getpid()}_{i}.mp3"
            )
            
            try:
                self.synthesize(chunk, language, temp_file, slow=slow)
                
                # Read and yield the audio data
                with open(temp_file, 'rb') as f:
                    audio_data = f.read()
                    yield audio_data
                
            finally:
                # Cleanup temp file
                self._cleanup_temp_file(temp_file)
    
    def list_voices(self, language: Optional[str] = None) -> List[Dict[str, str]]:
        """
        List available voices.
        
        Note: gTTS uses Google's default voice for each language.
        No voice selection available.
        """
        # Common language support in gTTS
        common_languages = {
            'en': 'English',
            'es': 'Spanish',
            'fr': 'French',
            'de': 'German',
            'it': 'Italian',
            'pt': 'Portuguese',
            'ru': 'Russian',
            'ja': 'Japanese',
            'ko': 'Korean',
            'zh': 'Chinese',
            'ar': 'Arabic',
            'hi': 'Hindi',
        }
        
        voices = []
        for code, name in common_languages.items():
            if language is None or code == language:
                voices.append({
                    'language_code': code,
                    'language_name': name,
                    'voice_name': 'default',
                    'gender': 'neutral'
                })
        
        return voices
    
    def set_voice_parameters(
        self, 
        speed: float = 1.0, 
        pitch: float = 1.0, 
        volume: float = 1.0
    ):
        """
        gTTS has limited voice control.
        Only 'slow' mode is supported (set via synthesize() slow parameter).
        """
        logger.warning(
            "gTTS has limited voice control. "
            "Use slow=True in synthesize() for slower speech."
        )


# ============================================================================
# PYTTSX3 CLIENT (OFFLINE TTS)
# ============================================================================

class Pyttsx3Client(BaseTTS):
    """
    Offline TTS using pyttsx3 library.
    
    Pros: Offline, no API costs, fast
    Cons: Robotic voice quality, limited languages
    Best for: Offline applications, testing, fallback
    """
    
    def __init__(self):
        super().__init__()
        if not PYTTSX3_AVAILABLE:
            raise ImportError(
                "pyttsx3 library not installed. "
                "Install with: pip install pyttsx3==2.90"
            )
        
        self.engine = pyttsx3.init()
        
        # Default voice parameters
        self.speed = 150  # Words per minute
        self.volume = 1.0
        self.voice_id = None
        
        logger.info("Initialized Pyttsx3Client (offline TTS)")
    
    def synthesize(
        self, 
        text: str, 
        language: str, 
        output_path: str,
        **kwargs
    ) -> str:
        """
        Generate speech using pyttsx3.
        
        Args:
            text: Text to convert
            language: Language code (support varies by system)
            output_path: Output file path
            
        Returns:
            Path to generated audio file
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")
        
        try:
            # Apply voice parameters
            self.engine.setProperty('rate', self.speed)
            self.engine.setProperty('volume', self.volume)
            
            # Try to select voice for language if available
            if self.voice_id:
                self.engine.setProperty('voice', self.voice_id)
            
            # Save to file
            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()
            
            logger.info(
                f"Generated offline TTS: {len(text)} chars, output={output_path}"
            )
            return output_path
            
        except Exception as e:
            logger.error(f"pyttsx3 synthesis error: {e}")
            raise SynthesisError(f"Failed to synthesize speech: {e}")
    
    def synthesize_streaming(
        self, 
        text: str, 
        language: str,
        **kwargs
    ) -> Generator[bytes, None, None]:
        """
        Generate audio chunks for streaming.
        
        Similar to gTTS, we chunk the text and generate separate files.
        """
        chunks = self._chunk_text(text, max_length=500)
        
        for i, chunk in enumerate(chunks):
            temp_file = os.path.join(
                self.temp_dir,
                f"tts_offline_{os.getpid()}_{i}.wav"
            )
            
            try:
                self.synthesize(chunk, language, temp_file)
                
                # Read and yield audio data
                with open(temp_file, 'rb') as f:
                    audio_data = f.read()
                    yield audio_data
                    
            finally:
                self._cleanup_temp_file(temp_file)
    
    def list_voices(self, language: Optional[str] = None) -> List[Dict[str, str]]:
        """List available system voices"""
        voices = self.engine.getProperty('voices')
        voice_list = []
        
        for voice in voices:
            # Extract language from voice
            voice_lang = None
            if hasattr(voice, 'languages') and voice.languages:
                voice_lang = voice.languages[0][:2]  # First 2 chars
            
            if language is None or voice_lang == language:
                voice_list.append({
                    'voice_id': voice.id,
                    'voice_name': voice.name,
                    'language_code': voice_lang or 'unknown',
                    'gender': 'male' if 'male' in voice.name.lower() else 'female'
                })
        
        return voice_list
    
    def set_voice_parameters(
        self, 
        speed: float = 1.0, 
        pitch: float = 1.0, 
        volume: float = 1.0
    ):
        """
        Set voice parameters for pyttsx3.
        
        Args:
            speed: Speech rate multiplier (1.0 = 150 wpm)
            pitch: Not supported in pyttsx3
            volume: Volume level (0.0 to 1.0)
        """
        self.speed = int(150 * speed)
        self.volume = max(0.0, min(1.0, volume))
        
        if pitch != 1.0:
            logger.warning("pyttsx3 does not support pitch adjustment")
        
        logger.info(f"Set voice parameters: speed={self.speed}wpm, volume={self.volume}")


# ============================================================================
# FACTORY FUNCTION
# ============================================================================

def get_tts_client(service_type: str = 'gtts') -> BaseTTS:
    """
    Factory function to get TTS client instance.
    
    Args:
        service_type: Type of TTS service ('gtts', 'pyttsx3')
        
    Returns:
        BaseTTS instance
        
    Raises:
        ValueError: If service_type is not supported
    """
    service_type = service_type.lower()
    
    if service_type == 'gtts':
        return GTTSClient()
    elif service_type == 'pyttsx3':
        return Pyttsx3Client()
    else:
        raise ValueError(
            f"Unsupported TTS service: {service_type}. "
            f"Supported: 'gtts', 'pyttsx3'"
        )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def synthesize_speech(
    text: str,
    language: str,
    output_path: str,
    service_type: Optional[str] = None,
    **kwargs
) -> str:
    """
    Convenience function for quick TTS synthesis.
    
    Args:
        text: Text to convert to speech
        language: Language code
        output_path: Where to save audio
        service_type: Optional service type (defaults to env var or 'gtts')
        **kwargs: Additional parameters passed to synthesize()
        
    Returns:
        Path to generated audio file
    """
    if service_type is None:
        service_type = os.getenv('TTS_SERVICE', 'gtts')
    
    tts_client = get_tts_client(service_type)
    return tts_client.synthesize(text, language, output_path, **kwargs)


def get_available_voices(
    language: Optional[str] = None,
    service_type: Optional[str] = None
) -> List[Dict[str, str]]:
    """
    Convenience function to list available voices.
    
    Args:
        language: Optional language filter
        service_type: Optional service type (defaults to env var or 'gtts')
        
    Returns:
        List of available voices
    """
    if service_type is None:
        service_type = os.getenv('TTS_SERVICE', 'gtts')
    
    tts_client = get_tts_client(service_type)
    return tts_client.list_voices(language)
