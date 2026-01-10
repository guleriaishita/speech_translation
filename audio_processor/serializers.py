import os
from rest_framework import serializers
from .models import AudioFile
from audio_processor.utils.audio_converter import get_audio_duration
# How This Works in Your API
# REST Upload Flow
# POST /api/audio/upload/
#    ↓
# AudioFileSerializer
#    ↓
# ✔ format check
# ✔ size check
# ✔ duration check
#    ↓
# AudioFile(status=pending)
#    ↓
# Celery task starts processing



# ---------------- CONFIG ---------------- #

ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}
MAX_FILE_SIZE_MB = 25
MAX_DURATION_SEC = 30 * 60  # 30 minutes


# ---------------- SERIALIZER ---------------- #

class AudioFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = AudioFile
        fields = [
            "id",
            "original_file",
            "source_language",
            "target_language",
            "status",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "created_at",
        ]

    # ---------- FIELD LEVEL VALIDATION ---------- #

    def validate_original_file(self, file):
        ext = os.path.splitext(file.name)[1].lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise serializers.ValidationError(
                f"Unsupported file format: {ext}"
            )

        return file

    # ---------- OBJECT LEVEL VALIDATION ---------- #

    def validate(self, attrs):
        file = attrs.get("original_file")

        # File size validation
        file_size_mb = file.size / (1024 * 1024)
        if file_size_mb > MAX_FILE_SIZE_MB:
            raise serializers.ValidationError(
                f"File size exceeds {MAX_FILE_SIZE_MB} MB limit"
            )

        # Duration validation
        try:
            # Check if file has a temporary path (for larger uploads)
            if hasattr(file, 'temporary_file_path'):
                try:
                    file_path = file.temporary_file_path()
                    duration = get_audio_duration(file_path)
                except Exception:
                    # If temporary_file_path exists but can't be read,
                    # fall through to in-memory handling
                    pass
                else:
                    # Successfully got duration from temporary file
                    if duration > MAX_DURATION_SEC:
                        raise serializers.ValidationError(
                            f"Audio duration ({duration:.1f}s) exceeds {MAX_DURATION_SEC}s limit"
                        )
                    return attrs
            
            # Handle in-memory files - write to temporary location
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp:
                for chunk in file.chunks():
                    tmp.write(chunk)
                tmp_path = tmp.name
            
            try:
                duration = get_audio_duration(tmp_path)
                if duration > MAX_DURATION_SEC:
                    raise serializers.ValidationError(
                        f"Audio duration ({duration:.1f}s) exceeds {MAX_DURATION_SEC}s limit"
                    )
            finally:
                # Clean up temporary file
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            
            # Reset file pointer for later use
            file.seek(0)
            
        except serializers.ValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            # For real errors (corrupted files, etc.), allow upload but log
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Could not validate audio duration: {e}")
            # Don't fail the upload - let the processing task handle it


        return attrs
