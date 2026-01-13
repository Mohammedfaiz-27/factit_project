import React, { useState, useRef } from 'react';
import { checkClaim, checkMultimodalClaim, checkURLClaim } from '../services/api';

export default function FactCheckerInput({ onResult, loading, setLoading }) {
  const [input, setInput] = useState('');
  const [error, setError] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isRecording, setIsRecording] = useState(false);
  const [inputMode, setInputMode] = useState('text'); // 'text', 'file', 'voice', 'link'

  const fileInputRef = useRef(null);
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      let result;

      if (inputMode === 'link') {
        // URL fact-checking endpoint
        result = await checkURLClaim(input);
      } else if (selectedFile) {
        // Multimodal endpoint (image/video/audio)
        result = await checkMultimodalClaim(input, selectedFile);
      } else {
        // Text-only endpoint
        result = await checkClaim(input);
      }

      onResult(result);
      // Reset form
      setInput('');
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      setSelectedFile(file);
      setError(null);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      audioChunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorder.onstop = () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        const audioFile = new File([audioBlob], 'recording.webm', { type: 'audio/webm' });
        setSelectedFile(audioFile);
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorder.start();
      setIsRecording(true);
      setError(null);
    } catch (err) {
      setError('Microphone access denied or not available');
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  return (
    <div className="fact-checker-input">
      <div className="input-mode-selector">
        <button
          type="button"
          className={`mode-btn ${inputMode === 'text' ? 'active' : ''}`}
          onClick={() => setInputMode('text')}
        >
          Text
        </button>
        <button
          type="button"
          className={`mode-btn ${inputMode === 'link' ? 'active' : ''}`}
          onClick={() => setInputMode('link')}
        >
          Link
        </button>
        <button
          type="button"
          className={`mode-btn ${inputMode === 'file' ? 'active' : ''}`}
          onClick={() => setInputMode('file')}
        >
          Image/Video
        </button>
        <button
          type="button"
          className={`mode-btn ${inputMode === 'voice' ? 'active' : ''}`}
          onClick={() => setInputMode('voice')}
        >
          Voice
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {inputMode === 'text' && (
          <input
            className="input-text"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Enter claim to fact-check"
            required={!selectedFile}
          />
        )}

        {inputMode === 'link' && (
          <input
            className="input-text"
            type="url"
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder="Enter article URL (e.g., https://example.com/article)"
            required
          />
        )}

        {inputMode === 'file' && (
          <div className="file-input-wrapper">
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*,video/*"
              onChange={handleFileChange}
              className="file-input"
            />
            {selectedFile && <span className="file-name">{selectedFile.name}</span>}
            <input
              className="input-text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Optional: Add context or question about the media"
            />
          </div>
        )}

        {inputMode === 'voice' && (
          <div className="voice-input-wrapper">
            {!isRecording ? (
              <button
                type="button"
                className="btn record-btn"
                onClick={startRecording}
              >
                Start Recording
              </button>
            ) : (
              <button
                type="button"
                className="btn stop-btn"
                onClick={stopRecording}
              >
                Stop Recording
              </button>
            )}
            {selectedFile && <span className="file-name">Recording ready</span>}
            <input
              className="input-text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Optional: Add context"
            />
          </div>
        )}

        <button
          className="btn submit-btn"
          type="submit"
          disabled={loading || (!input && !selectedFile)}
        >
          {loading ? 'Checking...' : 'Check Fact'}
        </button>

        {error && <div className="error-message">{error}</div>}
      </form>
    </div>
  );
}
