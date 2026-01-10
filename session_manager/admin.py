from django.contrib import admin
from .models import Session, Participant, SessionMessage, Translation


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ['room_code', 'sender_name', 'source_language', 'is_active', 'created_at']
    list_filter = ['is_active', 'source_language', 'created_at']
    search_fields = ['room_code', 'sender_name']
    readonly_fields = ['id', 'room_code', 'created_at', 'ended_at']


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ['name', 'session', 'role', 'target_language', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'target_language']
    search_fields = ['name', 'session__room_code']
    readonly_fields = ['id', 'joined_at', 'left_at']


@admin.register(SessionMessage)
class SessionMessageAdmin(admin.ModelAdmin):
    list_display = ['session', 'sender', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['session__room_code', 'transcription']
    readonly_fields = ['id', 'created_at', 'completed_at']


@admin.register(Translation)
class TranslationAdmin(admin.ModelAdmin):
    list_display = ['message', 'target_language', 'created_at']
    list_filter = ['target_language', 'created_at']
    search_fields = ['translated_text', 'message__session__room_code']
    readonly_fields = ['id', 'created_at']
