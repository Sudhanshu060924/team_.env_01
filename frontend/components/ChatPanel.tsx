'use client'

import { useState, useRef, useEffect } from 'react'
import { ChatMessage } from '@/types/ai'

interface ChatPanelProps {
  messages: ChatMessage[]
  onSend: (question: string) => void
  disabled?: boolean
}

export default function ChatPanel({ messages, onSend, disabled = false }: ChatPanelProps) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    const q = input.trim()
    if (!q || disabled) return
    onSend(q)
    setInput('')
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-3 h-full overflow-hidden">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500 shrink-0">Ask a Doubt</h2>

      <div className="flex-1 overflow-y-auto flex flex-col gap-3 min-h-0">
        {messages.length === 0 && (
          <p className="text-xs text-gray-600 italic">Ask anything about the lecture…</p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex flex-col gap-0.5 ${msg.role === 'student' ? 'items-end' : 'items-start'}`}
          >
            <p className="text-xs text-gray-500">{msg.role === 'student' ? 'You' : 'VidyaRoom AI'}</p>
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm leading-relaxed ${
                msg.role === 'student'
                  ? 'bg-indigo-700 text-white'
                  : 'bg-gray-800 text-gray-100'
              }`}
            >
              {msg.content}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2 shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={disabled ? 'Start lecture first…' : 'Ask a question…'}
          disabled={disabled}
          className="flex-1 bg-gray-800 text-gray-100 text-sm rounded px-3 py-2 outline-none focus:ring-1 focus:ring-indigo-500 placeholder-gray-600 disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !input.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm px-4 py-2 rounded transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  )
}
