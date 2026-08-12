'use client'

interface NotesPanelProps {
  notes: string | null
  isGenerating?: boolean
  onGenerate?: () => void
  lectureCompleted?: boolean
}

export default function NotesPanel({
  notes,
  isGenerating = false,
  onGenerate,
  lectureCompleted = false,
}: NotesPanelProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-3 h-full overflow-hidden">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Lecture Notes</h2>
        {lectureCompleted && !notes && !isGenerating && onGenerate && (
          <button
            onClick={onGenerate}
            className="text-xs bg-indigo-600 hover:bg-indigo-500 text-white px-3 py-1 rounded transition-colors"
          >
            Generate Notes
          </button>
        )}
      </div>

      {isGenerating && (
        <p className="text-xs text-indigo-400 animate-pulse">Generating notes…</p>
      )}

      {notes ? (
        <div className="overflow-y-auto flex-1 text-sm text-gray-200 whitespace-pre-wrap leading-relaxed">
          {notes}
        </div>
      ) : !isGenerating ? (
        <p className="text-xs text-gray-600 italic">
          {lectureCompleted
            ? 'Click "Generate Notes" to create a summary.'
            : 'Notes will be generated when the lecture ends.'}
        </p>
      ) : null}
    </div>
  )
}
