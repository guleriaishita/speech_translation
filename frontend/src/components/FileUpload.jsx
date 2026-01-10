import React, { useState, useRef } from 'react';
import axios from 'axios';
import ProgressBar from './ProgressBar';
import StatusIndicator from './StatusIndicator';

const ALLOWED_FORMATS = ['.mp3', '.wav', '.m4a', '.ogg', '.flac', '.webm'];
const MAX_FILE_SIZE = 25 * 1024 * 1024; // 25MB

function FileUpload({ sourceLang, targetLang }) {
    const [file, setFile] = useState(null);
    const [isDragging, setIsDragging] = useState(false);
    const [uploading, setUploading] = useState(false);
    const [processing, setProcessing] = useState(false);
    const [progress, setProgress] = useState(0);
    const [status, setStatus] = useState('idle');
    const [statusMessage, setStatusMessage] = useState('');
    const [error, setError] = useState('');
    const [result, setResult] = useState(null);
    const fileInputRef = useRef(null);
    const pollIntervalRef = useRef(null);

    const validateFile = (file) => {
        // Check file extension
        const ext = file.name.substring(file.name.lastIndexOf('.')).toLowerCase();
        if (!ALLOWED_FORMATS.includes(ext)) {
            throw new Error(`Invalid file format. Allowed: ${ALLOWED_FORMATS.join(', ')}`);
        }

        // Check file size
        if (file.size > MAX_FILE_SIZE) {
            throw new Error('File size exceeds 25MB limit');
        }

        return true;
    };

    const handleFileSelect = (selectedFile) => {
        try {
            setError('');
            setResult(null);
            validateFile(selectedFile);
            setFile(selectedFile);
            setStatusMessage('File ready for upload');
        } catch (err) {
            setError(err.message);
            setFile(null);
        }
    };

    const handleDragOver = (e) => {
        e.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = (e) => {
        e.preventDefault();
        setIsDragging(false);
    };

    const handleDrop = (e) => {
        e.preventDefault();
        setIsDragging(false);

        const droppedFile = e.dataTransfer.files[0];
        if (droppedFile) {
            handleFileSelect(droppedFile);
        }
    };

    const handleFileInputChange = (e) => {
        const selectedFile = e.target.files[0];
        if (selectedFile) {
            handleFileSelect(selectedFile);
        }
    };

    const pollStatus = async (taskId) => {
        try {
            const response = await axios.get(`/api/audio/status/${taskId}/`);
            const data = response.data;

            setProgress(data.progress || 0);
            setStatusMessage(data.status_message || 'Processing...');

            // Check if complete
            if (data.state === 'SUCCESS' && data.audio_status === 'completed') {
                clearInterval(pollIntervalRef.current);
                setProcessing(false);
                setStatus('success');
                setStatusMessage('Translation complete!');
                setResult({
                    audioId: data.audio_id,
                    transcription: data.transcription,
                    translation: data.translation,
                    outputFile: data.output_file
                });
            } else if (data.state === 'FAILURE' || data.audio_status === 'failed') {
                clearInterval(pollIntervalRef.current);
                setProcessing(false);
                setStatus('error');
                setError(data.error || 'Processing failed');
            }
        } catch (err) {
            console.error('Error polling status:', err);
            clearInterval(pollIntervalRef.current);
            setProcessing(false);
            setStatus('error');
            setError('Failed to check processing status');
        }
    };

    const handleUpload = async () => {
        if (!file) return;

        try {
            setError('');
            setUploading(true);
            setStatus('processing');
            setStatusMessage('Uploading file...');
            setProgress(0);

            // Create FormData
            const formData = new FormData();
            formData.append('original_file', file);
            formData.append('source_language', sourceLang);
            formData.append('target_language', targetLang);

            // Upload file
            const response = await axios.post('/api/audio/upload/', formData, {
                headers: {
                    'Content-Type': 'multipart/form-data'
                }
            });

            const { task_id, audio_id } = response.data;

            setUploading(false);
            setProcessing(true);
            setStatusMessage('Processing audio...');

            // Start polling for status
            pollIntervalRef.current = setInterval(() => {
                pollStatus(task_id);
            }, 2000);

        } catch (err) {
            setUploading(false);
            setStatus('error');
            setError(err.response?.data?.error || err.message || 'Upload failed');
        }
    };

    const handleDownload = async () => {
        if (!result?.audioId) return;

        try {
            const response = await axios.get(`/api/audio/download/${result.audioId}/`, {
                responseType: 'blob'
            });

            // Create download link
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `translated_${targetLang}_${result.audioId}.mp3`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            setError('Failed to download file');
        }
    };

    const handleReset = () => {
        setFile(null);
        setUploading(false);
        setProcessing(false);
        setProgress(0);
        setStatus('idle');
        setStatusMessage('');
        setError('');
        setResult(null);
        if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current);
        }
    };

    return (
        <div className="animate-fade-in">
            {/* Drag and Drop Area */}
            <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => !file && fileInputRef.current?.click()}
                style={{
                    border: `2px dashed ${isDragging ? 'var(--color-accent-primary)' : 'var(--glass-border)'}`,
                    borderRadius: 'var(--radius-lg)',
                    padding: '3rem 2rem',
                    textAlign: 'center',
                    cursor: file ? 'default' : 'pointer',
                    background: isDragging ? 'rgba(99, 102, 241, 0.1)' : 'var(--color-bg-secondary)',
                    transition: 'all 0.2s ease',
                    marginBottom: '1.5rem'
                }}
            >
                <input
                    ref={fileInputRef}
                    type="file"
                    accept={ALLOWED_FORMATS.join(',')}
                    onChange={handleFileInputChange}
                    style={{ display: 'none' }}
                />

                {!file ? (
                    <>
                        <div style={{
                            fontSize: '3rem',
                            marginBottom: '1rem',
                            opacity: 0.5
                        }}>
                            🎵
                        </div>
                        <h3 style={{
                            fontSize: '1.125rem',
                            fontWeight: '600',
                            marginBottom: '0.5rem',
                            color: 'var(--color-text-primary)'
                        }}>
                            Drop your audio file here
                        </h3>
                        <p style={{
                            fontSize: '0.875rem',
                            color: 'var(--color-text-secondary)',
                            marginBottom: '0.5rem'
                        }}>
                            or click to browse
                        </p>
                        <p style={{
                            fontSize: '0.75rem',
                            color: 'var(--color-text-tertiary)'
                        }}>
                            Supported: {ALLOWED_FORMATS.join(', ')} • Max 25MB
                        </p>
                    </>
                ) : (
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '1rem'
                    }}>
                        <div style={{
                            fontSize: '2rem'
                        }}>
                            🎵
                        </div>
                        <div style={{ textAlign: 'left', flex: 1, maxWidth: '400px' }}>
                            <div style={{
                                fontSize: '0.875rem',
                                fontWeight: '600',
                                color: 'var(--color-text-primary)',
                                marginBottom: '0.25rem',
                                wordBreak: 'break-all'
                            }}>
                                {file.name}
                            </div>
                            <div style={{
                                fontSize: '0.75rem',
                                color: 'var(--color-text-secondary)'
                            }}>
                                {(file.size / 1024 / 1024).toFixed(2)} MB
                            </div>
                        </div>
                        {!uploading && !processing && (
                            <button
                                onClick={(e) => {
                                    e.stopPropagation();
                                    handleReset();
                                }}
                                className="btn btn-secondary"
                                style={{ padding: '0.5rem 1rem' }}
                            >
                                ✕
                            </button>
                        )}
                    </div>
                )}
            </div>

            {/* Status Indicator */}
            {(uploading || processing) && (
                <div style={{ marginBottom: '1.5rem' }}>
                    <StatusIndicator status={status} message={statusMessage} />
                </div>
            )}

            {/* Progress Bar */}
            {processing && (
                <div style={{ marginBottom: '1.5rem' }}>
                    <ProgressBar progress={progress} status={statusMessage} />
                </div>
            )}

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

            {/* Results */}
            {result && (
                <div style={{
                    padding: '1.5rem',
                    background: 'var(--color-bg-secondary)',
                    borderRadius: 'var(--radius-lg)',
                    border: '1px solid var(--glass-border)',
                    marginBottom: '1.5rem'
                }}>
                    <h3 style={{
                        fontSize: '1rem',
                        fontWeight: '600',
                        marginBottom: '1rem',
                        color: 'var(--color-text-primary)'
                    }}>
                        Translation Results
                    </h3>

                    {result.transcription && (
                        <div style={{ marginBottom: '1rem' }}>
                            <div style={{
                                fontSize: '0.75rem',
                                fontWeight: '600',
                                color: 'var(--color-text-tertiary)',
                                marginBottom: '0.5rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em'
                            }}>
                                Original Transcription
                            </div>
                            <div style={{
                                fontSize: '0.875rem',
                                color: 'var(--color-text-secondary)',
                                lineHeight: '1.6'
                            }}>
                                {result.transcription}
                            </div>
                        </div>
                    )}

                    {result.translation && (
                        <div style={{ marginBottom: '1rem' }}>
                            <div style={{
                                fontSize: '0.75rem',
                                fontWeight: '600',
                                color: 'var(--color-text-tertiary)',
                                marginBottom: '0.5rem',
                                textTransform: 'uppercase',
                                letterSpacing: '0.05em'
                            }}>
                                Translation
                            </div>
                            <div style={{
                                fontSize: '0.875rem',
                                color: 'var(--color-text-primary)',
                                fontWeight: '500',
                                lineHeight: '1.6'
                            }}>
                                {result.translation}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Action Buttons */}
            <div style={{
                display: 'flex',
                gap: '1rem',
                justifyContent: 'center'
            }}>
                {file && !uploading && !processing && !result && (
                    <button
                        onClick={handleUpload}
                        className="btn btn-primary"
                        style={{ minWidth: '150px' }}
                    >
                        Upload & Translate
                    </button>
                )}

                {result && (
                    <>
                        <button
                            onClick={handleDownload}
                            className="btn btn-primary"
                            style={{ minWidth: '150px' }}
                        >
                            📥 Download Audio
                        </button>
                        <button
                            onClick={handleReset}
                            className="btn btn-secondary"
                        >
                            Upload Another
                        </button>
                    </>
                )}
            </div>
        </div>
    );
}

export default FileUpload;
