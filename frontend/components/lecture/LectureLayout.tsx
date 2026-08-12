"use client";

import { useState } from "react";
import {
  TopicState,
  ImportantEvent,
  ChatMessage,
  TranslationLine,
  TargetLanguage,
} from "@/types/ai";
import { ChatMessageRead } from "@/types/chat";
import { TranscriptLine } from "./TranscriptPanel";
import LectureVideo from "./LectureVideo";
import TranscriptPanel from "./TranscriptPanel";
import TranslationPanel from "./TranslationPanel";
import TopicPanel from "./TopicPanel";
import ImportantEventsPanel from "./ImportantEventsPanel";
import NotesPanel from "./NotesPanel";
import LectureChat from "./LectureChat";
import DoubtsPanel from "./DoubtsPanel";

type Tab = "topics" | "events" | "notes" | "chat" | "doubts";

const TABS: { id: Tab; label: string; icon?: string }[] = [
  { id: "topics",  label: "Topics",           icon: "☰" },
  { id: "events",  label: "Important Events",  icon: "⚡" },
  { id: "notes",   label: "Notes",             icon: "📋" },
  { id: "chat",    label: "Chat",              icon: "💬" },
  { id: "doubts",  label: "Doubts",            icon: "❓" },
];

interface LectureLayoutProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoSrc: string | null;
  onVideoEnded: () => void;
  transcriptLines: TranscriptLine[];
  translationLines: TranslationLine[];
  selectedLanguage: TargetLanguage;
  onLanguageChange: (lang: TargetLanguage) => void;
  topic: TopicState | null;
  importantEvents: ImportantEvent[];
  notes: string | null;
  isGeneratingNotes: boolean;
  isRegeneratingNotes?: boolean;
  notesError?: string | null;
  notesLanguage: TargetLanguage;
  onNotesLanguageChange: (lang: TargetLanguage) => void;
  chatMessages: ChatMessage[];
  onChatSend: (q: string) => void;
  isLive: boolean;
  isCompleted: boolean;
  lectureTitle: string;
  // Doubts (student ↔ teacher)
  doubtMessages?: ChatMessageRead[];
  onDoubtSend?: (content: string) => void;
  isDoubtSending?: boolean;
  doubtSendError?: string | null;
  showDoubts?: boolean;
}

export default function LectureLayout({
  videoRef,
  videoSrc,
  onVideoEnded,
  transcriptLines,
  translationLines,
  selectedLanguage,
  onLanguageChange,
  topic,
  importantEvents,
  notes,
  isGeneratingNotes,
  isRegeneratingNotes = false,
  notesError = null,
  notesLanguage,
  onNotesLanguageChange,
  chatMessages,
  onChatSend,
  isLive,
  isCompleted,
  lectureTitle,
  doubtMessages = [],
  onDoubtSend,
  isDoubtSending = false,
  doubtSendError = null,
  showDoubts = false,
}: LectureLayoutProps) {
  const [activeTab, setActiveTab] = useState<Tab>("topics");

  const visibleTabs = TABS.filter((tab) => tab.id !== "doubts" || showDoubts);

  return (
    /*
     * IMPORTANT: This outer div uses h-full (inherits from h-screen parent).
     * NO overflow-y-auto here — the page must never scroll as a whole.
     * Each inner panel handles its own scrolling independently.
     */
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* ── Top section: Video (left) + Transcript/Translation (right) ── */}
      <div className="flex flex-col lg:grid lg:grid-cols-[3fr_2fr] min-h-0 flex-1 overflow-hidden border-b border-gray-200">
        {/* Left — Video: fills available height, never expands page */}
        <div className="bg-black lg:overflow-hidden flex items-center justify-center border-b border-gray-200 lg:border-b-0 lg:border-r lg:border-gray-200"
          style={{ minHeight: 0 }}
        >
          <LectureVideo
            ref={videoRef}
            src={videoSrc ?? undefined}
            onEnded={onVideoEnded}
          />
        </div>

        {/* Right — Transcript (top half) + Translation (bottom half) */}
        <div className="flex flex-col min-h-0 overflow-hidden divide-y divide-gray-200">
          {/* Transcript — scrolls internally; NEVER expands page */}
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            <TranscriptPanel lines={transcriptLines} />
          </div>
          {/* Translation — scrolls internally; NEVER expands page */}
          <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
            <TranslationPanel
              lines={translationLines}
              selectedLanguage={selectedLanguage}
              onLanguageChange={onLanguageChange}
              disabled={!isLive}
            />
          </div>
        </div>
      </div>

      {/* ── Bottom section: tabbed panel ────────────────────────────── */}
      {/*
       * flex-shrink-0 with explicit height — does NOT grow to push content.
       * 300px on desktop, taller on mobile where transcript/translation
       * are stacked above and the overall container scrolls.
       */}
      <div className="flex flex-col shrink-0 bg-white" style={{ height: '300px' }}>
        {/* Tab bar */}
        <div
          className="flex border-b border-gray-200 shrink-0 bg-white overflow-x-auto"
          role="tablist"
          aria-label="Lecture sections"
        >
          {visibleTabs.map((tab) => (
            <button
              key={tab.id}
              role="tab"
              aria-selected={activeTab === tab.id}
              aria-controls={`tabpanel-${tab.id}`}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={[
                'flex items-center gap-1.5 px-4 py-3 text-xs font-medium transition-colors border-b-2 -mb-px whitespace-nowrap',
                activeTab === tab.id
                  ? 'border-yellow-500 text-yellow-600 font-semibold'
                  : 'border-transparent text-gray-500 hover:text-gray-700',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab panels — each manages its own internal scroll */}
        <div className="flex-1 min-h-0 overflow-y-auto p-5">
          {activeTab === "topics" && (
            <div id="tabpanel-topics" role="tabpanel" aria-labelledby="tab-topics">
              <TopicPanel topic={topic} />
            </div>
          )}
          {activeTab === "events" && (
            <div id="tabpanel-events" role="tabpanel" aria-labelledby="tab-events">
              <ImportantEventsPanel events={importantEvents} />
            </div>
          )}
          {activeTab === "notes" && (
            <div
              id="tabpanel-notes"
              role="tabpanel"
              aria-labelledby="tab-notes"
              className="h-full"
            >
              <NotesPanel
                notes={notes}
                isGenerating={isGeneratingNotes}
                isRegenerating={isRegeneratingNotes}
                notesError={notesError}
                lectureCompleted={isCompleted}
                notesLanguage={notesLanguage}
                onNotesLanguageChange={onNotesLanguageChange}
                lectureTitle={lectureTitle}
              />
            </div>
          )}
          {activeTab === "chat" && (
            <div
              id="tabpanel-chat"
              role="tabpanel"
              aria-labelledby="tab-chat"
              className="h-full flex flex-col min-h-0"
            >
              <LectureChat
                messages={chatMessages}
                onSend={onChatSend}
                disabled={!isLive && !isCompleted}
              />
            </div>
          )}
          {activeTab === "doubts" && showDoubts && (
            <div
              id="tabpanel-doubts"
              role="tabpanel"
              aria-labelledby="tab-doubts"
              className="h-full flex flex-col min-h-0"
            >
              <DoubtsPanel
                messages={doubtMessages}
                onSend={onDoubtSend ?? (() => {})}
                isSending={isDoubtSending}
                sendError={doubtSendError}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
