"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { ChatMessageRead } from "@/types/chat";

interface LectureChatProps {
  messages: ChatMessageRead[];
  onSend: (question: string) => void;
  isSending?: boolean;
  sendError?: string | null;
  disabled?: boolean;
}

export default function LectureChat({
  messages,
  onSend,
  isSending = false,
  sendError = null,
  disabled = false,
}: LectureChatProps) {
  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to newest message
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const q = input.trim();
      if (!q || disabled || isSending) return;
      onSend(q);
      setInput("");
    },
    [input, disabled, isSending, onSend]
  );

  const isDisabled = disabled || isSending;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <p className="text-[10px] uppercase tracking-widest text-gray-500 font-semibold mb-3 shrink-0">
        Ask AI about this lecture
      </p>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0 pr-1">
        {messages.length === 0 && (
          <p className="text-sm text-gray-500 italic">
            Ask anything about this lecture…
          </p>
        )}
        {messages.map((msg) => {
          const isStudent = msg.sender_role === "student";
          return (
            <div
              key={msg.id}
              className={`flex flex-col gap-1 ${isStudent ? "items-end" : "items-start"}`}
            >
              <span className="text-[10px] uppercase tracking-wider text-gray-600 font-semibold">
                {isStudent ? "You" : "AI"}
              </span>
              <div
                className={`max-w-[90%] px-3 py-2 text-sm leading-relaxed ${
                  isStudent
                    ? "bg-yellow-100 text-black border border-yellow-200"
                    : "bg-gray-100 text-black border border-gray-300"
                }`}
              >
                {msg.content}
              </div>
              {/* Show detected topic on AI messages */}
              {!isStudent && msg.detected_topic && (
                <span className="text-[10px] bg-gray-100 text-gray-600 border border-gray-200 px-2 py-0.5 rounded-full font-medium">
                  Topic: {msg.detected_topic}
                </span>
              )}
              <span className="text-[10px] text-gray-400">
                {new Date(msg.created_at).toLocaleTimeString([], {
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            </div>
          );
        })}

        <div ref={bottomRef} />
      </div>

      {/* Error */}
      {sendError && (
        <p className="text-xs text-red-600 mt-1 shrink-0">{sendError}</p>
      )}

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
            disabled
              ? "Lecture not available…"
              : isSending
              ? "Waiting for AI…"
              : "Ask your question…"
          }
          disabled={isDisabled}
          aria-label="Ask the AI a question about this lecture"
          className="flex-1 bg-white text-black text-sm border border-gray-300 px-3 py-2 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 placeholder-gray-500 disabled:opacity-40 transition-colors"
        />
        <button
          type="submit"
          disabled={isDisabled || !input.trim()}
          aria-label="Send question to AI"
          className="bg-yellow-500 text-black text-sm font-semibold px-4 py-2 disabled:opacity-30 hover:bg-yellow-600 transition-colors"
        >
          {isSending ? "…" : "Ask"}
        </button>
      </form>
    </div>
  );
}
