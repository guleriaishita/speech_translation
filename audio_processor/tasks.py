"""
Celery tasks for asynchronous audio processing.
Handles the complete workflow: upload -> transcribe -> translate -> TTS -> download
"""

import os
import logging
from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
import redis

from audio_processor.models import AudioFile
from audio_processor.utils.audio_converter import convert_to_wav
from audio_processor.utils.whisper_client import WhisperClient
from audio_processor.utils.translator import get_translator
from audio_processor.utils.tts_client import get_tts_client


logger = logging.getLogger(__name__)

# Redis connection for progress tracking
try:
    redis_client = redis.Redis(
        host=os.getenv('REDIS_HOST', 'localhost'),
        port=int(os.getenv('REDIS_PORT', 6379)),
        db=int(os.getenv('REDIS_DB', 0)),
        decode_responses=True
    )
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


def update_progress(task_id: str, progress: int, status_message: str = ""):
    """
    Update task progress in Redis.
    
    Args:
        task_id: Celery task ID
        progress: Progress percentage (0-100)
        status_message: Optional status message
    """
    if redis_client:
        try:
            key = f"task_progress:{task_id}"
            redis_client.hset(key, mapping={
                'progress': progress,
                'status': status_message,
                'updated_at': timezone.now().isoformat()
            })
            redis_client.expire(key, 3600)  # Expire after 1 hour
        except Exception as e:
            logger.warning(f"Failed to update progress in Redis: {e}")


def get_progress(task_id: str) -> dict:
    """
    Get task progress from Redis.
    
    Args:
        task_id: Celery task ID
        
    Returns:
        Dictionary with progress, status, and updated_at
    """
    if redis_client:
        try:
            key = f"task_progress:{task_id}"
            data = redis_client.hgetall(key)
            if data:
                return {
                    'progress': int(data.get('progress', 0)),
                    'status': data.get('status', ''),
                    'updated_at': data.get('updated_at', '')
                }
        except Exception as e:
            logger.warning(f"Failed to get progress from Redis: {e}")
    
    return {'progress': 0, 'status': 'unknown', 'updated_at': ''}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_audio_file(self, audio_id: str):
    """
    Process audio file: transcribe -> translate -> TTS.
    
    Args:
        audio_id: UUID of AudioFile instance
        
    Returns:
        Dictionary with success status and results
    """
    task_id = self.request.id
    audio_instance = None
    temp_files = []  # Track temp files for cleanup
    
    try:
        # ====================================================================
        # STEP 1: Load AudioFile from Database (10%)
        # ====================================================================
        logger.info(f"[Task {task_id}] Starting processing for audio {audio_id}")
        update_progress(task_id, 10, "Loading audio file...")
        
        try:
            audio_instance = AudioFile.objects.get(id=audio_id)
            audio_instance.status = AudioFile.STATUS_PROCESSING
            audio_instance.celery_task_id = task_id
            audio_instance.save()
        except AudioFile.DoesNotExist:
            logger.error(f"AudioFile {audio_id} not found")
            raise Exception(f"AudioFile {audio_id} does not exist")
        
        original_file_path = audio_instance.original_file.path
        
        # ====================================================================
        # STEP 2: Convert to WAV Format (20%)
        # ====================================================================
        update_progress(task_id, 20, "Converting audio format...")
        logger.info(f"[Task {task_id}] Converting to WAV format")
        
        wav_path = original_file_path.replace(
            os.path.splitext(original_file_path)[1], 
            '_converted.wav'
        )
        temp_files.append(wav_path)
        
        try:
            convert_to_wav(original_file_path, wav_path)
            logger.info(f"[Task {task_id}] Converted to WAV: {wav_path}")
        except Exception as e:
            logger.error(f"[Task {task_id}] Audio conversion failed: {e}")
            raise Exception(f"Audio conversion failed: {e}")
        
        # ====================================================================
        # STEP 3: Transcribe with Whisper (50%)
        # ====================================================================
        update_progress(task_id, 30, "Transcribing audio...")
        logger.info(f"[Task {task_id}] Starting transcription")
        
        try:
            whisper_model = os.getenv('WHISPER_MODEL', 'base')
            whisper_device = os.getenv('WHISPER_DEVICE', 'cpu')
            
            whisper_client = WhisperClient(
                model_name=whisper_model,
                device=whisper_device
            )
            
            # Detect language if not provided or set to 'auto'
            if audio_instance.source_language == 'auto':
                detected_lang = whisper_client.detect_language(wav_path)
                audio_instance.source_language = detected_lang
                logger.info(f"[Task {task_id}] Detected language: {detected_lang}")
            
            # Transcribe
            transcription = whisper_client.transcribe(
                wav_path,
                language=audio_instance.source_language
            )
            
            audio_instance.transcription = transcription
            audio_instance.save()
            
            logger.info(
                f"[Task {task_id}] Transcription complete: "
                f"{len(transcription)} characters"
            )
            update_progress(task_id, 50, "Transcription complete")
            
        except Exception as e:
            logger.error(f"[Task {task_id}] Transcription failed: {e}")
            raise Exception(f"Transcription failed: {e}")
        
        # ====================================================================
        # STEP 4: Translate Transcription (70%)
        # ====================================================================
        update_progress(task_id, 60, "Translating text...")
        logger.info(f"[Task {task_id}] Starting translation")
        
        try:
            translation_service = os.getenv('TRANSLATION_SERVICE', 'google')
            translator = get_translator(translation_service)
            
            translation = translator.translate(
                transcription,
                source_lang=audio_instance.source_language,
                target_lang=audio_instance.target_language
            )
            
            audio_instance.translation = translation
            audio_instance.save()
            
            logger.info(
                f"[Task {task_id}] Translation complete: "
                f"{audio_instance.source_language} -> {audio_instance.target_language}"
            )
            update_progress(task_id, 70, "Translation complete")
            
        except Exception as e:
            logger.error(f"[Task {task_id}] Translation failed: {e}")
            raise Exception(f"Translation failed: {e}")
        
        # ====================================================================
        # STEP 5: Generate TTS Audio (90%)
        # ====================================================================
        update_progress(task_id, 80, "Generating translated audio...")
        logger.info(f"[Task {task_id}] Starting TTS synthesis")
        
        try:
            tts_service = os.getenv('TTS_SERVICE', 'gtts')
            tts_client = get_tts_client(tts_service)
            
            # Generate output file path
            output_audio_path = original_file_path.replace(
                os.path.splitext(original_file_path)[1],
                f'_translated_{audio_instance.target_language}.mp3'
            )
            temp_files.append(output_audio_path)
            
            # Synthesize speech
            tts_client.synthesize(
                translation,
                language=audio_instance.target_language,
                output_path=output_audio_path
            )
            
            # Save to model
            with open(output_audio_path, 'rb') as f:
                audio_instance.output_audio.save(
                    os.path.basename(output_audio_path),
                    ContentFile(f.read()),
                    save=True
                )
            
            logger.info(f"[Task {task_id}] TTS synthesis complete")
            update_progress(task_id, 90, "Audio generation complete")
            
        except Exception as e:
            logger.error(f"[Task {task_id}] TTS synthesis failed: {e}")
            raise Exception(f"TTS synthesis failed: {e}")
        
        # ====================================================================
        # STEP 6: Finalize and Update Status (100%)
        # ====================================================================
        update_progress(task_id, 95, "Finalizing...")
        
        audio_instance.status = AudioFile.STATUS_COMPLETED
        audio_instance.completed_at = timezone.now()
        audio_instance.progress = 100
        audio_instance.save()
        
        update_progress(task_id, 100, "Processing complete")
        
        logger.info(f"[Task {task_id}] Processing complete for audio {audio_id}")
        
        # ====================================================================
        # STEP 7: Cleanup Temporary Files
        # ====================================================================
        _cleanup_temp_files(temp_files)
        
        return {
            'success': True,
            'audio_id': str(audio_id),
            'transcription': transcription,
            'translation': translation,
            'output_file': audio_instance.output_audio.url if audio_instance.output_audio else None
        }
        
    except Exception as e:
        # Handle errors
        logger.error(f"[Task {task_id}] Failed: {str(e)}")
        
        if audio_instance:
            audio_instance.status = AudioFile.STATUS_FAILED
            audio_instance.error_message = str(e)
            audio_instance.save()
        
        update_progress(task_id, 0, f"Failed: {str(e)}")
        
        # Cleanup temp files on error
        _cleanup_temp_files(temp_files)
        
        # Retry for transient errors
        if "rate limit" in str(e).lower() or "unavailable" in str(e).lower():
            logger.info(f"[Task {task_id}] Retrying due to transient error...")
            raise self.retry(exc=e)
        
        # Don't retry for permanent errors
        raise e


def _cleanup_temp_files(file_paths: list):
    """
    Clean up temporary files.
    
    Args:
        file_paths: List of file paths to delete
    """
    for filepath in file_paths:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.debug(f"Cleaned up temp file: {filepath}")
        except Exception as e:
            logger.warning(f"Failed to cleanup {filepath}: {e}")


@shared_task
def cleanup_old_files(days: int = 7):
    """
    Cleanup old audio files that are older than specified days.
    Run this task periodically via Celery Beat.
    
    Args:
        days: Number of days to keep files
    """
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=days)
    old_files = AudioFile.objects.filter(
        created_at__lt=cutoff_date,
        status=AudioFile.STATUS_COMPLETED
    )
    
    deleted_count = 0
    for audio_file in old_files:
        try:
            # Delete physical files
            if audio_file.original_file:
                audio_file.original_file.delete()
            if audio_file.converted_file:
                audio_file.converted_file.delete()
            if audio_file.output_audio:
                audio_file.output_audio.delete()
            
            # Delete database record
            audio_file.delete()
            deleted_count += 1
            
        except Exception as e:
            logger.error(f"Failed to delete audio file {audio_file.id}: {e}")
    
    logger.info(f"Cleaned up {deleted_count} old audio files")
    return {'deleted_count': deleted_count}
