import React from 'react';

const LANGUAGES = [
    { code: 'en', name: 'English' },
    { code: 'es', name: 'Spanish' },
    { code: 'fr', name: 'French' },
    { code: 'de', name: 'German' },
    { code: 'it', name: 'Italian' },
    { code: 'pt', name: 'Portuguese' },
    { code: 'ru', name: 'Russian' },
    { code: 'ja', name: 'Japanese' },
    { code: 'ko', name: 'Korean' },
    { code: 'zh', name: 'Chinese' },
    { code: 'ar', name: 'Arabic' },
    { code: 'hi', name: 'Hindi' },
];

function LanguageSelector({ label, value, onChange, disabled }) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <label style={{
                fontSize: '0.875rem',
                fontWeight: '500',
                color: 'var(--color-text-secondary)'
            }}>
                {label}
            </label>
            <select
                className="input-field"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                disabled={disabled}
            >
                {LANGUAGES.map((lang) => (
                    <option key={lang.code} value={lang.code}>
                        {lang.name}
                    </option>
                ))}
            </select>
        </div>
    );
}

export default LanguageSelector;
