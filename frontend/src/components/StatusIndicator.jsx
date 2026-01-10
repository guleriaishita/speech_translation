import React from 'react';

const STATUS_TYPES = {
    idle: { color: 'var(--color-text-tertiary)', label: 'Idle' },
    connecting: { color: 'var(--color-warning)', label: 'Connecting...' },
    connected: { color: 'var(--color-success)', label: 'Connected' },
    processing: { color: 'var(--color-accent-primary)', label: 'Processing...' },
    error: { color: 'var(--color-error)', label: 'Error' },
    success: { color: 'var(--color-success)', label: 'Complete' },
};

function StatusIndicator({ status, message }) {
    const statusConfig = STATUS_TYPES[status] || STATUS_TYPES.idle;

    return (
        <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.75rem',
            padding: '0.75rem 1rem',
            background: 'var(--color-bg-tertiary)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--glass-border)'
        }}>
            <div style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                background: statusConfig.color,
                boxShadow: `0 0 10px ${statusConfig.color}`,
                animation: (status === 'processing' || status === 'connecting') ? 'pulse 2s infinite' : 'none'
            }} />
            <div style={{ flex: 1 }}>
                <div style={{
                    fontSize: '0.875rem',
                    fontWeight: '600',
                    color: 'var(--color-text-primary)'
                }}>
                    {message || statusConfig.label}
                </div>
            </div>
        </div>
    );
}

export default StatusIndicator;
