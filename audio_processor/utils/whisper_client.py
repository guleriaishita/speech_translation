import whisper
import torch
from typing import Dict, Any


class WhisperClient:
    """
    Wrapper around OpenAI Whisper for transcription & language detection
    """

    def __init__(self, model_name: str = "base", device: str = "cpu"):
        """
        model_name: tiny | base | small | medium | large
        device: cpu | cuda
        """
        self.model_name = model_name
        self.device = device

        if device == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but not available")

        self.model = whisper.load_model(model_name, device=device)

    # ---------------- BASIC TRANSCRIPTION ---------------- #

    def transcribe(self, audio_path: str, language: str = None) -> str:
        """
        Transcribe audio to plain text.
        """
        result = self.model.transcribe(
            audio_path,
            language=language,
            fp16=self.device == "cuda"
        )
        return result.get("text", "").strip()

    # ---------------- LANGUAGE DETECTION ---------------- #

    def detect_language(self, audio_path: str) -> str:
        """
        Auto-detect spoken language.
        """
        audio = whisper.load_audio(audio_path)
        audio = whisper.pad_or_trim(audio)

        mel = whisper.log_mel_spectrogram(audio).to(self.model.device)
        _, probs = self.model.detect_language(mel)

        return max(probs, key=probs.get)

    # ---------------- TIMESTAMPED TRANSCRIPTION ---------------- #

    def transcribe_with_timestamps(self, audio_path: str) -> Dict[str, Any]:
        """
        Transcribe with segment-level timestamps.
        """
        result = self.model.transcribe(
            audio_path,
            word_timestamps=True,
            fp16=self.device == "cuda"
        )

        return {
            "text": result.get("text", "").strip(),
            "segments": result.get("segments", [])
        }
