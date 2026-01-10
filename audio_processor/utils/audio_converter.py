import os
import subprocess
import tempfile
from typing import List



#Upload Flow (REST)
# Upload → validate_audio_file
#       → convert_to_wav
#       → normalize_audio
#       → split_audio_chunks (if needed)
#       → Whisper STT

# Real-Time Flow (WebSocket)
# Mic Chunk → convert_to_wav
#          → normalize_audio
#          → buffer + VAD
#          → Whisper


# ---------------- CONFIG ---------------- #

ALLOWED_FORMATS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
MAX_FILE_SIZE_MB = 25          # Whisper-safe limit
MAX_DURATION_SEC = 30 * 60     # 30 minutes max


# ---------------- EXCEPTIONS ---------------- #

class AudioProcessingError(Exception):
    pass


# ---------------- HELPERS ---------------- #

def _run_ffmpeg(cmd: List[str]) -> None:
    """
    Run ffmpeg command safely.
    """
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise AudioProcessingError(f"FFmpeg failed: {e.stderr.decode()}")


# ---------------- CORE FUNCTIONS ---------------- #

def validate_audio_file(file_path: str) -> None:
    """
    Validate:
    - file exists
    - allowed format
    - file size
    - duration
    """
    if not os.path.exists(file_path):
        raise AudioProcessingError("Audio file does not exist")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in ALLOWED_FORMATS:
        raise AudioProcessingError(f"Unsupported format: {ext}")

    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise AudioProcessingError(
            f"File too large: {file_size_mb:.2f} MB"
        )

    duration = get_audio_duration(file_path)
    if duration > MAX_DURATION_SEC:
        raise AudioProcessingError(
            f"Audio too long: {duration:.2f} seconds"
        )


def convert_to_wav(input_path: str, output_path: str) -> None:
    """
    Convert any audio format to:
    - WAV
    - 16kHz
    - mono
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-ac", "1",            # mono
        "-ar", "16000",        # 16kHz
        "-sample_fmt", "s16",  # 16-bit PCM
        output_path
    ]
    _run_ffmpeg(cmd)


def get_audio_duration(file_path: str) -> float:
    """
    Extract duration using FFmpeg (ffprobe).
    Returns duration in seconds.
    """
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception:
        raise AudioProcessingError("Failed to get audio duration")


def split_audio_chunks(file_path: str, chunk_duration: int) -> List[str]:
    """
    Split long audio into chunks (in seconds).
    Returns list of chunk file paths.
    """
    duration = get_audio_duration(file_path)
    chunks = []

    if duration <= chunk_duration:
        return [file_path]

    base_dir = tempfile.mkdtemp(prefix="audio_chunks_")
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    start = 0
    index = 0

    while start < duration:
        chunk_path = os.path.join(
            base_dir,
            f"{base_name}_chunk_{index}.wav"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i", file_path,
            "-ss", str(start),
            "-t", str(chunk_duration),
            chunk_path
        ]

        _run_ffmpeg(cmd)
        chunks.append(chunk_path)

        start += chunk_duration
        index += 1

    return chunks


def normalize_audio(file_path: str) -> str:
    """
    Normalize volume using FFmpeg loudnorm filter.
    Returns normalized audio file path.
    """
    output_path = file_path.replace(".wav", "_normalized.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", file_path,
        "-af", "loudnorm",
        output_path
    ]

    _run_ffmpeg(cmd)
    return output_path
