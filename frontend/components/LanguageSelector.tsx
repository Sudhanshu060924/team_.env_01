'use client'

import { TargetLanguage, LANGUAGE_OPTIONS } from '@/types/ai'

interface LanguageSelectorProps {
  value: TargetLanguage
  onChange: (lang: TargetLanguage) => void
  disabled?: boolean
}

export default function LanguageSelector({ value, onChange, disabled = false }: LanguageSelectorProps) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value as TargetLanguage)}
      disabled={disabled}
      aria-label="Translation language"
      className="bg-gray-800 text-gray-200 text-xs rounded px-2 py-1 border border-gray-700 outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50 cursor-pointer"
    >
      {LANGUAGE_OPTIONS.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  )
}
