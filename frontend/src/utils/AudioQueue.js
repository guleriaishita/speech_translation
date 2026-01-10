/**
 * AudioQueue - Manages smooth continuous playback of audio chunks
 * Handles buffering and seamless transitions between chunks
 */
class AudioQueue {
    constructor() {
        this.queue = [];
        this.isPlaying = false;
        this.audioContext = null;
        this.currentSource = null;
        this.nextStartTime = 0;
    }

    /**
     * Initialize audio context (must be called after user interaction)
     */
    async init() {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Resume context if suspended (some browsers require user interaction)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
        }
    }

    /**
     * Add audio chunk to queue
     * @param {Blob|ArrayBuffer} audioData - Audio data to play
     */
    async enqueue(audioData) {
        try {
            // Initialize if not already done
            await this.init();

            // Convert Blob to ArrayBuffer if needed
            let arrayBuffer;
            if (audioData instanceof Blob) {
                arrayBuffer = await audioData.arrayBuffer();
            } else if (audioData instanceof ArrayBuffer) {
                arrayBuffer = audioData;
            } else {
                console.error('Invalid audio data type');
                return;
            }

            // Decode audio data
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);

            this.queue.push(audioBuffer);

            // Start playback if not already playing
            if (!this.isPlaying) {
                this.playNext();
            }
        } catch (error) {
            console.error('Error enqueueing audio:', error);
        }
    }

    /**
     * Play next chunk in queue
     */
    playNext() {
        if (this.queue.length === 0) {
            this.isPlaying = false;
            this.nextStartTime = 0;
            return;
        }

        this.isPlaying = true;
        const audioBuffer = this.queue.shift();

        // Create buffer source
        const source = this.audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.audioContext.destination);

        // Schedule playback
        const currentTime = this.audioContext.currentTime;
        const startTime = Math.max(currentTime, this.nextStartTime);

        source.start(startTime);

        // Calculate next start time for seamless playback
        this.nextStartTime = startTime + audioBuffer.duration;

        // Play next chunk when this one ends
        source.onended = () => {
            this.playNext();
        };

        this.currentSource = source;
    }

    /**
     * Clear queue and stop playback
     */
    clear() {
        this.queue = [];

        if (this.currentSource) {
            try {
                this.currentSource.stop();
            } catch (error) {
                // Ignore if already stopped
            }
            this.currentSource = null;
        }

        this.isPlaying = false;
        this.nextStartTime = 0;
    }

    /**
     * Get current queue size
     */
    getQueueSize() {
        return this.queue.length;
    }

    /**
     * Check if audio is currently playing
     */
    getIsPlaying() {
        return this.isPlaying;
    }
}

export default AudioQueue;
