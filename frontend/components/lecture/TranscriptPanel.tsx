"use client";

import { useEffect, useRef, useState } from "react";

export interface TranscriptLine {
  timestamp: number;
  text: string;
  language: string;
}

interface TranscriptPanelProps {
  lines: TranscriptLine[];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function isNearBottom(element: HTMLElement | null, threshold = 100): boolean {
  if (!element) return true;
  const { scrollHeight, scrollTop, clientHeight } = element;
  return scrollHeight - scrollTop - clientHeight < threshold;
}

export default function TranscriptPanel({ lines }: TranscriptPanelProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hasNewContent, setHasNewContent] = useState(false);
  const lastLengthRef = useRef(lines.length);

  // Auto-scroll only if user is already near bottom
  useEffect(() => {
    if (lines.length > lastLengthRef.current) {
      const container = containerRef.current;
      if (container && isNearBottom(container)) {
        // User is near bottom, auto-scroll
        container.scrollTop = container.scrollHeight;
        setHasNewContent(false);
      } else if (container && lines.length > lastLengthRef.current) {
        // User has scrolled up, show indicator
        setHasNewContent(true);
      }
    }
    lastLengthRef.current = lines.length;
  }, [lines.length]);

  return (
    <div className="flex flex-col h-full min-h-0 bg-white">
      {/* Panel header */}
      <div className="px-4 pt-4 pb-3 border-b border-gray-200 shrink-0">
        <h2 className="text-[11px] font-semibold uppercase tracking-widest text-gray-600">
          Transcript
        </h2>
      </div>

      {/* Content */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-4 py-4">
        {lines.length === 0 ? (
          <p className="text-sm text-gray-500 italic">
            Waiting for transcript…
          </p>
        ) : (
          <div className="flex flex-col gap-4">
            {lines.map((line, i) => {
              const isLatest = i === lines.length - 1;
              return (
                <div key={i} className="flex gap-3 items-start">
                  <span className="text-xs text-yellow-500 tabular-nums shrink-0 mt-0.5 font-mono font-medium">
                    {formatTime(line.timestamp)}
                  </span>
                  <p
                    className={`text-sm leading-relaxed ${
                      isLatest ? "text-black font-medium" : "text-gray-700"
                    }`}
                  >
                    {line.text}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* New content indicator */}
      {hasNewContent && (
        <div className="border-t border-gray-200 px-4 py-2 shrink-0">
          <button
            onClick={() => {
              if (containerRef.current) {
                containerRef.current.scrollTop =
                  containerRef.current.scrollHeight;
                setHasNewContent(false);
              }
            }}
            className="text-xs font-medium text-yellow-600 hover:text-yellow-700 flex items-center gap-1"
            aria-label="Scroll to latest transcript"
          >
            New transcript ↓
          </button>
        </div>
      )}
    </div>
  );
}
