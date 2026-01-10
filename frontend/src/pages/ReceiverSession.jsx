import React, { useState, useEffect, useRef } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import SessionWebSocket from '../services/sessionWebSocket';

function ReceiverSession() {
    const { roomCode } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const { session: initialSession, participantId, targetLanguage } = location.state || {};

    const [session, setSession] = useState(initialSession);
    const [messages, setMessages] = useState([]);
    const [wsConnected, setWsConnected] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');
    const [currentAudio, setCurrentAudio] = useState(null);
    const [playingMessageId, setPlayingMessageId] = useState(null);

    // WebSocket
    const wsRef = useRef(null);
    const audioRef = useRef(null);

    useEffect(() => {
        if (!participantId) {
            navigate('/');
            return;
        }

        console.log('[RECEIVER] useEffect: Setting up session');

        // Load session details
        loadSessionDetails();

        // Connect WebSocket only once
        const ws = new SessionWebSocket(roomCode, participantId, handleWebSocketMessage);
        ws.connect();
        wsRef.current = ws;

        // Cleanup on unmount
        return () => {
            console.log('[RECEIVER] useEffect: Cleaning up');
            if (wsRef.current) {
                wsRef.current.disconnect();
                wsRef.current = null;
            }
        };
    }, [participantId, roomCode]); // Only re-run if these change

    const loadSessionDetails = async () => {
        try {
            const response = await axios.get(`/api/sessions/${roomCode}/`);
            setSession(response.data);
        } catch (error) {
            console.error('Error loading session:', error);
        }
    };

    const handleWebSocketMessage = (data) => {
        console.log('[RECEIVER WS] Received message type:', data.type, data);

        switch (data.type) {
            case 'ws_connected':
            case 'connected':
                console.log('[RECEIVER WS] Connected to WebSocket');
                setWsConnected(true);
                setStatusMessage('Connected to session');
                // Request message history
                setTimeout(() => {
                    if (wsRef.current) {
                        wsRef.current.requestHistory();
                    }
                }, 500);
                break;

            case 'ws_disconnected':
                console.log('[RECEIVER WS] Disconnected from WebSocket');
                setWsConnected(false);
                setStatusMessage('Disconnected - reconnecting...');
                break;

            case 'participant_joined':
                setStatusMessage(`${data.participant_name} joined`);
                break;

            case 'participant_left':
                setStatusMessage(`${data.participant_name} left`);
                break;

            case 'processing_started':
                console.log('[RECEIVER WS] Processing started');
                setStatusMessage(`${data.sender_name} is sending audio...`);
                break;

            case 'new_message':
                console.log('[RECEIVER WS] NEW MESSAGE received!');
                // New message from sender
                handleNewMessage(data);
                break;

            case 'history_message':
                // Message from history
                addMessageToHistory(data);
                break;

            case 'error':
                setStatusMessage(`Error: ${data.error}`);
                break;

            default:
                console.log('Unhandled message type:', data.type);
        }
    };

    const handleNewMessage = (data) => {
        console.log('[RECEIVER] handleNewMessage called with data:', data);

        const message = {
            id: data.message_id,
            senderName: data.sender_name,
            transcription: data.transcription,
            translation: data.translation,
            audioBase64: data.audio,
            timestamp: new Date().toISOString(),
            isNew: true
        };

        console.log('[RECEIVER] Adding message to state:', message.id);
        setMessages(prev => [...prev, message]);
        setStatusMessage(`New message from ${data.sender_name}`);

        // Auto-play the audio
        if (data.audio) {
            console.log('[RECEIVER] Auto-playing audio for message:', message.id);
            playAudio(data.audio, data.message_id);
        } else {
            console.warn('[RECEIVER] No audio data in message');
        }
    };

    const addMessageToHistory = (data) => {
        const message = {
            id: data.message_id,
            senderName: data.sender_name,
            transcription: data.transcription,
            translation: data.translation,
            audioUrl: data.audio_url,
            timestamp: data.created_at,
            isNew: false
        };

        setMessages(prev => {
            // Avoid duplicates
            if (prev.find(m => m.id === message.id)) {
                return prev;
            }
            return [...prev, message];
        });
    };

    const playAudio = (audioBase64, messageId) => {
        try {
            // Convert base64 to blob
            const byteCharacters = atob(audioBase64);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            const blob = new Blob([byteArray], { type: 'audio/mp3' });
            const url = URL.createObjectURL(blob);

            setCurrentAudio(url);
            setPlayingMessageId(messageId);

            // Play using the audio element
            if (audioRef.current) {
                audioRef.current.src = url;
                audioRef.current.play()
                    .then(() => {
                        console.log('Playing audio');
                    })
                    .catch(err => {
                        console.error('Error playing audio:', err);
                    });
            }
        } catch (error) {
            console.error('Error playing audio:', error);
        }
    };

    const handleAudioEnded = () => {
        setPlayingMessageId(null);
        if (currentAudio) {
            URL.revokeObjectURL(currentAudio);
            setCurrentAudio(null);
        }
    };

    const handleLeaveSession = async () => {
        if (!confirm('Are you sure you want to leave the session?')) {
            return;
        }

        try {
            await axios.post(`/api/sessions/${roomCode}/leave/`, {
                participant_id: participantId
            });

            if (wsRef.current) {
                wsRef.current.disconnect();
            }

            navigate('/');
        } catch (error) {
            console.error('Error leaving session:', error);
        }
    };

    // Sort messages by timestamp
    const sortedMessages = [...messages].sort((a, b) =>
        new Date(a.timestamp) - new Date(b.timestamp)
    );

    return (
        <div style={{
            minHeight: '100vh',
            padding: '2rem'
        }}>
            <div style={{ maxWidth: '900px', margin: '0 auto' }}>
                {/* Header */}
                <header style={{ marginBottom: '2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h1 className="gradient-text" style={{ fontSize: '2rem', fontWeight: '700' }}>
                            👂 Receiver Session
                        </h1>
                        <button
                            onClick={handleLeaveSession}
                            className="btn btn-secondary"
                            style={{ padding: '0.75rem 1.5rem' }}
                        >
                            Leave Session
                        </button>
                    </div>

                    {/* Session Info */}
                    <div className="glass-card" style={{ padding: '1.5rem' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem', textAlign: 'center' }}>
                            <div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginBottom: '0.25rem' }}>
                                    Room Code
                                </div>
                                <div style={{ fontSize: '1.25rem', fontWeight: '700', color: 'var(--color-accent-primary)' }}>
                                    {roomCode}
                                </div>
                            </div>
                            <div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginBottom: '0.25rem' }}>
                                    Your Language
                                </div>
                                <div style={{ fontSize: '1.25rem', fontWeight: '700' }}>
                                    {targetLanguage?.toUpperCase()}
                                </div>
                            </div>
                            <div>
                                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)', marginBottom: '0.25rem' }}>
                                    Sender
                                </div>
                                <div style={{ fontSize: '1.25rem', fontWeight: '700' }}>
                                    {session?.sender_name || '...'}
                                </div>
                            </div>
                        </div>
                    </div>
                </header>

                {/* Status Bar */}
                <div style={{
                    padding: '1rem',
                    background: wsConnected ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                    border: `1px solid ${wsConnected ? 'rgb(34, 197, 94)' : 'rgb(239, 68, 68)'}`,
                    borderRadius: 'var(--radius-md)',
                    marginBottom: '2rem',
                    textAlign: 'center',
                    fontSize: '0.875rem',
                    fontWeight: '500'
                }}>
                    {wsConnected ? '🟢 Connected' : '🔴 Disconnected'} • {statusMessage || 'Waiting for messages...'}
                </div>

                {/* Audio Player (hidden) */}
                <audio
                    ref={audioRef}
                    onEnded={handleAudioEnded}
                    style={{ display: 'none' }}
                />

                {/* Messages */}
                <div className="glass-card" style={{ padding: '2rem' }}>
                    <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.5rem' }}>
                        Messages
                    </h2>

                    {sortedMessages.length === 0 ? (
                        <div style={{
                            padding: '3rem 2rem',
                            textAlign: 'center',
                            color: 'var(--color-text-tertiary)'
                        }}>
                            <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>💬</div>
                            <p>No messages yet. Waiting for sender to send audio...</p>
                        </div>
                    ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            {sortedMessages.map((message) => (
                                <div
                                    key={message.id}
                                    className={message.isNew ? 'animate-fade-in' : ''}
                                    style={{
                                        padding: '1.5rem',
                                        background: 'var(--color-bg-secondary)',
                                        borderRadius: 'var(--radius-lg)',
                                        border: message.isNew ? '2px solid var(--color-accent-primary)' : '1px solid var(--glass-border)'
                                    }}
                                >
                                    {/* Header */}
                                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
                                        <div style={{ fontSize: '0.875rem', fontWeight: '600' }}>
                                            {message.senderName}
                                        </div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
                                            {new Date(message.timestamp).toLocaleTimeString()}
                                        </div>
                                    </div>

                                    {/* Original Transcription */}
                                    {message.transcription && (
                                        <div style={{ marginBottom: '1rem' }}>
                                            <div style={{
                                                fontSize: '0.75rem',
                                                fontWeight: '600',
                                                color: 'var(--color-text-tertiary)',
                                                marginBottom: '0.5rem',
                                                textTransform: 'uppercase'
                                            }}>
                                                Original ({session?.source_language || 'source'})
                                            </div>
                                            <div style={{
                                                fontSize: '0.875rem',
                                                color: 'var(--color-text-secondary)',
                                                fontStyle: 'italic'
                                            }}>
                                                "{message.transcription}"
                                            </div>
                                        </div>
                                    )}

                                    {/* Translation */}
                                    <div style={{ marginBottom: '1rem' }}>
                                        <div style={{
                                            fontSize: '0.75rem',
                                            fontWeight: '600',
                                            color: 'var(--color-text-tertiary)',
                                            marginBottom: '0.5rem',
                                            textTransform: 'uppercase'
                                        }}>
                                            Translation ({targetLanguage})
                                        </div>
                                        <div style={{
                                            fontSize: '1rem',
                                            color: 'var(--color-text-primary)',
                                            fontWeight: '500',
                                            lineHeight: '1.6'
                                        }}>
                                            "{message.translation}"
                                        </div>
                                    </div>

                                    {/* Audio Controls */}
                                    {(message.audioBase64 || message.audioUrl) && (
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                                            {playingMessageId === message.id ? (
                                                <div style={{
                                                    padding: '0.75rem 1.5rem',
                                                    background: 'var(--color-accent-gradient)',
                                                    borderRadius: 'var(--radius-md)',
                                                    color: 'white',
                                                    fontSize: '0.875rem',
                                                    fontWeight: '600'
                                                }}>
                                                    🔊 Playing...
                                                </div>
                                            ) : (
                                                <button
                                                    onClick={() => {
                                                        if (message.audioBase64) {
                                                            playAudio(message.audioBase64, message.id);
                                                        }
                                                    }}
                                                    className="btn btn-primary"
                                                    style={{ padding: '0.75rem 1.5rem', fontSize: '0.875rem' }}
                                                >
                                                    ▶️ Play Translation
                                                </button>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}

export default ReceiverSession;
