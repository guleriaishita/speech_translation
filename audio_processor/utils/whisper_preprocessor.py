import os
import subprocess
from audio_processor.utils.audio_converter import (
    convert_to_wav,
    normalize_audio
)


class AudioPreprocessingError(Exception):
    pass


def preprocess_for_whisper(input_path: str) -> str:
    """
    Full preprocessing pipeline for Whisper:
    - Convert to WAV 16kHz mono
    - Normalize volume
    - Trim silence
    - Validate output
    """
    if not os.path.exists(input_path):
        raise AudioPreprocessingError("Input audio does not exist")

    wav_path = input_path.replace(".wav", "_16k.wav")

    # 1. Convert to WAV 16kHz mono
    convert_to_wav(input_path, wav_path)

    # 2. Normalize audio
    normalized_path = normalize_audio(wav_path)

    # 3. Trim silence (start & end)
    trimmed_path = normalized_path.replace(".wav", "_trimmed.wav")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", normalized_path,
        "-af", "silenceremove=start_periods=1:start_silence=0.5:start_threshold=-50dB:"
               "stop_periods=1:stop_silence=0.5:stop_threshold=-50dB",
        trimmed_path
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError:
        raise AudioPreprocessingError("Failed to trim silence")

    # 4. Final validation
    if os.path.getsize(trimmed_path) == 0:
        raise AudioPreprocessingError("Processed audio is empty or corrupted")

    return trimmed_path
