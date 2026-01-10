"""
WebSocket consumer for real-time audio translation.
Handles streaming audio, transcription, translation, and TTS synthesis.
"""

import os
import json
import asyncio
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import tempfile

from audio_processor.utils.whisper_client import WhisperClient
from audio_processor.utils.translator import get_translator
from audio_processor.utils.tts_client import get_tts_client
from realtime_handler.utils.audio_buffer import AudioBuffer


logger = logging.getLogger(__name__)


class TranslationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time translation.
    
    Flow:
    1. Client connects
    2. Client sends audio chunks
    3. Audio buffered until speech pause detected (VAD)
    4. Process: Transcribe -> Translate -> TTS
    5. Send translated audio back to client
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Per-connection state
        self.audio_buffer = None
        self.whisper_client = None
        self.translator = None
        self.tts_client = None
        self.source_language = None
        self.target_language = None
        self.temp_dir = tempfile.gettempdir()
        self.connection_id = None
        self.is_processing = False
    
    async def connect(self):
        """Handle WebSocket connection"""
        
        try:
            # Generate connection ID
            import uuid
            self.connection_id = str(uuid.uuid4())[:8]
            
            logger.info(f"[{self.connection_id}] WebSocket connection initiated")
            
            # TODO: Check connection limits (implemented in middleware)
            # For now, accept all connections
            
            await self.accept()
            
            # Send ready message
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'connection_id': self.connection_id,
                'message': 'WebSocket connected. Ready to receive audio.',
                'status': 'ready'
            }))
            
            logger.info(f"[{self.connection_id}] Connection established")
            
        except Exception as e:
            logger.error(f"Error during connection: {e}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        
        logger.info(
            f"[{self.connection_id}] WebSocket disconnected. Code: {close_code}"
        )
        
        # Cleanup resources
        await self._cleanup()
    
    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle incoming messages from WebSocket.
        
        Text messages: Configuration (languages, settings)
        Binary messages: Audio chunks
        """
        
        try:
            # Handle text messages (configuration)
            if text_data:
                await self._handle_text_message(text_data)
            
            # Handle binary messages (audio data)
            elif bytes_data:
                await self._handle_audio_chunk(bytes_data)
                
        except Exception as e:
            logger.error(f"[{self.connection_id}] Error in receive: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e),
                'message': 'An error occurred while processing your request'
            }))
    
    async def _handle_text_message(self, text_data):
        """Handle text messages (configuration)"""
        
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'configure':
                # Initialize services with provided configuration
                self.source_language = data.get('source_language', 'en')
                self.target_language = data.get('target_language', 'es')
                
                # Initialize services
                await self._initialize_services()
                
                await self.send(text_data=json.dumps({
                    'type': 'configured',
                    'source_language': self.source_language,
                    'target_language': self.target_language,
                    'message': 'Configuration applied. Ready to process audio.'
                }))
                
                logger.info(
                    f"[{self.connection_id}] Configured: "
                    f"{self.source_language} -> {self.target_language}"
                )
                
            elif message_type == 'ping':
                # Keepalive ping
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
                
        except json.JSONDecodeError as e:
            logger.error(f"[{self.connection_id}] Invalid JSON: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Invalid JSON format'
            }))
    
    async def _handle_audio_chunk(self, audio_data):
        """Handle incoming audio chunk"""
        
        # Check if services are initialized
        if not self.audio_buffer:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': 'Not configured. Send configuration first.',
                'message': 'Please send configuration message before audio'
            }))
            return
        
        # Prevent concurrent processing
        if self.is_processing:
            logger.debug(f"[{self.connection_id}] Already processing, queueing chunk")
            # In production, you might want to queue this
            return
        
        # Add chunk to buffer
        self.audio_buffer.add_chunk(audio_data)
        
        # Check if speech is complete (VAD detected pause)
        if self.audio_buffer.is_speech_complete():
            logger.info(f"[{self.connection_id}] Speech segment complete, processing...")
            
            # Process the complete utterance
            await self._process_complete_utterance()
    
    async def _process_complete_utterance(self):
        """Process a complete speech segment"""
        
        self.is_processing = True
        
        try:
            # Get buffered audio
            audio_data = self.audio_buffer.get_audio()
            
            if not audio_data or len(audio_data) < 1000:  # Too short
                logger.warning(f"[{self.connection_id}] Audio segment too short, skipping")
                self.is_processing = False
                return
            
            # Save to temporary file for processing
            temp_audio_path = os.path.join(
                self.temp_dir,
                f"ws_audio_{self.connection_id}_{asyncio.get_event_loop().time()}.wav"
            )
            
            with open(temp_audio_path, 'wb') as f:
                f.write(audio_data)
            
            # Send processing status
            await self.send(text_data=json.dumps({
                'type': 'processing',
                'message': 'Processing audio...'
            }))
            
            # Step 1: Transcribe
            transcription = await self._transcribe_audio(temp_audio_path)
            
            if not transcription:
                await self.send(text_data=json.dumps({
                    'type': 'info',
                    'message': 'No speech detected in audio segment'
                }))
                self.is_processing = False
                return
            
            await self.send(text_data=json.dumps({
                'type': 'transcription',
                'text': transcription,
                'language': self.source_language
            }))
            
            # Step 2: Translate
            translation = await self._translate_text(transcription)
            
            await self.send(text_data=json.dumps({
                'type': 'translation',
                'text': translation,
                'language': self.target_language
            }))
            
            # Step 3: Synthesize TTS
            await self._synthesize_and_send(translation)
            
            # Cleanup temp file
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
            
        except Exception as e:
            logger.error(f"[{self.connection_id}] Error processing utterance: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'error': str(e),
                'message': 'Failed to process audio segment'
            }))
        
        finally:
            self.is_processing = False
    
    async def _initialize_services(self):
        """Initialize translation services"""
        
        # Initialize audio buffer
        self.audio_buffer = AudioBuffer()
        
        # Initialize Whisper (in thread pool to avoid blocking)
        whisper_model = os.getenv('WHISPER_MODEL', 'base')
        whisper_device = os.getenv('WHISPER_DEVICE', 'cpu')
        
        self.whisper_client = await asyncio.to_thread(
            WhisperClient,
            model_name=whisper_model,
            device=whisper_device
        )
        
        # Initialize translator
        translation_service = os.getenv('TRANSLATION_SERVICE', 'google')
        self.translator = await asyncio.to_thread(get_translator, translation_service)
        
        # Initialize TTS
        tts_service = os.getenv('TTS_SERVICE', 'gtts')
        self.tts_client = await asyncio.to_thread(get_tts_client, tts_service)
        
        logger.info(f"[{self.connection_id}] Services initialized")
    
    async def _transcribe_audio(self, audio_path: str) -> str:
        """Transcribe audio using Whisper"""
        
        try:
            transcription = await asyncio.to_thread(
                self.whisper_client.transcribe,
                audio_path,
                language=self.source_language
            )
            
            logger.info(
                f"[{self.connection_id}] Transcribed: {len(transcription)} chars"
            )
            return transcription
            
        except Exception as e:
            logger.error(f"[{self.connection_id}] Transcription error: {e}")
            raise
    
    async def _translate_text(self, text: str) -> str:
        """Translate text"""
        
        try:
            translation = await asyncio.to_thread(
                self.translator.translate,
                text,
                self.source_language,
                self.target_language
            )
            
            logger.info(
                f"[{self.connection_id}] Translated: {len(translation)} chars"
            )
            return translation
            
        except Exception as e:
            logger.error(f"[{self.connection_id}] Translation error: {e}")
            raise
    
    async def _synthesize_and_send(self, text: str):
        """Generate TTS and send audio chunks"""
        
        try:
            # Use streaming synthesis if available
            if hasattr(self.tts_client, 'synthesize_streaming'):
                # Stream audio chunks
                chunk_count = 0
                
                async for audio_chunk in self._stream_tts(text):
                    await self.send(bytes_data=audio_chunk)
                    chunk_count += 1
                
                logger.info(
                    f"[{self.connection_id}] Sent {chunk_count} audio chunks"
                )
                
                # Send completion message
                await self.send(text_data=json.dumps({
                    'type': 'audio_complete',
                    'message': 'Audio synthesis complete'
                }))
            else:
                # Fallback: generate entire file and send
                temp_tts_path = os.path.join(
                    self.temp_dir,
                    f"ws_tts_{self.connection_id}_{asyncio.get_event_loop().time()}.mp3"
                )
                
                await asyncio.to_thread(
                    self.tts_client.synthesize,
                    text,
                    self.target_language,
                    temp_tts_path
                )
                
                # Read and send file
                with open(temp_tts_path, 'rb') as f:
                    audio_data = f.read()
                    await self.send(bytes_data=audio_data)
                
                # Cleanup
                os.remove(temp_tts_path)
                
                await self.send(text_data=json.dumps({
                    'type': 'audio_complete',
                    'message': 'Audio sent'
                }))
                
        except Exception as e:
            logger.error(f"[{self.connection_id}] TTS error: {e}")
            raise
    
    async def _stream_tts(self, text: str):
        """Stream TTS audio chunks"""
        
        # Run streaming synthesis in thread pool
        generator = await asyncio.to_thread(
            self.tts_client.synthesize_streaming,
            text,
            self.target_language
        )
        
        # Yield chunks
        for chunk in generator:
            yield chunk
    
    async def _cleanup(self):
        """Cleanup resources on disconnect"""
        
        try:
            # Clear buffer
            if self.audio_buffer:
                self.audio_buffer.clear()
            
            # Cleanup is mostly automatic with Python GC
            # Services will be cleaned up when consumer is destroyed
            
            logger.info(f"[{self.connection_id}] Resources cleaned up")
            
        except Exception as e:
            logger.warning(f"[{self.connection_id}] Cleanup error: {e}")
