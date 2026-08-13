"use client";

import { useState } from "react";
import {
  TopicState,
  ImportantEvent,
  TranslationLine,
  TargetLanguage,
  TranscriptChunk,
} from "@/types/ai";
import { ChatMessageRead } from "@/types/chat";
import LectureVideo from "./LectureVideo";
import TranscriptPanel from "./TranscriptPanel";
import TranslationPanel from "./TranslationPanel";
import TopicPanel from "./TopicPanel";
import ImportantEventsPanel from "./ImportantEventsPanel";
import NotesPanel from "./NotesPanel";
import LectureChat from "./LectureChat";
import DoubtsPanel from "./DoubtsPanel";
import LectureRatingPanel from "./LectureRatingPanel";

type Tab = "transcript" | "topics" | "events" | "notes" | "chat" | "doubts" | "rate";

const TABS: { id: Tab; label: string }[] = [
  { id: "transcript", label: "Transcript" },
  { id: "topics",     label: "Topics" },
  { id: "events",     label: "Important Events" },
  { id: "notes",      label: "Notes" },
  { id: "chat",       label: "Chat" },
  { id: "doubts",     label: "Doubts" },
  { id: "rate",       label: "Rate" },
];

interface LectureLayoutProps {
  videoRef: React.RefObject<HTMLVideoElement | null>;
  videoSrc: string | null;
  onVideoEnded: () => void;
  onSeek?: (seconds: number) => void;
  // Transcript
  transcriptChunks: TranscriptChunk[];
  // Translation
  translationLines: TranslationLine[];
  selectedLanguage: TargetLanguage;
  onLanguageChange: (lang: TargetLanguage) => void;
  // Topics
  topics: TopicState[];
  importantEvents: ImportantEvent[];
  notes: string | null;
  isGeneratingNotes: boolean;
  notesError?: string | null;
  notesLanguage: TargetLanguage;
  onNotesLanguageChange: (lang: TargetLanguage) => void;
  // Chat tab (student ↔ AI chatbot)
  aiChatMessages: ChatMessageRead[];
  onChatSend: (q: string) => void;
  isAiChatSending?: boolean;
  aiChatError?: string | null;
  isLive: boolean;
  isCompleted: boolean;
  lectureTitle: string;
  /** True when the processing pipeline found no speech in the video */
  noSpeechDetected?: boolean;
  // Doubts tab (student ↔ teacher)
  doubtMessages?: ChatMessageRead[];
  onDoubtSend?: (content: string) => void;
  isDoubtSending?: boolean;
  doubtSendError?: string | null;
  showDoubts?: boolean;
  lectureId?: string;
}

export default function LectureLayout({
  videoRef,
  videoSrc,
  onVideoEnded,
  onSeek,
  transcriptChunks,
  translationLines,
  selectedLanguage,
  onLanguageChange,
  topics,
  importantEvents,
  notes,
  isGeneratingNotes,
  notesError = null,
  notesLanguage,
  onNotesLanguageChange,
  aiChatMessages,
  onChatSend,
  isAiChatSending = false,
  aiChatError = null,
  isLive,
  isCompleted,
  lectureTitle,
  noSpeechDetected = false,
  doubtMessages = [],
  onDoubtSend,
  isDoubtSending = false,
  doubtSendError = null,
  showDoubts = false,
  lectureId,
}: LectureLayoutProps) {
  const [activeTab, setActiveTab] = useState<Tab>("transcript");

  const visibleTabs = TABS.filter((tab) => {
    if (tab.id === "doubts") return showDoubts;
    if (tab.id === "rate") return !!lectureId;
    return true;
  });

  return (
    /*
     * IMPORTANT: This outer div uses h-full (inherits from h-screen parent).
     * NO overflow-y-auto here — the page must never scroll as a whole.
     * Each inner panel handles its own scrolling independently.
     */
    <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
      {/* ── Top section: Video (left) + Translation (right) ── */}
      <div className="flex flex-col lg:grid lg:grid-cols-[3fr_2fr] min-h-0 flex-1 overflow-hidden border-b border-gray-200">
        {/* Left — Video: fills available height, never expands page */}
        <div className="bg-black lg:overflow-hidden flex items-center justify-center border-b border-gray-200 lg:border-b-0 lg:border-r lg:border-gray-200"
          style={{ minHeight: 0 }}
        >
          <LectureVideo
            ref={videoRef}
            src={videoSrc ?? undefined}
            lectureId={lectureId}
            onEnded={onVideoEnded}
          />
        </div>

        {/* Right — Translation (full height) */}
        <div className="flex flex-col min-h-0 overflow-hidden">
          <TranslationPanel
            lines={translationLines}
            selectedLanguage={selectedLanguage}
            onLanguageChange={onLanguageChange}
            onSeek={onSeek}
            noSpeechDetected={noSpeechDetected}
          />
        </div>
      </div>

      {/* ── Bottom section: tabbed panel ────────────────────────────── */}
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
          {activeTab === "transcript" && (
            <div id="tabpanel-transcript" role="tabpanel" aria-labelledby="tab-transcript" className="h-full">
              <TranscriptPanel
                chunks={transcriptChunks}
                onSeek={onSeek}
                noSpeechDetected={noSpeechDetected}
              />
            </div>
          )}
          {activeTab === "topics" && (
            <div id="tabpanel-topics" role="tabpanel" aria-labelledby="tab-topics">
              <TopicPanel
                topics={topics}
                onSeek={onSeek}
                noSpeechDetected={noSpeechDetected}
              />
            </div>
          )}
          {activeTab === "events" && (
            <div id="tabpanel-events" role="tabpanel" aria-labelledby="tab-events">
              <ImportantEventsPanel events={importantEvents} onSeek={onSeek} />
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
                notesError={notesError}
                lectureCompleted={isCompleted}
                notesLanguage={notesLanguage}
                onNotesLanguageChange={onNotesLanguageChange}
                lectureTitle={lectureTitle}
                noSpeechDetected={noSpeechDetected}
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
                messages={aiChatMessages}
                onSend={onChatSend}
                isSending={isAiChatSending}
                sendError={aiChatError}
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
          {activeTab === "rate" && lectureId && (
            <div
              id="tabpanel-rate"
              role="tabpanel"
              aria-labelledby="tab-rate"
            >
              <LectureRatingPanel lectureId={lectureId} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
