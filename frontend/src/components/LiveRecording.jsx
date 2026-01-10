import React, { useState, useRef, useEffect } from 'react';
import AudioQueue from '../utils/AudioQueue';
import StatusIndicator from './StatusIndicator';

function LiveRecording({ sourceLang, targetLang }) {
    const [isRecording, setIsRecording] = useState(false);
    const [isConnected, setIsConnected] = useState(false);
    const [status, setStatus] = useState('idle');
    const [statusMessage, setStatusMessage] = useState('Click "Start Recording" to begin');
    const [error, setError] = useState('');
    const [transcription, setTranscription] = useState('');
    const [translation, setTranslation] = useState('');
    const [permissionGranted, setPermissionGranted] = useState(false);

    const mediaRecorderRef = useRef(null);
    const mediaStreamRef = useRef(null);
    const websocketRef = useRef(null);
    const audioQueueRef = useRef(null);
    const visualizerRef = useRef(null);
    const canvasRef = useRef(null);
    const animationFrameRef = useRef(null);

    useEffect(() => {
        // Initialize audio queue
        audioQueueRef.current = new AudioQueue();

        return () => {
            // Cleanup on unmount
            handleStop();
            if (audioQueueRef.current) {
                audioQueueRef.current.clear();
            }
        };
    }, []);

    const initializeWebSocket = () => {
        return new Promise((resolve, reject) => {
            const ws = new WebSocket('ws://localhost:8000/ws/translate/');

            ws.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
                setStatus('connected');

                // Send configuration
                ws.send(JSON.stringify({
                    type: 'configure',
                    source_language: sourceLang,
                    target_language: targetLang
                }));

                resolve(ws);
            };

            ws.onmessage = async (event) => {
                // Handle text messages
                if (typeof event.data === 'string') {
                    try {
                        const data = JSON.parse(event.data);

                        switch (data.type) {
                            case 'connection_established':
                                setStatusMessage(data.message);
                                break;

                            case 'configured':
                                setStatusMessage('Ready to record');
                                break;

                            case 'processing':
                                setStatusMessage(data.message);
                                break;

                            case 'transcription':
                                setTranscription(prev => prev + (prev ? ' ' : '') + data.text);
                                setStatusMessage('Transcribed audio');
                                break;

                            case 'translation':
                                setTranslation(prev => prev + (prev ? ' ' : '') + data.text);
                                setStatusMessage('Translation received');
                                break;

                            case 'audio_complete':
                                setStatusMessage('Audio playback complete');
                                break;

                            case 'info':
                                setStatusMessage(data.message);
                                break;

                            case 'error':
                                console.error('WebSocket error:', data.error);
                                setError(data.error || data.message);
                                setStatus('error');
                                break;

                            default:
                                console.log('Unknown message type:', data.type);
                        }
                    } catch (err) {
                        console.error('Error parsing WebSocket message:', err);
                    }
                }
                // Handle binary messages (audio data)
                else {
                    try {
                        await audioQueueRef.current.enqueue(event.data);
                        setStatusMessage('Playing translated audio');
                    } catch (err) {
                        console.error('Error playing audio:', err);
                    }
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                setError('WebSocket connection error');
                setStatus('error');
                setIsConnected(false);
                reject(error);
            };

            ws.onclose = () => {
                console.log('WebSocket closed');
                setIsConnected(false);
                setStatus('idle');
                setStatusMessage('Disconnected');
            };

            websocketRef.current = ws;
        });
    };

    const initializeMediaRecorder = async () => {
        try {
            // Request microphone permission
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    sampleRate: 16000,
                    channelCount: 1,
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            setPermissionGranted(true);
            mediaStreamRef.current = stream;

            // Create MediaRecorder
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : 'audio/webm';

            const mediaRecorder = new MediaRecorder(stream, {
                mimeType,
                audioBitsPerSecond: 16000
            });

            mediaRecorder.ondataavailable = async (event) => {
                if (event.data.size > 0 && websocketRef.current?.readyState === WebSocket.OPEN) {
                    websocketRef.current.send(event.data);
                }
            };

            mediaRecorder.onerror = (error) => {
                console.error('MediaRecorder error:', error);
                setError('Recording error occurred');
                setStatus('error');
            };

            mediaRecorderRef.current = mediaRecorder;

            // Initialize visualizer
            initializeVisualizer(stream);

            return mediaRecorder;
        } catch (err) {
            console.error('Error accessing microphone:', err);
            setError('Failed to access microphone. Please grant permission.');
            setStatus('error');
            throw err;
        }
    };

    const initializeVisualizer = (stream) => {
        if (!canvasRef.current) return;

        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);

        source.connect(analyser);
        analyser.fftSize = 256;

        const bufferLength = analyser.frequencyBinCount;
        const dataArray = new Uint8Array(bufferLength);

        visualizerRef.current = { analyser, dataArray, bufferLength };

        drawVisualizer();
    };

    const drawVisualizer = () => {
        if (!canvasRef.current || !visualizerRef.current) return;

        const canvas = canvasRef.current;
        const ctx = canvas.getContext('2d');
        const { analyser, dataArray, bufferLength } = visualizerRef.current;

        const draw = () => {
            animationFrameRef.current = requestAnimationFrame(draw);

            analyser.getByteFrequencyData(dataArray);

            ctx.fillStyle = 'rgba(10, 14, 26, 0.2)';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.5;
            let barHeight;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                barHeight = (dataArray[i] / 255) * canvas.height * 0.8;

                const gradient = ctx.createLinearGradient(0, canvas.height - barHeight, 0, canvas.height);
                gradient.addColorStop(0, '#6366f1');
                gradient.addColorStop(1, '#8b5cf6');

                ctx.fillStyle = gradient;
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

                x += barWidth + 1;
            }
        };

        draw();
    };

    const handleStart = async () => {
        try {
            setError('');
            setTranscription('');
            setTranslation('');
            setStatus('connecting');
            setStatusMessage('Connecting...');

            // Initialize WebSocket
            await initializeWebSocket();

            // Initialize MediaRecorder
            const mediaRecorder = await initializeMediaRecorder();

            // Initialize audio queue
            await audioQueueRef.current.init();

            // Start recording (send chunks every 500ms)
            mediaRecorder.start(500);
            setIsRecording(true);
            setStatus('processing');
            setStatusMessage('Recording... Speak now');

        } catch (err) {
            console.error('Error starting recording:', err);
            setError(err.message || 'Failed to start recording');
            setStatus('error');
            handleStop();
        }
    };

    const handleStop = () => {
        // Stop media recorder
        if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
            mediaRecorderRef.current.stop();
        }

        // Stop media stream
        if (mediaStreamRef.current) {
            mediaStreamRef.current.getTracks().forEach(track => track.stop());
            mediaStreamRef.current = null;
        }

        // Close WebSocket
        if (websocketRef.current) {
            websocketRef.current.close();
            websocketRef.current = null;
        }

        // Stop visualizer
        if (animationFrameRef.current) {
            cancelAnimationFrame(animationFrameRef.current);
            animationFrameRef.current = null;
        }

        // Clear canvas
        if (canvasRef.current) {
            const ctx = canvasRef.current.getContext('2d');
            ctx.clearRect(0, 0, canvasRef.current.width, canvasRef.current.height);
        }

        setIsRecording(false);
        setIsConnected(false);
        setStatus('idle');
        setStatusMessage('Recording stopped');
    };

    return (
        <div className="animate-fade-in">
            {/* Status */}
            <div style={{ marginBottom: '1.5rem' }}>
                <StatusIndicator
                    status={isRecording ? 'processing' : (isConnected ? 'connected' : status)}
                    message={statusMessage}
                />
            </div>

            {/* Visualizer */}
            <div style={{
                background: 'var(--color-bg-secondary)',
                borderRadius: 'var(--radius-lg)',
                padding: '1.5rem',
                marginBottom: '1.5rem',
                border: '1px solid var(--glass-border)'
            }}>
                <canvas
                    ref={canvasRef}
                    width={600}
                    height={150}
                    style={{
                        width: '100%',
                        height: 'auto',
                        borderRadius: 'var(--radius-md)',
                        background: 'var(--color-bg-primary)'
                    }}
                />
                <div style={{
                    textAlign: 'center',
                    marginTop: '1rem',
                    fontSize: '0.875rem',
                    color: 'var(--color-text-secondary)'
                }}>
                    {isRecording ? '🎤 Recording in progress...' : '🎤 Audio Visualizer'}
                </div>
            </div>

            {/* Error Message */}
            {error && (
                <div style={{
                    padding: '1rem',
                    background: 'rgba(239, 68, 68, 0.1)',
                    border: '1px solid var(--color-error)',
                    borderRadius: 'var(--radius-md)',
                    marginBottom: '1.5rem'
                }}>
                    <div style={{
                        fontSize: '0.875rem',
                        color: 'var(--color-error)',
                        fontWeight: '500'
                    }}>
                        ⚠️ {error}
                    </div>
                </div>
            )}

            {/* Transcription and Translation */}
            {(transcription || translation) && (
                <div style={{
                    padding: '1.5rem',
                    background: 'var(--color-bg-secondary)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--glass-border)',
                    marginBottom: '1.5rem'
                }}>
                    {transcription && (
                        <div style={{ marginBottom: translation ? '1.5rem' : '0' }}>
                            <div style={{
                                fontSize: '0.75rem',
                                fontWeight: '600',
                                color: 'var(--color-text-tertiary)',
                                marginBottom: '0.5rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em'
                            }}>
                                Original ({sourceLang})
                            </div>
                            <div style={{
                                fontSize: '0.875rem',
                                color: 'var(--color-text-secondary)',
                                lineHeight: '1.6',
                                minHeight: '60px'
                            }}>
                                {transcription}
                            </div>
                        </div>
                    )}

                    {translation && (
                        <div>
                            <div style={{
                                fontSize: '0.75rem',
                                fontWeight: '600',
                                color: 'var(--color-text-tertiary)',
                                marginBottom: '0.5rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em'
                            }}>
                                Translation ({targetLang})
                            </div>
                            <div style={{
                                fontSize: '1rem',
                                color: 'var(--color-text-primary)',
                                fontWeight: '500',
                                lineHeight: '1.6',
                                minHeight: '60px'
                            }}>
                                {translation}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Control Buttons */}
            <div style={{
                display: 'flex',
                gap: '1rem',
                justifyContent: 'center'
            }}>
                {!isRecording ? (
                    <button
                        onClick={handleStart}
                        className="btn btn-primary"
                        style={{ minWidth: '200px', fontSize: '1rem', padding: '0.75rem 2rem' }}
                    >
                        🎤 Start Recording
                    </button>
                ) : (
                    <button
                        onClick={handleStop}
                        className="btn btn-danger"
                        style={{ minWidth: '200px', fontSize: '1rem', padding: '0.75rem 2rem' }}
                    >
                        ⏹️ Stop Recording
                    </button>
                )}
            </div>

            {/* Info */}
            <div style={{
                marginTop: '2rem',
                padding: '1rem',
                background: 'rgba(99, 102, 241, 0.1)',
                border: '1px solid rgba(99, 102, 241, 0.3)',
                borderRadius: 'var(--radius-md)',
                fontSize: '0.75rem',
                color: 'var(--color-text-secondary)',
                lineHeight: '1.6'
            }}>
                <strong style={{ color: 'var(--color-accent-primary)' }}>ℹ️ How it works:</strong><br />
                1. Click "Start Recording" and allow microphone access<br />
                2. Speak clearly in your source language<br />
                3. Translation happens in real-time<br />
                4. Translated audio plays automatically
            </div>
        </div>
    );
}

export default LiveRecording;
