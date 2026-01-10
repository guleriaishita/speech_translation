"""
Serializers for session management
"""

from rest_framework import serializers
from .models import Session, Participant, SessionMessage, Translation


class ParticipantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Participant
        fields = ['id', 'name', 'role', 'target_language', 'joined_at', 'is_active']
        read_only_fields = ['id', 'joined_at', 'is_active']


class SessionSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)
    participant_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Session
        fields = [
            'id', 'room_code', 'sender_name', 'source_language',
            'created_at', 'is_active', 'participants', 'participant_count'
        ]
        read_only_fields = ['id', 'room_code', 'created_at', 'is_active']
    
    def get_participant_count(self, obj):
        return obj.participants.filter(is_active=True).count()


class TranslationSerializer(serializers.ModelSerializer):
    translated_audio_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Translation
        fields = ['id', 'target_language', 'translated_text', 'translated_audio_url', 'created_at']
    
    def get_translated_audio_url(self, obj):
        if obj.translated_audio:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.translated_audio.url)
        return None


class SessionMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.name', read_only=True)
    translations = TranslationSerializer(many=True, read_only=True)
    original_audio_url = serializers.SerializerMethodField()
    
    class Meta:
        model = SessionMessage
        fields = [
            'id', 'session', 'sender_name', 'original_audio',
            'original_audio_url', 'transcription', 'translations',
            'status', 'error_message', 'created_at', 'completed_at'
        ]
        read_only_fields = ['id', 'status', 'created_at', 'completed_at']
    
    def get_original_audio_url(self, obj):
        if obj.original_audio:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.original_audio.url)
        return None
