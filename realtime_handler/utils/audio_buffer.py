"""
Audio buffer for WebSocket real-time translation.
Collects audio chunks and uses VAD to detect when to process complete utterances.
"""

import logging
from typing import Optional
from realtime_handler.utils.vad import VAD


logger = logging.getLogger(__name__)


class AudioBuffer:
    """
    Buffer for collecting audio chunks in real-time WebSocket connections.
    
    Uses Voice Activity Detection (VAD) to determine when a complete
    utterance has been received and is ready for processing.
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        max_buffer_duration: float = 5.0,
        vad_aggressiveness: int = 2
    ):
        """
        Initialize audio buffer.
        
        Args:
            sample_rate: Audio sample rate in Hz
            max_buffer_duration: Maximum buffer duration in seconds
            vad_aggressiveness: VAD aggressiveness level (0-3)
        """
        self.sample_rate = sample_rate
        self.max_buffer_size = int(sample_rate * max_buffer_duration * 2)  # 2 bytes per sample
        self.vad_aggressiveness = vad_aggressiveness
        
        # Buffer state
        self.buffer = bytearray()
        self.frames = []  # List of frames for VAD analysis
        
        # Initialize VAD
        try:
            self.vad = VAD(
                aggressiveness=vad_aggressiveness,
                sample_rate=sample_rate
            )
        except ImportError:
            logger.warning("VAD not available, using size-based buffering only")
            self.vad = None
        
        logger.debug(
            f"AudioBuffer initialized: sample_rate={sample_rate}Hz, "
            f"max_duration={max_buffer_duration}s"
        )
    
    def add_chunk(self, audio_data: bytes):
        """
        Add audio chunk to buffer.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
        """
        self.buffer.extend(audio_data)
        
        # If VAD is available, also track frames
        if self.vad:
            frames = self.vad.split_into_frames(audio_data)
            self.frames.extend(frames)
        
        logger.debug(f"Added {len(audio_data)} bytes, buffer size: {len(self.buffer)}")
    
    def is_speech_complete(self) -> bool:
        """
        Check if a complete speech utterance has been buffered.
        
        Returns:
            True if speech is complete (pause detected or buffer full)
        """
        # Check if buffer is full (safety limit)
        if len(self.buffer) >= self.max_buffer_size:
            logger.info("Buffer full, considering speech complete")
            return True
        
        # Check if buffer has minimum content
        min_buffer_size = int(self.sample_rate * 0.5 * 2)  # 0.5 seconds minimum
        if len(self.buffer) < min_buffer_size:
            return False
        
        # Use VAD to detect speech end if available
        if self.vad and len(self.frames) > 0:
            speech_ended = self.vad.detect_speech_end(
                self.frames,
                silence_threshold=10  # ~300ms of silence
            )
            
            if speech_ended:
                logger.info("VAD detected speech end")
                return True
        
        return False
    
    def get_audio(self) -> bytes:
        """
        Get buffered audio and clear the buffer.
        
        Returns:
            Buffered audio data as bytes
        """
        audio_data = bytes(self.buffer)
        self.clear()
        
        logger.debug(f"Retrieved {len(audio_data)} bytes from buffer")
        return audio_data
    
    def clear(self):
        """Clear the buffer"""
        self.buffer.clear()
        self.frames.clear()
        logger.debug("Buffer cleared")
    
    def get_buffer_duration(self) -> float:
        """
        Get current buffer duration in seconds.
        
        Returns:
            Duration in seconds
        """
        # 2 bytes per sample (16-bit audio)
        samples = len(self.buffer) // 2
        return samples / self.sample_rate
    
    def is_empty(self) -> bool:
        """Check if buffer is empty"""
        return len(self.buffer) == 0
    
    def get_buffer_size(self) -> int:
        """Get buffer size in bytes"""
        return len(self.buffer)
