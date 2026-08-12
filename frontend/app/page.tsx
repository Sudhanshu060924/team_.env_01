"use client";

import { useRef, useState, useCallback, useId } from "react";
import { useLecture } from "@/hooks/useLecture";
import { useLectureWebSocket } from "@/hooks/useLectureWebSocket";
import { useAudioCapture } from "@/hooks/useAudioCapture";
import { useFrameCapture } from "@/hooks/useFrameCapture";
import LectureHeader from "@/components/lecture/LectureHeader";
import LectureLayout from "@/components/lecture/LectureLayout";
import { TranscriptLine } from "@/components/lecture/TranscriptPanel";
import {
  WSMessage,
  TopicState,
  ImportantEvent,
  ChatMessage,
  TranslationLine,
  TargetLanguage,
} from "@/types/ai";
import UniversityWatermark from "@/components/layout/UniversityWatermark";

export default function HomePage() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uid = useId();

  const {
    lecture,
    status: lectureStatus,
    error,
    startLecture,
    completeLecture,
  } = useLecture();
  const [lectureTitle, setLectureTitle] = useState("Demo Lecture");

  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [videoSrc, setVideoSrc] = useState<string | null>(null);

  const [transcriptLines, setTranscriptLines] = useState<TranscriptLine[]>([]);
  const [translationLines, setTranslationLines] = useState<TranslationLine[]>([]);
  const [selectedLanguage, setSelectedLanguage] = useState<TargetLanguage>("english");
  const [topic, setTopic] = useState<TopicState | null>(null);
  const [importantEvents, setImportantEvents] = useState<ImportantEvent[]>([]);
  const [notes, setNotes] = useState<string | null>(null);
  const [isGeneratingNotes, setIsGeneratingNotes] = useState(false);
  const [isRegeneratingNotes, setIsRegeneratingNotes] = useState(false);
  const [notesError, setNotesError] = useState<string | null>(null);
  const [notesLanguage, setNotesLanguage] = useState<TargetLanguage>("english");
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;
      setVideoFile(file);
      setVideoSrc((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return URL.createObjectURL(file);
      });
      const name = file.name.replace(/\.[^.]+$/, "");
      setLectureTitle(name || "Demo Lecture");
    },
    []
  );

  const handleWsMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case "speech_event":
          if (msg.content) {
            setTranscriptLines((prev) => [
              ...prev,
              {
                timestamp: msg.timestamp ?? 0,
                text: msg.content!,
                language: (msg.metadata as Record<string, string>)?.language ?? "en",
              },
            ]);
          }
          break;
        case "translation":
          if (msg.content) {
            setTranslationLines((prev) => [
              ...prev,
              {
                timestamp: msg.timestamp ?? 0,
                content: msg.content!,
                language: ((msg.metadata as Record<string, string>)?.language ?? "english") as TargetLanguage,
                source: (msg.metadata as Record<string, string>)?.source,
              },
            ]);
          }
          break;
        case "topic_update":
          if (msg.content) {
            setTopic({
              topic: msg.content,
              subtopic: (msg.metadata as Record<string, string>)?.subtopic ?? "",
              timestamp: msg.timestamp ?? 0,
            });
          }
          break;
        case "important_event":
        case "board_event":
          if (msg.content) {
            setImportantEvents((prev) => [
              ...prev,
              {
                id: `${uid}-${Date.now()}`,
                timestamp: msg.timestamp ?? 0,
                content: msg.content!,
                isFormula: !!(msg.metadata as Record<string, boolean>)?.is_formula,
              },
            ]);
          }
          break;
        case "notes":
          if (msg.content) {
            setNotes(msg.content);
            setIsGeneratingNotes(false);
            setIsRegeneratingNotes(false);
            setNotesError(null);
            if ((msg as { language?: string }).language) {
              setNotesLanguage(
                (msg as { language?: string }).language as TargetLanguage
              );
            }
          }
          break;
        case "notes_generating":
          setIsRegeneratingNotes(true);
          setNotesError(null);
          break;
        case "lecture_completed":
          setIsGeneratingNotes(true);
          break;
        case "answer":
          if (msg.content) {
            setChatMessages((prev) => [
              ...prev,
              {
                id: `ai-${Date.now()}`,
                role: "ai",
                content: msg.content!,
                timestamp: Date.now(),
              },
            ]);
          }
          break;
        default:
          break;
      }
    },
    [uid]
  );

  const { status: wsStatus, sendMessage } = useLectureWebSocket({
    lectureId: lecture?.lecture_id ?? null,
    onMessage: handleWsMessage,
  });

  const isLive = lectureStatus === "live";
  const isCompleted = lectureStatus === "completed";

  useAudioCapture({
    videoRef,
    lectureId: lecture?.lecture_id ?? null,
    sendMessage,
    enabled: isLive,
    chunkMs: 5000,
  });

  useFrameCapture({
    videoRef,
    lectureId: lecture?.lecture_id ?? null,
    sendMessage,
    enabled: isLive,
    intervalMs: 3000,
  });

  const handleLanguageChange = useCallback(
    (lang: TargetLanguage) => {
      setSelectedLanguage(lang);
      if (lecture) {
        sendMessage({
          type: "language_change",
          lecture_id: lecture.lecture_id,
          target_language: lang,
        });
      }
    },
    [lecture, sendMessage]
  );

  const handleNotesLanguageChange = useCallback(
    (lang: TargetLanguage) => {
      setNotesLanguage(lang);
      if (lecture && isCompleted) {
        sendMessage({
          type: "generate_notes",
          lecture_id: lecture.lecture_id,
          target_language: lang,
        });
      }
    },
    [lecture, isCompleted, sendMessage]
  );

  const handleStart = async () => {
    const fileName = videoFile?.name ?? "demo.mp4";
    const result = await startLecture(lectureTitle, fileName);
    if (result) {
      videoRef.current?.play().catch(() => {});
    }
  };

  const handleVideoEnded = useCallback(() => {
    if (!lecture) return;
    sendMessage({
      type: "lecture_completed",
      lecture_id: lecture.lecture_id,
      timestamp: videoRef.current?.duration ?? 0,
    });
    completeLecture();
  }, [lecture, sendMessage, completeLecture]);

  const handleQuestion = useCallback(
    (question: string) => {
      if (!lecture) return;
      setChatMessages((prev) => [
        ...prev,
        {
          id: `student-${Date.now()}`,
          role: "student",
          content: question,
          timestamp: Date.now(),
        },
      ]);
      sendMessage({
        type: "question",
        lecture_id: lecture.lecture_id,
        content: question,
        timestamp: videoRef.current?.currentTime ?? 0,
      });
    },
    [lecture, sendMessage]
  );

  const canStart =
    lectureStatus === "idle" ||
    lectureStatus === "error" ||
    lectureStatus === "starting";

  return (
    <div className="h-screen bg-white text-black flex flex-col font-sans overflow-hidden">
      <LectureHeader
        title={lecture?.title ?? "VidyaRoom"}
        wsStatus={wsStatus}
        lectureStatus={lectureStatus}
        selectedLanguage={selectedLanguage}
        onLanguageChange={handleLanguageChange}
        disabled={!isLive}
      />

      {/* ── Start screen ─────────────────────────────────────────────── */}
      {canStart && (
        <div className="flex-1 flex items-center justify-center p-6 relative overflow-hidden">
          <UniversityWatermark />
          <div className="w-full max-w-sm flex flex-col gap-6 border border-gray-200 p-8 bg-white rounded-lg relative z-10">
            <div className="flex items-center gap-3">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src="/logo.jpg"
                alt="CSJMU Kanpur"
                className="w-10 h-10 rounded-full object-cover border border-gray-200"
              />
              <div>
                <h1 className="text-base font-bold text-black">Upload Lecture</h1>
                <p className="text-xs text-gray-500">CSJMU Kanpur · VidyaRoom</p>
              </div>
            </div>

            {/* Video file picker */}
            <div className="flex flex-col gap-2">
              <label className="text-[11px] font-semibold uppercase tracking-widest text-gray-600">
                Video File
              </label>
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                aria-label="Choose video file"
                className="cursor-pointer border border-dashed border-gray-300 hover:border-yellow-500 px-4 py-6 flex flex-col items-center gap-2 transition-colors w-full text-center bg-white hover:bg-yellow-50 rounded-lg"
              >
                {videoFile ? (
                  <>
                    <span className="text-2xl" aria-hidden="true">▶</span>
                    <span className="text-sm text-black break-all">{videoFile.name}</span>
                    <span className="text-xs text-gray-600">
                      {(videoFile.size / 1024 / 1024).toFixed(1)} MB · click to change
                    </span>
                  </>
                ) : (
                  <>
                    <span className="text-3xl text-gray-400" aria-hidden="true">▶</span>
                    <span className="text-sm text-gray-700">Click to choose a video file</span>
                    <span className="text-xs text-gray-500">MP4, WebM, MOV, MKV…</span>
                  </>
                )}
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="video/*"
                className="hidden"
                onChange={handleFileChange}
                aria-label="Video file input"
              />
            </div>

            {/* Lecture title */}
            <div className="flex flex-col gap-2">
              <label
                htmlFor="lecture-title-input"
                className="text-[11px] font-semibold uppercase tracking-widest text-gray-600"
              >
                Lecture Title
              </label>
              <input
                id="lecture-title-input"
                type="text"
                value={lectureTitle}
                onChange={(e) => setLectureTitle(e.target.value)}
                className="bg-white text-black border border-gray-300 rounded px-3 py-2 text-sm outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 transition-colors"
                placeholder="e.g. Binary Search"
              />
            </div>

            {error && (
              <p className="text-xs text-red-700 border border-red-300 px-3 py-2 bg-red-50 rounded">
                ⚠ {error}
              </p>
            )}

            <button
              onClick={handleStart}
              disabled={lectureStatus === "starting" || !videoFile}
              className="bg-yellow-400 text-black font-semibold py-2.5 text-sm hover:bg-yellow-500 disabled:opacity-30 transition-colors rounded-md flex items-center justify-center gap-2"
            >
              {lectureStatus === "starting" ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  Starting…
                </>
              ) : (
                "▶  Start Lecture"
              )}
            </button>

            {!videoFile && (
              <p className="text-xs text-gray-500 text-center">Select a video to enable start</p>
            )}
          </div>
        </div>
      )}

      {/* ── Live / Completed view ─────────────────────────────────────── */}
      {(isLive || isCompleted) && (
        <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
          <LectureLayout
            videoRef={videoRef}
            videoSrc={videoSrc}
            onVideoEnded={handleVideoEnded}
            transcriptLines={transcriptLines}
            translationLines={translationLines}
            selectedLanguage={selectedLanguage}
            onLanguageChange={handleLanguageChange}
            topic={topic}
            importantEvents={importantEvents}
            notes={notes}
            isGeneratingNotes={isGeneratingNotes}
            isRegeneratingNotes={isRegeneratingNotes}
            notesError={notesError}
            notesLanguage={notesLanguage}
            onNotesLanguageChange={handleNotesLanguageChange}
            chatMessages={chatMessages}
            onChatSend={handleQuestion}
            isLive={isLive}
            isCompleted={isCompleted}
            lectureTitle={lecture?.title ?? ""}
          />
        </div>
      )}
    </div>
  );
}
