import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Home from './pages/Home';
import SenderSession from './pages/SenderSession';
import ReceiverSession from './pages/ReceiverSession';

function App() {
    return (
        <Router>
            <div style={{
                minHeight: '100vh',
                background: 'var(--color-bg-primary)',
                backgroundImage: 'radial-gradient(circle at 20% 20%, rgba(99, 102, 241, 0.1) 0%, transparent 50%), radial-gradient(circle at 80% 80%, rgba(139, 92, 246, 0.1) 0%, transparent 50%)'
            }}>
                <Routes>
                    <Route path="/" element={<Home />} />
                    <Route path="/sender/:roomCode" element={<SenderSession />} />
                    <Route path="/receiver/:roomCode" element={<ReceiverSession />} />
                    <Route path="*" element={<Navigate to="/" replace />} />
                </Routes>
            </div>
        </Router>
    );
}

export default App;
