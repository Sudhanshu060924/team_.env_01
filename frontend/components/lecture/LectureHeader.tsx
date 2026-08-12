"use client";

import { WSStatus } from "@/hooks/useLectureWebSocket";
import { LectureStatus } from "@/types/lecture";

interface LectureHeaderProps {
  title: string;
  wsStatus: WSStatus;
  lectureStatus: LectureStatus;
  selectedLanguage: string;
  onLanguageChange: (lang: "english" | "hindi" | "hinglish") => void;
  disabled?: boolean;
}

const WS_DOT: Record<string, string> = {
  connected:    "bg-green-500",
  connecting:   "bg-yellow-400 animate-pulse",
  disconnected: "bg-gray-400",
  error:        "bg-red-500",
};

export default function LectureHeader({
  title,
  wsStatus,
  lectureStatus,
  selectedLanguage,
  onLanguageChange,
  disabled = false,
}: LectureHeaderProps) {
  return (
    <header className="flex items-center justify-between px-4 h-12 border-b border-gray-200 shrink-0 bg-white">
      {/* Brand + title */}
      <div className="flex items-center gap-3 min-w-0">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/logo.jpg"
          alt="CSJMU"
          className="w-7 h-7 rounded-full object-cover border border-gray-200 shrink-0"
        />
        <span className="text-sm font-bold tracking-tight text-black whitespace-nowrap">
          VidyaRoom
        </span>
        {title && title !== "VidyaRoom" && (
          <span className="text-sm text-gray-600 truncate hidden sm:block">{title}</span>
        )}
        {lectureStatus === "live" && (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded border border-yellow-400 text-yellow-700 bg-yellow-50">
            <span className="w-1.5 h-1.5 rounded-full bg-yellow-500 animate-pulse" />
            Live
          </span>
        )}
        {lectureStatus === "completed" && (
          <span className="text-[10px] font-semibold px-2 py-0.5 rounded border border-green-300 text-green-700 bg-green-50">
            Completed
          </span>
        )}
      </div>

      {/* Right: connection dot + language */}
      <div className="flex items-center gap-3 shrink-0">
        <div className="flex items-center gap-1.5">
          <span className={`inline-block w-2 h-2 rounded-full ${WS_DOT[wsStatus] ?? WS_DOT.disconnected}`} />
          <span className="text-xs text-gray-500 hidden sm:block capitalize">{wsStatus}</span>
        </div>

        <label className="sr-only" htmlFor="header-lang-select">Language</label>
        <select
          id="header-lang-select"
          value={selectedLanguage}
          onChange={(e) => onLanguageChange(e.target.value as "english" | "hindi" | "hinglish")}
          disabled={disabled}
          className="bg-white text-black text-xs border border-gray-300 rounded px-2 py-1 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 cursor-pointer disabled:opacity-40 transition-colors"
        >
          <option value="english">English</option>
          <option value="hindi">Hindi</option>
          <option value="hinglish">Hinglish</option>
        </select>
      </div>
    </header>
  );
}
