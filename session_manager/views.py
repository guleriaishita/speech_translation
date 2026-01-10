"""
API Views for Session Management
Handles creation, joining, and management of translation sessions.
"""

import logging
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

from .models import Session, Participant, SessionMessage
from .serializers import SessionSerializer, ParticipantSerializer, SessionMessageSerializer

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name='dispatch')
class CreateSessionView(APIView):
    """
    Create a new translation session.
    
    POST /api/sessions/create/
    
    Request:
        - sender_name: Name of the sender (optional)
        - source_language: Source language code (default: 'en')
    
    Response:
        - 201: Session created with room_code
    """
    
    def post(self, request):
        sender_name = request.data.get('sender_name', 'Anonymous')
        source_language = request.data.get('source_language', 'en')
        
        # Create session
        session = Session.objects.create(
            sender_name=sender_name,
            source_language=source_language
        )
        
        # Create sender participant
        sender_participant = Participant.objects.create(
            session=session,
            name=sender_name,
            role=Participant.ROLE_SENDER,
            target_language=source_language  # Sender speaks source language
        )
        
        logger.info(f"Created session {session.room_code} by {sender_name}")
        
        serializer = SessionSerializer(session, context={'request': request})
        return Response({
            'success': True,
            'message': 'Session created successfully',
            'session': serializer.data,
            'sender_id': str(sender_participant.id)
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class JoinSessionView(APIView):
    """
    Join an existing session as a receiver.
    
    POST /api/sessions/join/
    
    Request:
        - room_code: Session room code
        - name: Participant name (optional)
        - target_language: Target language code
    
    Response:
        - 200: Joined successfully
        - 404: Session not found
        - 400: Session inactive
    """
    
    def post(self, request):
        room_code = request.data.get('room_code', '').upper()
        name = request.data.get('name', 'Anonymous')
        target_language = request.data.get('target_language')
        
        if not room_code or not target_language:
            return Response({
                'error': 'room_code and target_language are required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Find session
        try:
            session = Session.objects.get(room_code=room_code)
        except Session.DoesNotExist:
            return Response({
                'error': f'Session with code {room_code} not found'
            }, status=status.HTTP_404_NOT_FOUND)
       
        # Check if session is active
        if not session.is_active:
            return Response({
                'error': 'This session has ended'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create participant
        participant = Participant.objects.create(
            session=session,
            name=name,
            role=Participant.ROLE_RECEIVER,
            target_language=target_language
        )
        
        logger.info(f"{name} joined session {room_code} for {target_language}")
        
        serializer = SessionSerializer(session, context={'request': request})
        return Response({
            'success': True,
            'message': 'Joined session successfully',
            'session': serializer.data,
            'participant_id': str(participant.id)
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class SessionDetailView(APIView):
    """
    Get session details.
    
    GET /api/sessions/<room_code>/
    
    Response:
        - 200: Session details
        - 404: Session not found
    """
    
    def get(self, request, room_code):
        room_code = room_code.upper()
        session = get_object_or_404(Session, room_code=room_code)
        
        serializer = SessionSerializer(session, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class LeaveSessionView(APIView):
    """
    Leave a session.
    
    POST /api/sessions/<room_code>/leave/
    
    Request:
        - participant_id: ID of the participant leaving
    
    Response:
        - 200: Left successfully
    """
    
    def post(self, request, room_code):
        participant_id = request.data.get('participant_id')
        
        if not participant_id:
            return Response({
                'error': 'participant_id is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            participant = Participant.objects.get(id=participant_id, session__room_code=room_code.upper())
        except Participant.DoesNotExist:
            return Response({
                'error': 'Participant not found'
            }, status=status.HTTP_404_NOT_FOUND)
        
        # Mark as left
        participant.leave()
        
        # If sender leaves, end the session
        if participant.role == Participant.ROLE_SENDER:
            participant.session.end_session()
            logger.info(f"Session {room_code} ended by sender")
        
        return Response({
            'success': True,
            'message': 'Left session successfully'
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class SessionMessagesView(APIView):
    """
    Get message history for a session.
    
    GET /api/sessions/<room_code>/messages/
    
    Response:
        - 200: List of messages
        - 404: Session not found
    """
    
    def get(self, request, room_code):
        session = get_object_or_404(Session, room_code=room_code.upper())
        
        messages = SessionMessage.objects.filter(session=session).order_by('created_at')
        serializer = SessionMessageSerializer(messages, many=True, context={'request': request})
        
        return Response({
            'success': True,
            'count': messages.count(),
            'messages': serializer.data
        }, status=status.HTTP_200_OK)


@method_decorator(csrf_exempt, name='dispatch')
class ActiveSessionsView(APIView):
    """
    Get list of active sessions (for debugging/admin).
    
    GET /api/sessions/active/
    """
    
    def get(self, request):
        sessions = Session.objects.filter(is_active=True).order_by('-created_at')[:20]
        serializer = SessionSerializer(sessions, many=True, context={'request': request})
        
        return Response({
            'success': True,
            'count': sessions.count(),
            'sessions': serializer.data
        }, status=status.HTTP_200_OK)
