"""
REST API views for audio file upload, status checking, and download.
Handles the file upload workflow with Celery task integration.
"""

import os
import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from celery.result import AsyncResult

from audio_processor.models import AudioFile
from audio_processor.serializers import AudioFileSerializer
from audio_processor.tasks import process_audio_file, get_progress


logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class AudioUploadView(APIView):
    """
    Handle audio file uploads.
    
    POST /api/audio/upload/
    
    Request:
        - original_file: Audio file (multipart/form-data)
        - source_language: Source language code (or 'auto' for detection)
        - target_language: Target language code
    
    Response:
        - 201: Created with task_id and audio_id
        - 400: Validation error
    """
    
    parser_classes = [MultiPartParser, FormParser]
    
    def post(self, request):
        """Create new audio file and trigger processing task"""
        
        serializer = AudioFileSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.warning(f"Validation failed: {serializer.errors}")
            return Response(
                {
                    'error': 'Validation failed',
                    'details': serializer.errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Save audio file
        audio_instance = serializer.save()
        logger.info(f"Created audio file: {audio_instance.id}")
        
        # Trigger Celery task for processing
        task = process_audio_file.delay(str(audio_instance.id))
        
        # Update audio instance with task ID
        audio_instance.celery_task_id = task.id
        audio_instance.save()
        
        logger.info(
            f"Triggered processing task {task.id} for audio {audio_instance.id}"
        )
        
        return Response(
            {
                'success': True,
                'message': 'Audio file uploaded successfully',
                'audio_id': str(audio_instance.id),
                'task_id': task.id,
                'status': audio_instance.status,
                'source_language': audio_instance.source_language,
                'target_language': audio_instance.target_language
            },
            status=status.HTTP_201_CREATED
        )


@method_decorator(csrf_exempt, name='dispatch')
class TaskStatusView(APIView):
    """
    Check the status of a processing task.
    
    GET /api/audio/status/<task_id>/
    
    Response:
        - 200: Task status with progress and results
        - 404: Task not found
    """
    
    def get(self, request, task_id):
        """Get task status and progress"""
        
        try:
            # Get Celery task result
            task_result = AsyncResult(task_id)
            
            # Get progress from Redis
            progress_data = get_progress(task_id)
            
            # Try to find associated AudioFile
            try:
                audio_file = AudioFile.objects.get(celery_task_id=task_id)
                audio_id = str(audio_file.id)
                audio_status = audio_file.status
                transcription = audio_file.transcription
                translation = audio_file.translation
                error_message = audio_file.error_message
                output_file = audio_file.output_audio.url if audio_file.output_audio else None
            except AudioFile.DoesNotExist:
                audio_id = None
                audio_status = None
                transcription = None
                translation = None
                error_message = None
                output_file = None
            
            response_data = {
                'task_id': task_id,
                'state': task_result.state,
                'progress': progress_data.get('progress', 0),
                'status_message': progress_data.get('status', ''),
                'audio_id': audio_id,
                'audio_status': audio_status,
            }
            
            # Add results if task is complete
            if task_result.ready():
                if task_result.successful():
                    result = task_result.result
                    response_data.update({
                        'success': True,
                        'transcription': transcription,
                        'translation': translation,
                        'output_file': output_file
                    })
                else:
                    response_data.update({
                        'success': False,
                        'error': str(task_result.result) if task_result.result else error_message
                    })
            
            logger.info(f"Status check for task {task_id}: {task_result.state}")
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error checking task {task_id}: {e}")
            return Response(
                {
                    'error': 'Failed to retrieve task status',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class DownloadView(APIView):
    """
    Download translated audio file.
    
    GET /api/audio/download/<audio_id>/
    
    Response:
        - 200: Audio file stream
        - 404: File not found or not ready
    """
    
    def get(self, request, audio_id):
        """Download translated audio file"""
        
        try:
            # Get audio file instance
            audio_file = get_object_or_404(AudioFile, id=audio_id)
            
            # Check if processing is complete
            if audio_file.status != AudioFile.STATUS_COMPLETED:
                return Response(
                    {
                        'error': 'Audio file is not ready for download',
                        'status': audio_file.status,
                        'message': 'Please wait for processing to complete'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check if output file exists
            if not audio_file.output_audio:
                return Response(
                    {
                        'error': 'Output audio file not found',
                        'message': 'Processing may have failed'
                    },
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Serve the file
            file_path = audio_file.output_audio.path
            
            if not os.path.exists(file_path):
                logger.error(f"File not found on disk: {file_path}")
                raise Http404("Audio file not found on disk")
            
            # Generate filename for download
            filename = f"translated_{audio_file.target_language}_{audio_file.id}.mp3"
            
            # Open and serve file
            response = FileResponse(
                open(file_path, 'rb'),
                content_type='audio/mpeg'
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Content-Length'] = os.path.getsize(file_path)
            
            logger.info(f"Serving download for audio {audio_id}")
            
            return response
            
        except Http404:
            raise
        except Exception as e:
            logger.error(f"Error serving download for {audio_id}: {e}")
            return Response(
                {
                    'error': 'Failed to serve file',
                    'details': str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(csrf_exempt, name='dispatch')
class AudioDetailView(APIView):
    """
    Get details of an audio file.
    
    GET /api/audio/detail/<audio_id>/
    
    Response:
        - 200: Audio file details
        - 404: Not found
    """
    
    def get(self, request, audio_id):
        """Get audio file details"""
        
        audio_file = get_object_or_404(AudioFile, id=audio_id)
        serializer = AudioFileSerializer(audio_file)
        
        # Add additional fields
        response_data = serializer.data
        response_data.update({
            'transcription': audio_file.transcription,
            'translation': audio_file.translation,
            'progress': audio_file.progress,
            'error_message': audio_file.error_message,
            'output_audio_url': audio_file.output_audio.url if audio_file.output_audio else None
        })
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    def delete(self, request, audio_id):
        """Delete an audio file"""
        
        audio_file = get_object_or_404(AudioFile, id=audio_id)
        
        # Delete physical files
        try:
            if audio_file.original_file:
                audio_file.original_file.delete()
            if audio_file.converted_file:
                audio_file.converted_file.delete()
            if audio_file.output_audio:
                audio_file.output_audio.delete()
        except Exception as e:
            logger.warning(f"Error deleting files for {audio_id}: {e}")
        
        # Delete database record
        audio_file.delete()
        
        logger.info(f"Deleted audio file {audio_id}")
        
        return Response(
            {'success': True, 'message': 'Audio file deleted'},
            status=status.HTTP_200_OK
        )
