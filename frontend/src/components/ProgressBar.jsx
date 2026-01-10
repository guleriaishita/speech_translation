import React from 'react';

function ProgressBar({ progress, status }) {
    return (
        <div style={{ width: '100%' }}>
            <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '0.5rem'
            }}>
                <span style={{
                    fontSize: '0.875rem',
                    color: 'var(--color-text-secondary)',
                    fontWeight: '500'
                }}>
                    {status || 'Processing...'}
                </span>
                <span style={{
                    fontSize: '0.875rem',
                    fontWeight: '600',
                    color: 'var(--color-accent-primary)'
                }}>
                    {progress}%
                </span>
            </div>
            <div style={{
                width: '100%',
                height: '8px',
                background: 'var(--color-bg-tertiary)',
                borderRadius: 'var(--radius-full)',
                overflow: 'hidden',
                position: 'relative'
            }}>
                <div
                    style={{
                        width: `${progress}%`,
                        height: '100%',
                        background: 'var(--color-accent-gradient)',
                        borderRadius: 'var(--radius-full)',
                        transition: 'width 0.3s ease',
                        boxShadow: '0 0 10px rgba(99, 102, 241, 0.5)'
                    }}
                />
            </div>
        </div>
    );
}

export default ProgressBar;
