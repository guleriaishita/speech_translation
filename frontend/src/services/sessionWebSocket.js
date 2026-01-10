/**
 * WebSocket service for session-based real-time translation
 */

class SessionWebSocket {
    constructor(roomCode, participantId, onMessage) {
        this.roomCode = roomCode;
        this.participantId = participantId;
        this.onMessage = onMessage;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 2000;
    }

    connect() {
        const wsUrl = `ws://127.0.0.1:8000/ws/session/${this.roomCode}/?participant_id=${this.participantId}`;

        console.log(`[WS] Connecting to ${wsUrl}`);

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            console.log('[WS] Connected');
            this.reconnectAttempts = 0;

            if (this.onMessage) {
                this.onMessage({
                    type: 'ws_connected',
                    message: 'WebSocket connected'
                });
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('[WS] Received:', data.type);

                if (this.onMessage) {
                    this.onMessage(data);
                }
            } catch (error) {
                console.error('[WS] Error parsing message:', error);
            }
        };

        this.ws.onerror = (error) => {
            console.error('[WS] Error:', error);

            if (this.onMessage) {
                this.onMessage({
                    type: 'error',
                    error: 'WebSocket error occurred'
                });
            }
        };

        this.ws.onclose = (event) => {
            console.log('[WS] Disconnected:', event.code);

            if (this.onMessage) {
                this.onMessage({
                    type: 'ws_disconnected',
                    code: event.code
                });
            }

            // Auto-reconnect
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.reconnectAttempts++;
                console.log(`[WS] Reconnecting attempt ${this.reconnectAttempts}...`);

                setTimeout(() => {
                    this.connect();
                }, this.reconnectDelay);
            }
        };
    }

    sendAudioFile(audioBase64) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'audio_file',
                audio_data: audioBase64
            }));
            console.log('[WS] Sent audio file');
        } else {
            console.error('[WS] Cannot send, not connected');
        }
    }

    requestHistory() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({
                type: 'get_history'
            }));
            console.log('[WS] Requested history');
        }
    }

    disconnect() {
        if (this.ws) {
            console.log('[WS] Disconnecting...');
            this.ws.close();
            this.ws = null;
        }
    }

    isConnected() {
        return this.ws && this.ws.readyState === WebSocket.OPEN;
    }
}

export default SessionWebSocket;
