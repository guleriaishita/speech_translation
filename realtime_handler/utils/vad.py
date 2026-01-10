"""
Voice Activity Detection (VAD) module using webrtcvad.
Detects speech presence in audio to determine when to process buffered audio.
"""

import logging
try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False


logger = logging.getLogger(__name__)


class VAD:
    """
    Voice Activity Detection using WebRTC VAD.
    
    Detects speech in audio frames to determine when a user has stopped speaking.
    """
    
    def __init__(self, aggressiveness: int = 2, sample_rate: int = 16000):
        """
        Initialize VAD.
        
        Args:
            aggressiveness: VAD aggressiveness level (0-3)
                0: Least aggressive (more speech detected)
                3: Most aggressive (less speech detected)
                Recommended: 2 for balanced performance
            sample_rate: Audio sample rate in Hz (8000, 16000, 32000, or 48000)
        """
        if not WEBRTCVAD_AVAILABLE:
            raise ImportError(
                "webrtcvad library not installed. "
                "Install with: pip install webrtcvad==2.0.10"
            )
        
        if aggressiveness not in range(4):
            raise ValueError("Aggressiveness must be 0-3")
        
        if sample_rate not in [8000, 16000, 32000, 48000]:
            raise ValueError("Sample rate must be 8000, 16000, 32000, or 48000 Hz")
        
        self.vad = webrtcvad.Vad(aggressiveness)
        self.sample_rate = sample_rate
        self.aggressiveness = aggressiveness
        
        # Frame duration in milliseconds (10, 20, or 30)
        self.frame_duration_ms = 30
        self.frame_size = int(sample_rate * self.frame_duration_ms / 1000) * 2  # 2 bytes per sample (16-bit)
        
        logger.info(
            f"Initialized VAD: aggressiveness={aggressiveness}, "
            f"sample_rate={sample_rate}Hz, frame_duration={self.frame_duration_ms}ms"
        )
    
    def is_speech(self, frame: bytes) -> bool:
        """
        Check if a single frame contains speech.
        
        Args:
            frame: Audio frame (must be correct size for sample rate and duration)
            
        Returns:
            True if speech is detected, False otherwise
        """
        if len(frame) != self.frame_size:
            # Pad or truncate frame to correct size
            if len(frame) < self.frame_size:
                frame = frame + b'\x00' * (self.frame_size - len(frame))
            else:
                frame = frame[:self.frame_size]
        
        try:
            return self.vad.is_speech(frame, self.sample_rate)
        except Exception as e:
            logger.warning(f"VAD error: {e}")
            return False
    
    def detect_speech_end(
        self, 
        frames: list, 
        silence_threshold: int = 10
    ) -> bool:
        """
        Detect if speech has ended by analyzing multiple frames.
        
        Args:
            frames: List of audio frames
            silence_threshold: Number of consecutive silent frames to consider speech ended
            
        Returns:
            True if speech has ended (silence detected), False otherwise
        """
        if len(frames) < silence_threshold:
            return False
        
        # Check last N frames
        recent_frames = frames[-silence_threshold:]
        silent_count = sum(1 for frame in recent_frames if not self.is_speech(frame))
        
        # If most recent frames are silent, speech has ended
        return silent_count >= silence_threshold * 0.8  # 80% threshold
    
    def split_into_frames(self, audio_data: bytes) -> list:
        """
        Split audio data into frames of correct size.
        
        Args:
            audio_data: Raw audio bytes (16-bit PCM)
            
        Returns:
            List of audio frames
        """
        frames = []
        for i in range(0, len(audio_data), self.frame_size):
            frame = audio_data[i:i + self.frame_size]
            if len(frame) == self.frame_size:  # Only add complete frames
                frames.append(frame)
        
        return frames


def detect_speech_end(
    audio_frames: list,
    sample_rate: int = 16000,
    aggressiveness: int = 2,
    silence_threshold: int = 10
) -> bool:
    """
    Convenience function to detect if speech has ended.
    
    Args:
        audio_frames: List of audio frames (bytes)
        sample_rate: Sample rate in Hz
        aggressiveness: VAD aggressiveness (0-3)
        silence_threshold: Number of silent frames to consider speech ended
        
    Returns:
        True if speech has ended
    """
    vad = VAD(aggressiveness=aggressiveness, sample_rate=sample_rate)
    return vad.detect_speech_end(audio_frames, silence_threshold=silence_threshold)
