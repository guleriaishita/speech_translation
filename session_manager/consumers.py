"""
Session-based WebSocket consumer for room broadcasting.
Extends the original consumer to support multi-receiver translation.
"""

import os
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import tempfile
import base64

from audio_processor.utils.whisper_client import WhisperClient
from audio_processor.utils.translator import get_translator
from audio_processor.utils.tts_client import get_tts_client
from session_manager.models import Session, Participant, SessionMessage, Translation

logger = logging.getLogger(__name__)


class SessionConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for session-based real-time translation.
    
    Supports:
    - Room-based communication
    - Sender broadcasts to all receivers
    - Per-receiver language translation
    - Message history
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.room_code = None
        self.room_group_name = None
        self.participant_id = None
        self.participant = None
        self.session = None
        self.role = None
        
        # Translation services (shared for sender)
        self.whisper_client = None
        self.temp_dir = tempfile.gettempdir()
    
    async def connect(self):
        """Handle WebSocket connection to a session"""
        
        try:
            # Get room code from URL
            self.room_code = self.scope['url_route']['kwargs']['room_code'].upper()
            self.room_group_name = f'session_{self.room_code}'
            
            # Get participant_id from query string
            query_string = self.scope.get('query_string', b'').decode()
            params = dict(param.split('=') for param in query_string.split('&') if '=' in param)
            self.participant_id = params.get('participant_id')
            
            if not self.participant_id:
                logger.error(f"No participant_id provided for room {self.room_code}")
                await self.close()
                return
            
            # Verify participant and session exist
            self.participant = await self.get_participant(self.participant_id, self.room_code)
            if not self.participant:
                logger.error(f"Invalid participant {self.participant_id} for room {self.room_code}")
                await self.close()
                return
            
            self.session = self.participant.session
            self.role = self.participant.role
            
            # Join room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )
            
            # Update participant's channel name
            await self.update_participant_channel(self.participant_id, self.channel_name)
            
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connected',
                'room_code': self.room_code,
                'participant_id': self.participant_id,
                'role': self.role,
                'message': f'Connected to session {self.room_code}'
            }))
            
            # Notify room about new participant
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_joined',
                    'participant_name': self.participant.name,
                    'participant_role': self.role
                }
            )
            
            # Send message history to receiver
            if self.role == 'receiver':
                await self.send_message_history()
            
            logger.info(f"[{self.room_code}] {self.participant.name} ({self.role}) connected")
            
        except Exception as e:
            logger.error(f"Error during connect: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle disconnection"""
        
        if self.room_group_name:
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Notify room
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'participant_left',
                    'participant_name': self.participant.name if self.participant else 'Unknown'
                }
            )
        
        logger.info(f"[{self.room_code}] Participant disconnected. Code: {close_code}")
    
    async def receive(self, text_data=None, bytes_data=None):
        """Handle incoming messages"""
        
        try:
            if text_data:
                data = json.loads(text_data)
                message_type = data.get('type')
                
                if message_type == 'audio_file':
                    # Sender uploads audio file (base64 encoded)
                    await self.handle_audio_file(data)
                
                elif message_type == 'get_history':
                    # Request message history
                    await self.send_message_history()
            
            elif bytes_data:
                # Live audio streaming (sender only)
                if self.role == 'sender':
                   await self.handle_audio_stream(bytes_data)
                
        except Exception as e:
            logger.error(f"[{self.room_code}] Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e)
            }))
    
    async def handle_audio_file(self, data):
        """Handle uploaded audio file from sender"""
        
        if self.role != 'sender':
            return
        
        try:
            # Decode base64 audio
            audio_base64 = data.get('audio_data')
            audio_bytes = base64.b64decode(audio_base64)
            
            # Save to temp file
            temp_path = os.path.join(
                self.temp_dir,
                f"session_{self.room_code}_{asyncio.get_event_loop().time()}.wav"
            )
            
            with open(temp_path, 'wb') as f:
                f.write(audio_bytes)
            
            # Notify room: processing started
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'processing_started',
                    'sender_name': self.participant.name
                }
            )
            
            # Process audio
            await self.process_and_broadcast(temp_path)
            
            # Cleanup
            if os.path.exists(temp_path):
                os.remove(temp_path)
            
        except Exception as e:
            logger.error(f"[{self.room_code}] Error handling audio file: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Failed to process audio file'
            }))
    
    async def handle_audio_stream(self, audio_data):
        """Handle live audio streaming (future enhancement)"""
        # For now, buffer and process similar to file upload
        # In future, implement real-time VAD and streaming
        pass
    
    async def process_and_broadcast(self, audio_path):
        """Process audio and broadcast translations to all receivers"""
        
        try:
            # Step 1: Transcribe
            transcription = await self.transcribe_audio(audio_path, self.session.source_language)
            
            if not transcription:
                await self.send(text_data=json.dumps({
                    'type': 'info',
                    'message': 'No speech detected'
                }))
                return
            
            # Create session message
            message = await self.create_session_message(transcription, audio_path)
            
            # Get all active receivers
            receivers = await self.get_active_receivers()
            
            # Translate for each unique target language
            target_languages = set(r.target_language for r in receivers)
            
            translations = {}
            for target_lang in target_languages:
                # Translate
                translated_text = await self.translate_text(
                    transcription,
                    self.session.source_language,
                    target_lang
                )
                
                # Generate TTS
                tts_path = os.path.join(
                    self.temp_dir,
                    f"tts_{message.id}_{target_lang}.mp3"
                )
                
                await self.synthesize_audio(translated_text, target_lang, tts_path)
                
                # Save translation to database
                await self.save_translation(message, target_lang, translated_text, tts_path)
                
                # Read audio file as base64
                with open(tts_path, 'rb') as f:
                    audio_base64 = base64.b64encode(f.read()).decode('utf-8')
                
                translations[target_lang] = {
                    'text': translated_text,
                    'audio': audio_base64
                }
                
                # Cleanup
                if os.path.exists(tts_path):
                    os.remove(tts_path)
            
            # Broadcast to all receivers
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'new_translation',
                    'message_id': str(message.id),
                    'transcription': transcription,
                    'translations': translations,
                    'sender_name': self.participant.name
                }
            )
            
            # Mark message as completed
            await self.mark_message_completed(message.id)
            
            logger.info(f"[{self.room_code}] Message broadcast to {len(receivers)} receivers")
            
        except Exception as e:
            logger.error(f"[{self.room_code}] Error processing audio: {e}")
            raise
    
    # Channel layer message handlers
    
    async def participant_joined(self, event):
        """Notify client about new participant"""
        await self.send(text_data=json.dumps({
            'type': 'participant_joined',
            'participant_name': event['participant_name'],
            'role': event['participant_role']
        }))
    
    async def participant_left(self, event):
        """Notify client about participant leaving"""
        await self.send(text_data=json.dumps({
            'type': 'participant_left',
            'participant_name': event['participant_name']
        }))
    
    async def processing_started(self, event):
        """Notify clients that processing started"""
        await self.send(text_data=json.dumps({
            'type': 'processing_started',
            'sender_name': event['sender_name']
        }))
    
    async def new_translation(self, event):
        """Send new translation to receiver"""
        
        logger.info(f"[{self.room_code}] new_translation handler called, role={self.role}")
        
        # Only send to receiver
        if self.role != 'receiver':
            logger.debug(f"[{self.room_code}] Skipping - not a receiver")
            return
        
        # Get translation for this receiver's language
        target_lang = self.participant.target_language
        translation_data = event['translations'].get(target_lang)
        
        logger.info(f"[{self.room_code}] Receiver target_lang={target_lang}, has_translation={translation_data is not None}")
        
        if translation_data:
            message_to_send = {
                'type': 'new_message',
                'message_id': event['message_id'],
                'sender_name': event['sender_name'],
                'transcription': event['transcription'],
                'translation': translation_data['text'],
                'audio': translation_data['audio']
            }
            await self.send(text_data=json.dumps(message_to_send))
            logger.info(f"[{self.room_code}] Sent new_message to receiver")
        else:
            logger.warning(f"[{self.room_code}] No translation for target_lang={target_lang}")

    
    # Database operations
    
    @database_sync_to_async
    def get_participant(self, participant_id, room_code):
        """Get participant from database"""
        try:
            return Participant.objects.select_related('session').get(
                id=participant_id,
                session__room_code=room_code,
                is_active=True
            )
        except Participant.DoesNotExist:
            return None
    
    @database_sync_to_async
    def update_participant_channel(self, participant_id, channel_name):
        """Update participant's channel name"""
        Participant.objects.filter(id=participant_id).update(channel_name=channel_name)
    
    @database_sync_to_async
    def get_active_receivers(self):
        """Get all active receivers in this session"""
        return list(Participant.objects.filter(
            session=self.session,
            role='receiver',
            is_active=True
        ))
    
    @database_sync_to_async
    def create_session_message(self, transcription, audio_path):
        """Create a new session message"""
        from django.core.files import File
        
        message = SessionMessage.objects.create(
            session=self.session,
            sender=self.participant,
            transcription=transcription,
            status='processing'
        )
        
        # Save audio file
        with open(audio_path, 'rb') as f:
            message.original_audio.save(f'msg_{message.id}.wav', File(f), save=True)
        
        return message
    
    @database_sync_to_async
    def save_translation(self, message, target_lang, text, audio_path):
        """Save translation to database"""
        from django.core.files import File
        
        translation = Translation.objects.create(
            message=message,
            target_language=target_lang,
            translated_text=text
        )
        
        # Save audio file
        with open(audio_path, 'rb') as f:
            translation.translated_audio.save(f'trans_{translation.id}.mp3', File(f), save=True)
        
        return translation
    
    @database_sync_to_async
    def mark_message_completed(self, message_id):
        """Mark message as completed"""
        from django.utils import timezone
        SessionMessage.objects.filter(id=message_id).update(
            status='completed',
            completed_at=timezone.now()
        )
    
    async def send_message_history(self):
        """Send message history to receiver"""
        messages = await self.get_message_history()
        
        for msg in messages:
            translation = await self.get_translation(msg.id, self.participant.target_language)
            
            if translation:
                await self.send(text_data=json.dumps({
                    'type': 'history_message',
                    'message_id': str(msg.id),
                    'sender_name': msg.sender.name if msg.sender else 'Unknown',
                    'transcription': msg.transcription,
                    'translation': translation.translated_text,
                    'audio_url': translation.translated_audio.url if translation.translated_audio else None,
                    'created_at': msg.created_at.isoformat()
                }))
    
    @database_sync_to_async
    def get_message_history(self):
        """Get message history for this session"""
        return list(SessionMessage.objects.filter(
            session=self.session,
            status='completed'
        ).order_by('created_at').select_related('sender'))
    
    @database_sync_to_async
    def get_translation(self, message_id, target_lang):
        """Get translation for a message"""
        try:
            return Translation.objects.get(
                message_id=message_id,
                target_language=target_lang
            )
        except Translation.DoesNotExist:
            return None
    
    # Translation services
    
    async def transcribe_audio(self, audio_path, language):
        """Transcribe audio using Whisper"""
        if not self.whisper_client:
            whisper_model = os.getenv('WHISPER_MODEL', 'base')
            whisper_device = os.getenv('WHISPER_DEVICE', 'cpu')
            self.whisper_client = await asyncio.to_thread(
                WhisperClient,
                model_name=whisper_model,
                device=whisper_device
            )
        
        return await asyncio.to_thread(
            self.whisper_client.transcribe,
            audio_path,
            language=language
        )
    
    async def translate_text(self, text, source_lang, target_lang):
        """Translate text"""
        translation_service = os.getenv('TRANSLATION_SERVICE', 'google')
        translator = await asyncio.to_thread(get_translator, translation_service)
        
        return await asyncio.to_thread(
            translator.translate,
            text,
            source_lang,
            target_lang
        )
    
    async def synthesize_audio(self, text, language, output_path):
        """Synthesize speech"""
        tts_service = os.getenv('TTS_SERVICE', 'gtts')
        tts_client = await asyncio.to_thread(get_tts_client, tts_service)
        
        await asyncio.to_thread(
            tts_client.synthesize,
            text,
            language,
            output_path
        )
