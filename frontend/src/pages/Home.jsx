import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import LanguageSelector from '../components/LanguageSelector';

function Home() {
    const navigate = useNavigate();
    const [mode, setMode] = useState(null); // 'sender' or 'receiver'
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    // Sender state
    const [senderName, setSenderName] = useState('');
    const [sourceLanguage, setSourceLanguage] = useState('en');

    // Receiver state
    const [receiverName, setReceiverName] = useState('');
    const [roomCode, setRoomCode] = useState('');
    const [targetLanguage, setTargetLanguage] = useState('es');

    const handleCreateSession = async () => {
        if (!senderName.trim()) {
            setError('Please enter your name');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const response = await axios.post('/api/sessions/create/', {
                sender_name: senderName,
                source_language: sourceLanguage
            });

            const { session, sender_id } = response.data;

            // Navigate to sender page
            navigate(`/sender/${session.room_code}`, {
                state: {
                    session,
                    senderId: sender_id
                }
            });

        } catch (err) {
            setError(err.response?.data?.error || 'Failed to create session');
        } finally {
            setLoading(false);
        }
    };

    const handleJoinSession = async () => {
        if (!receiverName.trim() || !roomCode.trim()) {
            setError('Please enter your name and room code');
            return;
        }

        setLoading(true);
        setError('');

        try {
            const response = await axios.post('/api/sessions/join/', {
                room_code: roomCode.toUpperCase(),
                name: receiverName,
                target_language: targetLanguage
            });

            const { session, participant_id } = response.data;

            // Navigate to receiver page
            navigate(`/receiver/${session.room_code}`, {
                state: {
                    session,
                    participantId: participant_id,
                    targetLanguage
                }
            });

        } catch (err) {
            setError(err.response?.data?.error || 'Failed to join session');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div style={{
            minHeight: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '2rem'
        }}>
            <div style={{ maxWidth: '600px', width: '100%' }}>
                {/* Header */}
                <header style={{ textAlign: 'center', marginBottom: '3rem' }}>
                    <h1 className="gradient-text" style={{
                        fontSize: '2.5rem',
                        fontWeight: '700',
                        marginBottom: '0.5rem',
                        letterSpacing: '-0.02em'
                    }}>
                        🌍 Real-Time Translation
                    </h1>
                    <p style={{
                        fontSize: '1rem',
                        color: 'var(--color-text-secondary)',
                        fontWeight: '500'
                    }}>
                        Connect and communicate across languages in real-time
                    </p>
                </header>

                {mode === null ? (
                    /* Mode Selection */
                    <div className="glass-card" style={{ padding: '2rem' }}>
                        <h2 style={{
                            fontSize: '1.25rem',
                            fontWeight: '600',
                            marginBottom: '1.5rem',
                            color: 'var(--color-text-primary)',
                            textAlign: 'center'
                        }}>
                            Choose Your Role
                        </h2>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                            <button
                                onClick={() => setMode('sender')}
                                className="btn btn-primary"
                                style={{
                                    padding: '1.5rem',
                                    fontSize: '1rem',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                            >
                                <span style={{ fontSize: '2rem' }}>🎤</span>
                                <span style={{ fontWeight: '600' }}>Create Session (Sender)</span>
                                <span style={{ fontSize: '0.875rem', opacity: 0.8 }}>
                                    Send audio and share with receivers
                                </span>
                            </button>

                            <button
                                onClick={() => setMode('receiver')}
                                className="btn btn-secondary"
                                style={{
                                    padding: '1.5rem',
                                    fontSize: '1rem',
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '0.5rem'
                                }}
                            >
                                <span style={{ fontSize: '2rem' }}>👂</span>
                                <span style={{ fontWeight: '600' }}>Join Session (Receiver)</span>
                                <span style={{ fontSize: '0.875rem', opacity: 0.8 }}>
                                    Join a session using a room code
                                </span>
                            </button>
                        </div>
                    </div>
                ) : mode === 'sender' ? (
                    /* Sender Setup */
                    <div className="glass-card" style={{ padding: '2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <button
                                onClick={() => setMode(null)}
                                className="btn"
                                style={{ marginRight: '1rem', padding: '0.5rem 1rem' }}
                            >
                                ← Back
                            </button>
                            <h2 style={{
                                fontSize: '1.25rem',
                                fontWeight: '600',
                                color: 'var(--color-text-primary)'
                            }}>
                                Create Session
                            </h2>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: '0.875rem',
                                    fontWeight: '600',
                                    marginBottom: '0.5rem',
                                    color: 'var(--color-text-secondary)'
                                }}>
                                    Your Name
                                </label>
                                <input
                                    type="text"
                                    value={senderName}
                                    onChange={(e) => setSenderName(e.target.value)}
                                    placeholder="Enter your name"
                                    className="input"
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem 1rem',
                                        fontSize: '1rem',
                                        border: '1px solid var(--glass-border)',
                                        borderRadius: 'var(--radius-md)',
                                        background: 'var(--color-bg-secondary)',
                                        color: 'var(--color-text-primary)'
                                    }}
                                />
                            </div>

                            <LanguageSelector
                                label="Source Language (Your Language)"
                                value={sourceLanguage}
                                onChange={setSourceLanguage}
                            />

                            {error && (
                                <div style={{
                                    padding: '1rem',
                                    background: 'rgba(239, 68, 68, 0.1)',
                                    border: '1px solid var(--color-error)',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-error)',
                                    fontSize: '0.875rem'
                                }}>
                                    {error}
                                </div>
                            )}

                            <button
                                onClick={handleCreateSession}
                                disabled={loading}
                                className="btn btn-primary"
                                style={{ width: '100%', padding: '1rem' }}
                            >
                                {loading ? 'Creating...' : 'Create Session & Get Room Code'}
                            </button>
                        </div>
                    </div>
                ) : (
                    /* Receiver Setup */
                    <div className="glass-card" style={{ padding: '2rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', marginBottom: '1.5rem' }}>
                            <button
                                onClick={() => setMode(null)}
                                className="btn"
                                style={{ marginRight: '1rem', padding: '0.5rem 1rem' }}
                            >
                                ← Back
                            </button>
                            <h2 style={{
                                fontSize: '1.25rem',
                                fontWeight: '600',
                                color: 'var(--color-text-primary)'
                            }}>
                                Join Session
                            </h2>
                        </div>

                        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: '0.875rem',
                                    fontWeight: '600',
                                    marginBottom: '0.5rem',
                                    color: 'var(--color-text-secondary)'
                                }}>
                                    Your Name
                                </label>
                                <input
                                    type="text"
                                    value={receiverName}
                                    onChange={(e) => setReceiverName(e.target.value)}
                                    placeholder="Enter your name"
                                    className="input"
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem 1rem',
                                        fontSize: '1rem',
                                        border: '1px solid var(--glass-border)',
                                        borderRadius: 'var(--radius-md)',
                                        background: 'var(--color-bg-secondary)',
                                        color: 'var(--color-text-primary)'
                                    }}
                                />
                            </div>

                            <div>
                                <label style={{
                                    display: 'block',
                                    fontSize: '0.875rem',
                                    fontWeight: '600',
                                    marginBottom: '0.5rem',
                                    color: 'var(--color-text-secondary)'
                                }}>
                                    Room Code
                                </label>
                                <input
                                    type="text"
                                    value={roomCode}
                                    onChange={(e) => setRoomCode(e.target.value.toUpperCase())}
                                    placeholder="Enter room code"
                                    className="input"
                                    style={{
                                        width: '100%',
                                        padding: '0.75rem 1rem',
                                        fontSize: '1.25rem',
                                        fontWeight: '600',
                                        textAlign: 'center',
                                        letterSpacing: '0.2em',
                                        border: '1px solid var(--glass-border)',
                                        borderRadius: 'var(--radius-md)',
                                        background: 'var(--color-bg-secondary)',
                                        color: 'var(--color-text-primary)'
                                    }}
                                    maxLength={10}
                                />
                            </div>

                            <LanguageSelector
                                label="Target Language (Your Language)"
                                value={targetLanguage}
                                onChange={setTargetLanguage}
                            />

                            {error && (
                                <div style={{
                                    padding: '1rem',
                                    background: 'rgba(239, 68, 68, 0.1)',
                                    border: '1px solid var(--color-error)',
                                    borderRadius: 'var(--radius-md)',
                                    color: 'var(--color-error)',
                                    fontSize: '0.875rem'
                                }}>
                                    {error}
                                </div>
                            )}

                            <button
                                onClick={handleJoinSession}
                                disabled={loading}
                                className="btn btn-primary"
                                style={{ width: '100%', padding: '1rem' }}
                            >
                                {loading ? 'Joining...' : 'Join Session'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

export default Home;
