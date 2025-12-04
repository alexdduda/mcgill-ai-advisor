import React, { useState, useEffect, useRef } from 'react';
import { FaArrowUp } from "react-icons/fa6";
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import './App.css';

// --- TYPING INDICATOR COMPONENT ---
const TypingIndicator = () => (
  <div className="typing-indicator">
    <div className="dot"></div>
    <div className="dot"></div>
    <div className="dot"></div>
  </div>
);

export default function ChatInterface() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(scrollToBottom, [messages, isLoading]);

  // Fetch History on Mount
  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const res = await axios.get('http://localhost:8000/history/guest');
        setMessages(res.data);
      } catch (err) {
        console.error("Failed to load history:", err);
      }
    };
    fetchHistory();
  }, []);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const response = await axios.post('http://localhost:8000/chat', {
        username: "guest",
        message: input
      });

      const botMessage = { 
        role: 'assistant', 
        content: response.data.response 
      };
      
      setMessages(prev => [...prev, botMessage]);
    } catch (error) {
      console.error("Error:", error);
      setMessages(prev => [...prev, { role: 'error', content: '❌ Error connecting to server.' }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="chat-container">
      {/* Styles for the typing indicator animation included here for convenience */}
      <style>{`
        .typing-indicator {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 4px;
          padding: 5px;
        }
        .dot {
          width: 6px;
          height: 6px;
          background-color: currentColor; /* Uses text color of parent */
          border-radius: 50%;
          opacity: 0.6;
          animation: pulse 1.4s infinite ease-in-out both;
        }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        .dot:nth-child(3) { animation-delay: 0s; }
        
        @keyframes pulse {
          0%, 80%, 100% { transform: scale(0); }
          40% { transform: scale(1); }
        }
      `}</style>

      <header className="chat-header">
        <h1>🎓 McGill AI Advisor</h1>
      </header>
      
      <div className="messages-area">
        {messages.map((msg, index) => (
          <div key={index} className={`message-row ${msg.role}`}>
            <div className={`message-bubble ${msg.role}`}>
              <ReactMarkdown>{msg.content}</ReactMarkdown>
            </div>
          </div>
        ))}
        
        {/* Loading Bubble Logic */}
        {isLoading && (
          <div className="message-row assistant">
            <div className="message-bubble assistant">
              <TypingIndicator />
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
      </div>

      <form className="input-area" onSubmit={sendMessage}>
        <input 
          type="text" 
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about courses (e.g. 'hardest CS classes')..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading}>
          <FaArrowUp />
        </button>
      </form>
    </div>
  );
}