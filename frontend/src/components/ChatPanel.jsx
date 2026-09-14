import React, { useState, useRef, useEffect } from 'react';
import { sendChat } from '../api';

function renderInlineMarkdown(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, index) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    }
    return <React.Fragment key={index}>{part}</React.Fragment>;
  });
}

function AssistantMessage({ content }) {
  const lines = content.split(/\r?\n/);

  return (
    <div className="space-y-2 leading-6">
      {lines.map((line, index) => {
        const trimmed = line.trim();

        if (!trimmed || /^[-_]{3,}$/.test(trimmed)) return null;

        if (trimmed.startsWith('### ')) {
          return (
            <h3 key={index} className="pt-2 text-sm font-semibold text-slate-900">
              {renderInlineMarkdown(trimmed.slice(4))}
            </h3>
          );
        }

        if (trimmed.startsWith('* ')) {
          return (
            <div key={index} className="flex gap-2 pl-1">
              <span className="text-sky-500">•</span>
              <span>{renderInlineMarkdown(trimmed.slice(2))}</span>
            </div>
          );
        }

        return <p key={index}>{renderInlineMarkdown(trimmed)}</p>;
      })}
    </div>
  );
}

function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: 'assistant', content: 'Hi! I am Vistaar, your AI Business Advisor. How can I help you today?' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const suggestions = [
    "How am I doing vs last month?",
    "Why did you flag this?",
    "Which product should I focus on?",
    "When should I restock?"
  ];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSend = async (text) => {
    if (!text.trim()) return;
    
    const userMsg = { role: 'user', content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendChat(text);
      setMessages(prev => [...prev, { role: 'assistant', content: res.answer || 'I processed your request.' }]);
    } catch (error) {
      setMessages(prev => [...prev, { role: 'assistant', content: 'Sorry, I encountered an error connecting to the server.' }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-180px)] bg-white rounded-2xl shadow-sm border border-slate-100 overflow-hidden">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[85%] p-3 rounded-2xl text-sm ${
              msg.role === 'user' 
                ? 'bg-sky-500 text-white rounded-tr-sm' 
                : 'bg-slate-100 text-slate-800 rounded-tl-sm'
            }`}>
              {msg.role === 'assistant' ? <AssistantMessage content={msg.content} /> : msg.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 p-3 rounded-2xl rounded-tl-sm text-sm text-slate-500 flex gap-1 items-center">
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
              <span className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 border-t border-slate-100 bg-slate-50">
        {messages.length === 1 && (
          <div className="flex gap-2 overflow-x-auto pb-3 scrollbar-hide">
            {suggestions.map((sug, i) => (
              <button 
                key={i}
                onClick={() => handleSend(sug)}
                className="whitespace-nowrap px-3 py-1.5 bg-white border border-slate-200 text-xs text-sky-600 rounded-full hover:bg-sky-50 transition-colors shadow-sm"
              >
                {sug}
              </button>
            ))}
          </div>
        )}
        
        <form onSubmit={(e) => { e.preventDefault(); handleSend(input); }} className="flex gap-2">
          <input 
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask a question..."
            className="flex-1 px-4 py-2 bg-white border border-slate-200 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-sky-500"
            disabled={loading}
          />
          <button 
            type="submit"
            disabled={loading || !input.trim()}
            className="w-10 h-10 flex-shrink-0 bg-sky-500 text-white rounded-full flex items-center justify-center disabled:opacity-50 transition-colors"
          >
            ➤
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatPanel;
