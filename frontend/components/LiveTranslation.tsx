'use client'

import { Translation } from '@/types/ai'

interface LiveTranslationProps {
  translations: Translation[]
  targetLanguage?: string
}

export default function LiveTranslation({ translations, targetLanguage = 'Hindi' }: LiveTranslationProps) {
  const latest = translations[translations.length - 1]

  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-3 h-full min-h-[140px]">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Live Translation</h2>
      {latest ? (
        <div className="flex flex-col gap-3">
          <div>
            <p className="text-xs text-gray-500 mb-1">Teacher</p>
            <p className="text-sm text-gray-100 leading-relaxed">{latest.original}</p>
          </div>
          <div>
            <p className="text-xs text-gray-500 mb-1">{targetLanguage}</p>
            <p className="text-sm text-indigo-300 leading-relaxed">{latest.translated}</p>
          </div>
        </div>
      ) : (
        <p className="text-xs text-gray-600 italic">Translations will appear here during the lecture…</p>
      )}
    </div>
  )
}
