"""
Session Management Models
Handles rooms, participants, and message history for real-time translation sessions.
"""

import uuid
import secrets
from django.db import models
from django.utils import timezone


def generate_room_code():
    """Generate a unique 6-character room code"""
    return secrets.token_urlsafe(6)[:6].upper()


class Session(models.Model):
    """Translation session/room"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_code = models.CharField(max_length=10, unique=True, default=generate_room_code, db_index=True)
    sender_name = models.CharField(max_length=100, default="Anonymous")
    source_language = models.CharField(max_length=10, default='en')
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_code', 'is_active']),
        ]
    
    def __str__(self):
        return f"Session {self.room_code} ({self.sender_name})"
    
    def end_session(self):
        """Mark session as ended"""
        self.is_active = False
        self.ended_at = timezone.now()
        self.save()


class Participant(models.Model):
    """Participant in a translation session"""
    
    ROLE_SENDER = 'sender'
    ROLE_RECEIVER = 'receiver'
    
    ROLE_CHOICES = [
        (ROLE_SENDER, 'Sender'),
        (ROLE_RECEIVER, 'Receiver'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=100, default="Anonymous")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_RECEIVER)
    target_language = models.CharField(max_length=10)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # WebSocket connection tracking
    channel_name = models.CharField(max_length=255, blank=True)
    
    class Meta:
        ordering = ['joined_at']
        indexes = [
            models.Index(fields=['session', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.role}) in {self.session.room_code}"
    
    def leave(self):
        """Mark participant as having left"""
        self.is_active = False
        self.left_at = timezone.now()
        self.save()


class SessionMessage(models.Model):
    """Message sent in a session"""
    
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    
    STATUS_CHOICES = [
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(Participant, on_delete=models.SET_NULL, null=True, related_name='sent_messages')
    
    # Audio files
    original_audio = models.FileField(upload_to='session_audio/original/', null=True, blank=True)
    
    # Transcription and translation
    transcription = models.TextField(blank=True)
    
    # Processing status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    error_message = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'created_at']),
        ]
    
    def __str__(self):
        return f"Message in {self.session.room_code} at {self.created_at}"


class Translation(models.Model):
    """Per-language translation of a message"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(SessionMessage, on_delete=models.CASCADE, related_name='translations')
    target_language = models.CharField(max_length=10)
    translated_text = models.TextField()
    translated_audio = models.FileField(upload_to='session_audio/translated/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [['message', 'target_language']]
        ordering = ['created_at']
    
    def __str__(self):
        return f"Translation to {self.target_language} for message {self.message.id}"
