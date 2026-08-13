"use client";

import { TopicState } from "@/types/ai";

interface TopicPanelProps {
  topics: TopicState[];
  onSeek?: (seconds: number) => void;
  noSpeechDetected?: boolean;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function TopicPanel({
  topics,
  onSeek,
  noSpeechDetected = false,
}: TopicPanelProps) {
  if (topics.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">
        {noSpeechDetected
          ? "No speech detected in this video."
          : "Topics will appear here…"}
      </p>
    );
  }

  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-600 mb-3">
        Topics
      </p>
      <ul className="flex flex-col gap-3">
        {topics.map((t, i) => (
          <li key={i} className="flex gap-3 items-start">
            <button
              onClick={() => onSeek?.(t.timestamp)}
              className="text-xs text-yellow-500 tabular-nums shrink-0 mt-0.5 font-mono font-medium hover:text-yellow-600 hover:underline transition-colors cursor-pointer"
              title={`Seek to ${formatTime(t.timestamp)}`}
              aria-label={`Seek video to ${formatTime(t.timestamp)}`}
            >
              {formatTime(t.timestamp)}
            </button>
            <div>
              <p className="text-sm font-semibold text-black leading-snug">
                {t.topic}
              </p>
              {t.subtopic && (
                <p className="text-xs text-gray-500 mt-0.5">{t.subtopic}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
