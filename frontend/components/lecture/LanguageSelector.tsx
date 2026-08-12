"use client";

import { TargetLanguage, LANGUAGE_OPTIONS } from "@/types/ai";

interface LanguageSelectorProps {
  value: TargetLanguage;
  onChange: (lang: TargetLanguage) => void;
  disabled?: boolean;
}

export default function LanguageSelector({
  value,
  onChange,
  disabled = false,
}: LanguageSelectorProps) {
  return (
    <>
      <label htmlFor="translation-lang-select" className="sr-only">
        Translation language
      </label>
      <select
        id="translation-lang-select"
        value={value}
        onChange={(e) => onChange(e.target.value as TargetLanguage)}
        disabled={disabled}
        className="bg-white text-black text-xs border border-gray-300 px-2 py-0.5 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 cursor-pointer disabled:opacity-40 transition-colors rounded"
      >
        {LANGUAGE_OPTIONS.map((opt) => (
          <option
            key={opt.value}
            value={opt.value}
            className="bg-white text-black"
          >
            {opt.label}
          </option>
        ))}
      </select>
    </>
  );
}
