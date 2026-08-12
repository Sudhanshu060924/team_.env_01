"use client";

import { ImportantEvent } from "@/types/ai";

interface ImportantEventsPanelProps {
  events: ImportantEvent[];
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function ImportantEventsPanel({
  events,
}: ImportantEventsPanelProps) {
  if (events.length === 0) {
    return (
      <p className="text-sm text-gray-500 italic">
        Key concepts &amp; formulas will appear here…
      </p>
    );
  }

  return (
    <ul className="flex flex-col gap-4">
      {[...events].reverse().map((evt) => (
        <li key={evt.id} className="flex gap-3 items-start">
          <span className="text-xs text-yellow-500 tabular-nums shrink-0 mt-0.5 font-mono font-medium">
            {formatTime(evt.timestamp)}
          </span>
          <div>
            <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-0.5">
              {evt.isFormula ? "Formula" : "Important concept"}
            </p>
            <p
              className={`text-sm leading-relaxed ${
                evt.isFormula ? "font-mono text-yellow-600" : "text-black"
              }`}
            >
              {evt.content}
            </p>
          </div>
        </li>
      ))}
    </ul>
  );
}
