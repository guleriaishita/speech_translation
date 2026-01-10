import React, { useState, useEffect, useRef } from 'react';
import { useParams, useLocation, useNavigate } from 'react-router-dom';
import axios from 'axios';
import SessionWebSocket from '../services/sessionWebSocket';

function SenderSession() {
    const { roomCode } = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    const { session: initialSession, senderId } = location.state || {};

    const [session, setSession] = useState(initialSession);
    const [participants, setParticipants] = useState([]);
    const [messages, setMessages] = useState([]);
    const [wsConnected, setWsConnected] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [statusMessage, setStatusMessage] = useState('');

    // File upload
    const [selectedFile, setSelectedFile] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const fileInputRef = useRef(null);

    // Audio recording
    const [isRecording, setIsRecording] = useState(false);
    const [recordedBlob, setRecordedBlob] = useState(null);
    const [recordingDuration, setRecordingDuration] = useState(0);
    const mediaRecorderRef = useRef(null);
    const recordingTimerRef = useRef(null);
    const audioChunksRef = useRef([]);

    // WebSocket
    const wsRef = useRef(null);

    useEffect(() => {
        if (!senderId) {
            // Session state not passed, redirect to home
            navigate('/');
            return;
        }

        console.log('[SENDER] useEffect: Setting up session');

        // Load session details
        loadSessionDetails();

        // Connect WebSocket only once
        const ws = new SessionWebSocket(roomCode, senderId, handleWebSocketMessage);
        ws.connect();
        wsRef.current = ws;

        return () => {
            console.log('[SENDER] useEffect: Cleaning up');
            if (wsRef.current) {
                wsRef.current.disconnect();
                wsRef.current = null;
            }
        };
    }, [senderId, roomCode]); // Only re-run if these change

    const loadSessionDetails = async () => {
        try {
            const response = await axios.get(`/api/sessions/${roomCode}/`);
            setSession(response.data);
            setParticipants(response.data.participants || []);
        } catch (error) {
            console.error('Error loading session:', error);
        }
    };

    const handleWebSocketMessage = (data) => {
        switch (data.type) {
            case 'ws_connected':
            case 'connected':
                setWsConnected(true);
                setStatusMessage('Connected to session');
                break;

            case 'ws_disconnected':
                setWsConnected(false);
                setStatusMessage('Disconnected - reconnecting...');
                break;

            case 'participant_joined':
                setStatusMessage(`${data.participant_name} joined as ${data.role}`);
                loadSessionDetails(); // Refresh participant list
                break;

            case 'participant_left':
                setStatusMessage(`${data.participant_name} left`);
                loadSessionDetails();
                break;

            case 'processing_started':
                setProcessing(true);
                setStatusMessage('Processing audio...');
                break;

            case 'error':
                setStatusMessage(`Error: ${data.error}`);
                setProcessing(false);
                break;

            default:
                console.log('Unhandled message type:', data.type);
        }
    };

    const handleFileSelect = (file) => {
        if (!file) return;

        // Validate file type
        const validTypes = ['audio/wav', 'audio/mp3', 'audio/mpeg', 'audio/webm', 'audio/ogg'];
        if (!validTypes.includes(file.type) && !file.name.match(/\.(wav|mp3|webm|ogg)$/i)) {
            alert('Please select a valid audio file');
            return;
        }

        setSelectedFile(file);
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);

        const file = e.dataTransfer.files[0];
        handleFileSelect(file);
    };

    const handleSendAudio = async () => {
        if (!selectedFile || !wsConnected) return;

        setProcessing(true);
        setStatusMessage('Uploading audio...');

        try {
            // Convert file to base64
            const reader = new FileReader();
            reader.onload = async (e) => {
                const base64 = e.target.result.split(',')[1];

                // Send via WebSocket
                wsRef.current.sendAudioFile(base64);

                setStatusMessage('Audio sent! Processing...');
                setSelectedFile(null);

                // Processing state will be updated by WebSocket messages
                setTimeout(() => {
                    setProcessing(false);
                    setStatusMessage('Audio processed and broadcast to receivers');
                }, 5000);
            };

            reader.readAsDataURL(selectedFile);

        } catch (error) {
            console.error('Error sending audio:', error);
            setStatusMessage('Failed to send audio');
            setProcessing(false);
        }
    };

    const startRecording = async () => {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

            // Create MediaRecorder
            const mediaRecorder = new MediaRecorder(stream, {
                mimeType: 'audio/webm'
            });

            audioChunksRef.current = [];

            mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    audioChunksRef.current.push(event.data);
                }
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
                setRecordedBlob(audioBlob);

                // Stop all tracks
                stream.getTracks().forEach(track => track.stop());

                // Stop timer
                if (recordingTimerRef.current) {
                    clearInterval(recordingTimerRef.current);
                }
            };

            mediaRecorder.start();
            mediaRecorderRef.current = mediaRecorder;
            setIsRecording(true);
            setRecordingDuration(0);

            // Start duration timer
            recordingTimerRef.current = setInterval(() => {
                setRecordingDuration(prev => prev + 1);
            }, 1000);

            setStatusMessage('Recording...');

        } catch (error) {
            console.error('Error starting recording:', error);
            setStatusMessage('Microphone access denied or unavailable');
        }
    };

    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
            setStatusMessage('Recording stopped');
        }
    };

    const discardRecording = () => {
        setRecordedBlob(null);
        setRecordingDuration(0);
        setStatusMessage('');
    };

    const sendRecording = async () => {
        if (!recordedBlob || !wsConnected) return;

        setProcessing(true);
        setStatusMessage('Sending recording...');

        try {
            // Convert blob to base64
            const reader = new FileReader();
            reader.onload = async (e) => {
                const base64 = e.target.result.split(',')[1];

                // Send via WebSocket
                wsRef.current.sendAudioFile(base64);

                setStatusMessage('Recording sent! Processing...');
                setRecordedBlob(null);
                setRecordingDuration(0);

                // Processing state will be updated by WebSocket messages
                setTimeout(() => {
                    setProcessing(false);
                    setStatusMessage('Audio processed and broadcast to receivers');
                }, 5000);
            };

            reader.readAsDataURL(recordedBlob);

        } catch (error) {
            console.error('Error sending recording:', error);
            setStatusMessage('Failed to send recording');
            setProcessing(false);
        }
    };

    const formatDuration = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const copyRoomCode = () => {
        navigator.clipboard.writeText(roomCode);
        setStatusMessage('Room code copied to clipboard!');
        setTimeout(() => setStatusMessage(''), 2000);
    };

    const handleLeaveSession = async () => {
        if (!confirm('Are you sure you want to leave? This will end the session for all participants.')) {
            return;
        }

        try {
            await axios.post(`/api/sessions/${roomCode}/leave/`, {
                participant_id: senderId
            });

            if (wsRef.current) {
                wsRef.current.disconnect();
            }

            navigate('/');
        } catch (error) {
            console.error('Error leaving session:', error);
        }
    };

    const receivers = participants.filter(p => p.role === 'receiver' && p.is_active);

    return (
        <div style={{
            minHeight: '100vh',
            padding: '2rem'
        }}>
            <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
                {/* Header */}
                <header style={{ marginBottom: '2rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                        <h1 className="gradient-text" style={{ fontSize: '2rem', fontWeight: '700' }}>
                            🎤 Sender Session
                        </h1>
                        <button
                            onClick={handleLeaveSession}
                            className="btn btn-secondary"
                            style={{ padding: '0.75rem 1.5rem' }}
                        >
                            Leave Session
                        </button>
                    </div>

                    {/* Room Code Display */}
                    <div className="glass-card" style={{
                        padding: '1.5rem',
                        textAlign: 'center',
                        background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.1), rgba(139, 92, 246, 0.1))'
                    }}>
                        <div style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)', marginBottom: '0.5rem' }}>
                            Share this code with receivers:
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '1rem' }}>
                            <div style={{
                                fontSize: '2.5rem',
                                fontWeight: '700',
                                letterSpacing: '0.3em',
                                color: 'var(--color-accent-primary)'
                            }}>
                                {roomCode}
                            </div>
                            <button
                                onClick={copyRoomCode}
                                className="btn btn-primary"
                                style={{ padding: '0.75rem 1.5rem' }}
                            >
                                📋 Copy
                            </button>
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
                    {wsConnected ? '🟢 Connected' : '🔴 Disconnected'} • {statusMessage || 'Ready to send audio'}
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '2rem' }}>
                    {/* Main Content */}
                    <div>
                        {/* File Upload */}
                        <div className="glass-card" style={{ padding: '2rem', marginBottom: '2rem' }}>
                            <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.5rem' }}>
                                Send Audio
                            </h2>

                            <div
                                onDragOver={handleDragOver}
                                onDragLeave={handleDragLeave}
                                onDrop={handleDrop}
                                onClick={() => !selectedFile && fileInputRef.current?.click()}
                                style={{
                                    border: `2px dashed ${isDragging ? 'var(--color-accent-primary)' : 'var(--glass-border)'}`,
                                    borderRadius: 'var(--radius-lg)',
                                    padding: '3rem 2rem',
                                    textAlign: 'center',
                                    cursor: selectedFile ? 'default' : 'pointer',
                                    background: isDragging ? 'rgba(99, 102, 241, 0.1)' : 'var(--color-bg-secondary)',
                                    transition: 'all 0.2s ease',
                                    marginBottom: '1.5rem'
                                }}
                            >
                                <input
                                    ref={fileInputRef}
                                    type="file"
                                    accept="audio/*"
                                    onChange={(e) => handleFileSelect(e.target.files[0])}
                                    style={{ display: 'none' }}
                                />

                                {!selectedFile ? (
                                    <>
                                        <div style={{ fontSize: '3rem', marginBottom: '1rem', opacity: 0.5 }}>🎵</div>
                                        <h3 style={{ fontSize: '1.125rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                                            Drop audio file here
                                        </h3>
                                        <p style={{ fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>
                                            or click to browse • Supports WAV, MP3, WebM, OGG
                                        </p>
                                    </>
                                ) : (
                                    <div>
                                        <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>🎵</div>
                                        <div style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.5rem' }}>
                                            {selectedFile.name}
                                        </div>
                                        <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                                            {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                                        </div>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                setSelectedFile(null);
                                            }}
                                            className="btn btn-secondary"
                                            style={{ marginTop: '1rem', padding: '0.5rem 1rem' }}
                                        >
                                            Remove
                                        </button>
                                    </div>
                                )}
                            </div>

                            <button
                                onClick={handleSendAudio}
                                disabled={!selectedFile || !wsConnected || processing}
                                className="btn btn-primary"
                                style={{ width: '100%', padding: '1rem', fontSize: '1rem' }}
                            >
                                {processing ? '⏳ Processing...' : '📤 Send to All Receivers'}
                            </button>
                        </div>

                        {/* Live Recording */}
                        <div className="glass-card" style={{ padding: '2rem' }}>
                            <h2 style={{ fontSize: '1.25rem', fontWeight: '600', marginBottom: '1.5rem' }}>
                                Record Audio
                            </h2>

                            {!isRecording && !recordedBlob ? (
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>🎙️</div>
                                    <button
                                        onClick={startRecording}
                                        disabled={!wsConnected || processing}
                                        className="btn btn-primary"
                                        style={{ padding: '1rem 2rem', fontSize: '1rem' }}
                                    >
                                        🔴 Start Recording
                                    </button>
                                    <p style={{
                                        fontSize: '0.875rem',
                                        color: 'var(--color-text-secondary)',
                                        marginTop: '1rem'
                                    }}>
                                        Click to record from your microphone
                                    </p>
                                </div>
                            ) : isRecording ? (
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{
                                        fontSize: '3rem',
                                        marginBottom: '1rem',
                                        animation: 'pulse 1.5s ease-in-out infinite'
                                    }}>
                                        🔴
                                    </div>
                                    <div style={{
                                        fontSize: '2rem',
                                        fontWeight: '700',
                                        color: 'var(--color-accent-primary)',
                                        marginBottom: '1rem'
                                    }}>
                                        {formatDuration(recordingDuration)}
                                    </div>
                                    <button
                                        onClick={stopRecording}
                                        className="btn btn-secondary"
                                        style={{ padding: '1rem 2rem', fontSize: '1rem' }}
                                    >
                                        ⏹️ Stop Recording
                                    </button>
                                </div>
                            ) : (
                                <div style={{ textAlign: 'center' }}>
                                    <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>✅</div>
                                    <div style={{
                                        fontSize: '1.125rem',
                                        fontWeight: '600',
                                        marginBottom: '0.5rem'
                                    }}>
                                        Recording Complete
                                    </div>
                                    <div style={{
                                        fontSize: '0.875rem',
                                        color: 'var(--color-text-secondary)',
                                        marginBottom: '1.5rem'
                                    }}>
                                        Duration: {formatDuration(recordingDuration)}
                                    </div>
                                    <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
                                        <button
                                            onClick={discardRecording}
                                            className="btn btn-secondary"
                                            style={{ padding: '0.75rem 1.5rem' }}
                                        >
                                            🗑️ Discard
                                        </button>
                                        <button
                                            onClick={sendRecording}
                                            disabled={!wsConnected || processing}
                                            className="btn btn-primary"
                                            style={{ padding: '0.75rem 1.5rem' }}
                                        >
                                            📤 Send Recording
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Sidebar - Receivers */}
                    <div>
                        <div className="glass-card" style={{ padding: '1.5rem' }}>
                            <h3 style={{ fontSize: '1rem', fontWeight: '600', marginBottom: '1rem' }}>
                                Receivers ({receivers.length})
                            </h3>

                            {receivers.length === 0 ? (
                                <div style={{
                                    padding: '2rem 1rem',
                                    textAlign: 'center',
                                    color: 'var(--color-text-tertiary)',
                                    fontSize: '0.875rem'
                                }}>
                                    No receivers yet.<br />Share the room code!
                                </div>
                            ) : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                                    {receivers.map((receiver) => (
                                        <div
                                            key={receiver.id}
                                            style={{
                                                padding: '0.75rem',
                                                background: 'var(--color-bg-secondary)',
                                                borderRadius: 'var(--radius-md)',
                                                border: '1px solid var(--glass-border)'
                                            }}
                                        >
                                            <div style={{ fontSize: '0.875rem', fontWeight: '600', marginBottom: '0.25rem' }}>
                                                {receiver.name}
                                            </div>
                                            <div style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
                                                {receiver.target_language.toUpperCase()}
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}

export default SenderSession;
