"use client";

import { useState, useRef, useEffect } from "react";
import { ChatMessage } from "@/types/ai";

interface LectureChatProps {
  messages: ChatMessage[];
  onSend: (question: string) => void;
  disabled?: boolean;
}

export default function LectureChat({
  messages,
  onSend,
  disabled = false,
}: LectureChatProps) {
  const [input, setInput] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll only if near bottom
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    // Scroll to bottom if user is near bottom
    if (
      container.scrollHeight - container.scrollTop - container.clientHeight <
      100
    ) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || disabled) return;
    onSend(q);
    setInput("");
  };

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Messages */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0"
      >
        {messages.length === 0 && (
          <p className="text-sm text-gray-500 italic">
            Ask anything about this lecture…
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-1 ${msg.role === "student" ? "items-end" : "items-start"}`}
          >
            <span className="text-[10px] uppercase tracking-wider text-gray-600 font-semibold">
              {msg.role === "student" ? "You" : "AI"}
            </span>
            <div
              className={`max-w-[90%] px-3 py-2 text-sm leading-relaxed rounded ${
                msg.role === "student"
                  ? "bg-yellow-100 text-black"
                  : "bg-gray-100 text-black border border-gray-300"
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="flex gap-2 mt-3 shrink-0 border-t border-gray-200 pt-3"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            disabled ? "Start lecture first…" : "Ask about this lecture…"
          }
          disabled={disabled}
          aria-label="Ask a question about this lecture"
          className="flex-1 bg-white text-black text-sm border border-gray-300 px-3 py-2 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 placeholder-gray-500 disabled:opacity-40 transition-colors"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          aria-label="Send question"
          className="bg-yellow-500 text-black text-sm font-semibold px-4 py-2 rounded disabled:opacity-30 hover:bg-yellow-600 transition-colors"
        >
          Ask
        </button>
      </form>
    </div>
  );
}
