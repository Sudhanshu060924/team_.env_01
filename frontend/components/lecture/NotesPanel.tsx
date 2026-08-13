"use client";

import { useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";
import { TargetLanguage, LANGUAGE_OPTIONS } from "@/types/ai";

// ── Markdown component map (VidyaRoom design: white/black/yellow) ──────────────

const mdComponents: Components = {
  // Headings
  h1: ({ children }) => (
    <h1 className="text-xl font-bold text-black mt-6 mb-3 leading-tight border-b border-gray-200 pb-2">
      {children}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="text-base font-bold text-black mt-5 mb-2 leading-tight">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="text-sm font-semibold text-black mt-4 mb-1.5 leading-tight">
      {children}
    </h3>
  ),
  // Paragraph
  p: ({ children }) => (
    <p className="text-sm text-gray-800 mb-3 leading-relaxed">{children}</p>
  ),
  // Unordered list
  ul: ({ children }) => (
    <ul className="list-none mb-3 space-y-1.5 pl-0">{children}</ul>
  ),
  // Ordered list
  ol: ({ children }) => (
    <ol className="list-decimal list-inside mb-3 space-y-1.5 text-sm text-gray-800 pl-2">
      {children}
    </ol>
  ),
  // List item — custom bullet with yellow accent
  li: ({ children }) => (
    <li className="text-sm text-gray-800 leading-relaxed flex gap-2 items-start">
      <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-yellow-500 shrink-0" />
      <span>{children}</span>
    </li>
  ),
  // Bold
  strong: ({ children }) => (
    <strong className="font-semibold text-black">{children}</strong>
  ),
  // Inline code
  code: ({ inline, className, children, ...props }: { inline?: boolean; className?: string; children?: React.ReactNode }) => {
    if (inline) {
      return (
        <code
          className="bg-gray-100 text-black text-xs font-mono px-1.5 py-0.5 rounded border border-gray-200"
          {...props}
        >
          {children}
        </code>
      );
    }
    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  // Fenced code block
  pre: ({ children }) => (
    <pre className="bg-gray-950 text-green-400 text-xs font-mono rounded border border-gray-700 p-4 overflow-x-auto mb-3 leading-relaxed">
      {children}
    </pre>
  ),
  // Horizontal rule
  hr: () => <hr className="border-gray-200 my-4" />,
  // Blockquote
  blockquote: ({ children }) => (
    <blockquote className="border-l-4 border-yellow-500 pl-4 my-3 text-sm text-gray-600 italic">
      {children}
    </blockquote>
  ),
};

// ── PDF generation ─────────────────────────────────────────────────────────────

// Convert an ArrayBuffer to a base64 string (works in all browsers)
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  return btoa(binary);
}

// Font name constants used throughout the PDF renderer
const FONT_NAME = "NotoSansDevanagari";
const FONT_FILE = "NotoSansDevanagari-Regular.ttf";

async function downloadNotesPdf(
  markdown: string,
  lectureTitle: string,
  language: string,
): Promise<void> {
  // Dynamic import so jspdf is only loaded when needed
  const { jsPDF } = await import("jspdf");

  const doc = new jsPDF({
    orientation: "portrait",
    unit: "mm",
    format: "a4",
  });

  // ── Register Noto Sans Devanagari for full Unicode / Hindi support ──────────
  // Fetch the TTF from /public/fonts (served statically by Next.js).
  // We load it here (once per PDF generation) so the font is embedded in the
  // PDF and Hindi/Devanagari characters render correctly on all viewers.
  try {
    const fontUrl = "/fonts/NotoSansDevanagari-Regular.ttf";
    const resp = await fetch(fontUrl);
    if (resp.ok) {
      const buffer = await resp.arrayBuffer();
      const b64 = arrayBufferToBase64(buffer);
      doc.addFileToVFS(FONT_FILE, b64);
      doc.addFont(FONT_FILE, FONT_NAME, "normal");
    }
  } catch {
    // If the font fails to load (e.g. offline), fall back to helvetica.
    // English / Hinglish text will still render; Devanagari will be missing.
  }

  // Helper: set font — uses Noto Sans Devanagari when available, otherwise
  // falls back to helvetica so the layout never breaks.
  const hasDev = doc.getFontList()[FONT_NAME] !== undefined;
  const setDocFont = (style: "normal" | "bold" = "normal") => {
    if (hasDev) {
      // Noto Sans Devanagari is a single-weight variable font; jsPDF only
      // needs one variant registered.  Bold headings are handled via font size.
      doc.setFont(FONT_NAME, "normal");
    } else {
      doc.setFont("helvetica", style);
    }
  };

  // Page geometry
  const pageW = doc.internal.pageSize.getWidth();
  const pageH = doc.internal.pageSize.getHeight();
  const marginL = 20;
  const marginR = 20;
  const marginT = 25;
  const marginB = 20;
  const maxW = pageW - marginL - marginR;

  let y = marginT;
  const lineH = 7;
  const sectionGap = 4;

  // Helper: add a new page if needed
  const checkPage = (neededHeight: number) => {
    if (y + neededHeight > pageH - marginB) {
      doc.addPage();
      y = marginT;
      addPageNumber();
    }
  };

  let currentPage = 1;
  const addPageNumber = () => {
    const total = doc.getNumberOfPages();
    doc.setFontSize(9);
    doc.setTextColor(150, 150, 150);
    setDocFont();
    doc.text(
      `Page ${currentPage} of ${total}`,
      pageW / 2,
      pageH - 10,
      { align: "center" },
    );
    currentPage++;
  };

  // ── Header ──────────────────────────────────────────────────────────────────
  doc.setFontSize(9);
  doc.setTextColor(100, 100, 100);
  setDocFont();
  doc.text("VidyaRoom", marginL, y);
  doc.text("Lecture Notes", pageW - marginR, y, { align: "right" });
  y += 5;

  doc.setDrawColor(230, 230, 230);
  doc.setLineWidth(0.3);
  doc.line(marginL, y, pageW - marginR, y);
  y += 6;

  // Title
  doc.setFontSize(16);
  doc.setTextColor(0, 0, 0);
  setDocFont("bold");
  const titleLines = doc.splitTextToSize(lectureTitle || "Lecture Notes", maxW);
  checkPage(titleLines.length * 8);
  doc.text(titleLines, marginL, y);
  y += titleLines.length * 8;

  // Language badge
  doc.setFontSize(9);
  doc.setTextColor(100, 100, 100);
  setDocFont();
  const langLabel =
    language === "hindi"
      ? "Hindi"
      : language === "hinglish"
        ? "Hinglish"
        : "English";
  doc.text(`Language: ${langLabel}  ·  ${new Date().toLocaleDateString()}`, marginL, y);
  y += 6;

  doc.line(marginL, y, pageW - marginR, y);
  y += sectionGap + 2;

  // ── Parse and render markdown lines ────────────────────────────────────────
  const lines = markdown.split("\n");

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();

    // Blank line — small gap
    if (line.trim() === "") {
      y += 2;
      continue;
    }

    // H1
    if (line.startsWith("# ")) {
      const text = line.replace(/^# /, "");
      doc.setFontSize(14);
      setDocFont("bold");
      doc.setTextColor(0, 0, 0);
      const wrapped = doc.splitTextToSize(text, maxW);
      checkPage(wrapped.length * 7 + sectionGap);
      y += sectionGap;
      doc.text(wrapped, marginL, y);
      y += wrapped.length * 7 + 2;
      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.2);
      doc.line(marginL, y, pageW - marginR, y);
      y += 3;
      continue;
    }

    // H2
    if (line.startsWith("## ")) {
      const text = line.replace(/^## /, "");
      doc.setFontSize(13);
      setDocFont("bold");
      doc.setTextColor(0, 0, 0);
      const wrapped = doc.splitTextToSize(text, maxW);
      checkPage(wrapped.length * 6.5 + sectionGap);
      y += sectionGap;
      doc.text(wrapped, marginL, y);
      y += wrapped.length * 6.5 + 1;
      continue;
    }

    // H3
    if (line.startsWith("### ")) {
      const text = line.replace(/^### /, "");
      doc.setFontSize(11.5);
      setDocFont("bold");
      doc.setTextColor(30, 30, 30);
      const wrapped = doc.splitTextToSize(text, maxW);
      checkPage(wrapped.length * 6 + 2);
      y += 2;
      doc.text(wrapped, marginL, y);
      y += wrapped.length * 6;
      continue;
    }

    // Bullet list item  (- or *)
    if (/^[\-\*]\s/.test(line)) {
      const text = line.replace(/^[\-\*]\s/, "").replace(/\*\*/g, "");
      doc.setFontSize(11);
      setDocFont();
      doc.setTextColor(40, 40, 40);
      const wrapped = doc.splitTextToSize(text, maxW - 8);
      checkPage(wrapped.length * lineH);
      // Yellow bullet
      doc.setFillColor(234, 179, 8);
      doc.circle(marginL + 2, y - 1.5, 1.2, "F");
      doc.text(wrapped, marginL + 7, y);
      y += wrapped.length * lineH;
      continue;
    }

    // Numbered list item
    const numbered = line.match(/^(\d+)\.\s(.*)/);
    if (numbered) {
      const num = numbered[1];
      const text = numbered[2].replace(/\*\*/g, "");
      doc.setFontSize(10);
      setDocFont();
      doc.setTextColor(40, 40, 40);
      const wrapped = doc.splitTextToSize(text, maxW - 10);
      checkPage(wrapped.length * lineH);
      doc.text(`${num}.`, marginL, y);
      doc.text(wrapped, marginL + 8, y);
      y += wrapped.length * lineH;
      continue;
    }

    // Code fence marker (``` lines) — skip the fence characters, render content differently
    if (line.startsWith("```")) {
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      checkPage(4);
      doc.setDrawColor(200, 200, 200);
      doc.setLineWidth(0.2);
      doc.line(marginL, y, pageW - marginR, y);
      y += 4;
      continue;
    }

    // Normal paragraph (strip bold markers for PDF)
    const text = line.replace(/\*\*/g, "").replace(/`([^`]+)`/g, "$1");
    if (text.trim()) {
      doc.setFontSize(10);
      setDocFont();
      doc.setTextColor(40, 40, 40);
      const wrapped = doc.splitTextToSize(text, maxW);
      checkPage(wrapped.length * lineH);
      doc.text(wrapped, marginL, y);
      y += wrapped.length * lineH;
    }
  }

  // Add page number to the last page
  addPageNumber();

  const safeName = (lectureTitle || "notes")
    .replace(/[^a-z0-9_\-]/gi, "_")
    .toLowerCase()
    .slice(0, 50);
  doc.save(`vidyaroom_${safeName}_notes.pdf`);
}

// ── Component ──────────────────────────────────────────────────────────────────

interface NotesPanelProps {
  notes: string | null;
  isGenerating?: boolean;
  lectureCompleted?: boolean;
  notesLanguage: TargetLanguage;
  onNotesLanguageChange: (lang: TargetLanguage) => void;
  lectureTitle?: string;
  /** True when a language-change regen is in progress */
  isRegenerating?: boolean;
  /** Error string from notes generation failure */
  notesError?: string | null;
  /** True when the pipeline found no speech in the video — notes cannot be generated */
  noSpeechDetected?: boolean;
}

export default function NotesPanel({
  notes,
  isGenerating = false,
  lectureCompleted = false,
  notesLanguage,
  onNotesLanguageChange,
  lectureTitle = "Lecture Notes",
  isRegenerating = false,
  notesError = null,
  noSpeechDetected = false,
}: NotesPanelProps) {
  const handleDownloadPdf = useCallback(async () => {
    if (!notes) return;
    await downloadNotesPdf(notes, lectureTitle, notesLanguage);
  }, [notes, lectureTitle, notesLanguage]);

  // ── States ────────────────────────────────────────────────────────────────

  const isLoading = isGenerating || isRegenerating;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* ── Toolbar ───────────────────────────────────────────────────────── */}
      <div className="flex items-center gap-3 pb-3 border-b border-gray-200 shrink-0 flex-wrap">
        {/* Language selector */}
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-semibold uppercase tracking-widest text-gray-500">
            Notes language
          </span>
          <select
            value={notesLanguage}
            onChange={(e) => onNotesLanguageChange(e.target.value as TargetLanguage)}
            disabled={isLoading}
            className="bg-white text-black text-xs border border-gray-300 px-2 py-0.5 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 cursor-pointer disabled:opacity-40 transition-colors rounded"
            aria-label="Notes language"
          >
            {LANGUAGE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value} className="bg-white text-black">
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Spacer */}
        <div className="flex-1" />

        {/* PDF download button */}
        {notes && !isLoading && (
          <button
            onClick={handleDownloadPdf}
            className="flex items-center gap-1.5 text-xs font-semibold bg-yellow-500 hover:bg-yellow-600 text-black px-3 py-1.5 rounded transition-colors"
            aria-label="Download notes as PDF"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-3.5 h-3.5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M7 10l5 5m0 0l5-5m-5 5V4" />
            </svg>
            PDF
          </button>
        )}
      </div>

      {/* ── Content area ──────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto pt-3 min-h-0">

        {/* Loading state */}
        {isLoading && (
          <div className="flex items-center gap-3 py-6 text-sm text-gray-500">
            <span className="inline-block w-4 h-4 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
            Generating your lecture notes…
          </div>
        )}

        {/* Error state */}
        {!isLoading && notesError && (
          <div className="py-4 text-sm text-red-700 border border-red-200 bg-red-50 rounded px-4">
            Unable to generate notes right now. Please try again.
          </div>
        )}

        {/* Notes content */}
        {!isLoading && !notesError && notes && (
          <article className="prose-notes max-w-none">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={mdComponents}
            >
              {notes}
            </ReactMarkdown>
          </article>
        )}

        {/* No speech — notes cannot be generated */}
        {!isLoading && !notesError && !notes && noSpeechDetected && (
          <p className="text-sm text-gray-500 italic py-2">
            No speech was detected in this video — notes could not be generated.
          </p>
        )}

        {/* Empty — lecture in progress */}
        {!isLoading && !notesError && !notes && !lectureCompleted && !noSpeechDetected && (
          <p className="text-sm text-gray-500 italic py-2">
            Notes will be available after the lecture.
          </p>
        )}

        {/* Empty — lecture done but notes pending */}
        {!isLoading && !notesError && !notes && lectureCompleted && !noSpeechDetected && (
          <p className="text-sm text-gray-500 italic py-2">
            Notes are being prepared…
          </p>
        )}
      </div>
    </div>
  );
}
