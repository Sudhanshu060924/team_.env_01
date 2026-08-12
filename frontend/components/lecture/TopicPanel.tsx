"use client";

import { TopicState } from "@/types/ai";

interface TopicPanelProps {
  topic: TopicState | null;
}

export default function TopicPanel({ topic }: TopicPanelProps) {
  return (
    <div>
      <p className="text-[11px] font-semibold uppercase tracking-widest text-gray-600 mb-3">
        Current Topic
      </p>
      {topic ? (
        <>
          <p className="text-base font-semibold text-black leading-snug">
            {topic.topic}
          </p>
          {topic.subtopic && (
            <p className="text-sm text-gray-600 mt-1">{topic.subtopic}</p>
          )}
        </>
      ) : (
        <p className="text-sm text-gray-500 italic">Topic will appear here…</p>
      )}
    </div>
  );
}
