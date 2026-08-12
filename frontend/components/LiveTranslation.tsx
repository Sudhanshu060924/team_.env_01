'use client'

import { useEffect, useRef } from 'react'
import { TranslationLine, TargetLanguage } from '@/types/ai'
import LanguageSelector from './LanguageSelector'

interface LiveTranslationProps {
  lines: TranslationLine[]
  selectedLanguage: TargetLanguage
  onLanguageChange: (lang: TargetLanguage) => void
  disabled?: boolean
}

const LANGUAGE_LABEL: Record<TargetLanguage, string> = {
  english:  'English',
  hindi:    'Hindi',
  hinglish: 'Hinglish',
}

export default function LiveTranslation({
  lines,
  selectedLanguage,
  onLanguageChange,
  disabled = false,
}: LiveTranslationProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to the newest translation
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [lines.length])

  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-3 min-h-[160px]">
      {/* Header row: title + language dropdown */}
      <div className="flex items-center justify-between shrink-0">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">
          Live Translation
        </h2>
        <LanguageSelector
          value={selectedLanguage}
          onChange={onLanguageChange}
          disabled={disabled}
        />
      </div>

      {/* Translation history */}
      {lines.length === 0 ? (
        <p className="text-xs text-gray-600 italic">
          Translations will appear here during the lecture…
        </p>
      ) : (
        <div className="overflow-y-auto flex-1 max-h-40 flex flex-col gap-3 pr-1">
          {lines.map((line, i) => (
            <div key={i} className="flex flex-col gap-1">
              <span className="text-xs text-gray-600 tabular-nums">
                {formatTime(line.timestamp)}
                <span className="ml-2 text-gray-700">
                  {LANGUAGE_LABEL[line.language] ?? line.language}
                </span>
              </span>
              <p
                className={`text-sm leading-relaxed ${
                  line.language === 'hinglish'
                    ? 'text-amber-200'
                    : line.language === 'hindi'
                    ? 'text-indigo-200'
                    : 'text-gray-100'
                }`}
              >
                {line.content}
              </p>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      )}
    </div>
  )
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  return `${m}:${String(s).padStart(2, '0')}`
}
