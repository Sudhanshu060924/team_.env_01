'use client'

import { useEffect, useState, FormEvent } from 'react'
import { api } from '@/lib/api'
import { RatingRead } from '@/types/feedback'
import Button from '@/components/ui/Button'

interface LectureRatingPanelProps {
  lectureId: string
}

function StarIcon({ filled, hovered }: { filled: boolean; hovered: boolean }) {
  const color = filled || hovered ? '#f59e0b' : '#d1d5db'
  return (
    <svg
      width="28"
      height="28"
      viewBox="0 0 24 24"
      fill={filled || hovered ? color : 'none'}
      stroke={color}
      strokeWidth={1.6}
    >
      <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
    </svg>
  )
}

function StarRatingInput({
  value,
  onChange,
}: {
  value: number
  // eslint-disable-next-line no-unused-vars
  onChange: (v: number) => void
}) {
  const [hovered, setHovered] = useState(0)

  return (
    <div className="flex items-center gap-1" role="group" aria-label="Star rating">
      {[1, 2, 3, 4, 5].map((star) => (
        <button
          key={star}
          type="button"
          onClick={() => onChange(star)}
          onMouseEnter={() => setHovered(star)}
          onMouseLeave={() => setHovered(0)}
          aria-label={`${star} star${star !== 1 ? 's' : ''}`}
          className="p-0.5 rounded transition-transform hover:scale-110"
        >
          <StarIcon filled={star <= value} hovered={star <= hovered && hovered > value} />
        </button>
      ))}
      {value > 0 && (
        <span className="ml-2 text-sm font-semibold text-yellow-700">
          {['', 'Poor', 'Fair', 'Good', 'Very Good', 'Excellent'][value]}
        </span>
      )}
    </div>
  )
}

function StarDisplay({ value }: { value: number }) {
  return (
    <div className="flex items-center gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <svg
          key={star}
          width="16"
          height="16"
          viewBox="0 0 24 24"
          fill={star <= value ? '#f59e0b' : 'none'}
          stroke={star <= value ? '#f59e0b' : '#d1d5db'}
          strokeWidth={1.6}
        >
          <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
        </svg>
      ))}
    </div>
  )
}

export default function LectureRatingPanel({ lectureId }: LectureRatingPanelProps) {
  const [existing, setExisting] = useState<RatingRead | null>(null)
  const [loading, setLoading] = useState(true)
  const [isEditing, setIsEditing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  // Form state
  const [selectedRating, setSelectedRating] = useState(0)
  const [feedbackText, setFeedbackText] = useState('')

  // Load existing rating on mount
  useEffect(() => {
    setLoading(true)
    api.getMyRating(lectureId)
      .then((r) => {
        setExisting(r)
        if (r) {
          setSelectedRating(r.rating)
          setFeedbackText(r.feedback ?? '')
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [lectureId])

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (selectedRating === 0) return
    setSubmitting(true)
    setSubmitError(null)
    setSuccess(false)

    try {
      const payload = {
        rating: selectedRating,
        feedback: feedbackText.trim() || null,
      }
      const saved = existing
        ? await api.updateRating(lectureId, payload)
        : await api.createRating(lectureId, payload)
      setExisting(saved)
      setIsEditing(false)
      setSuccess(true)
      setTimeout(() => setSuccess(false), 3000)
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to submit rating')
    } finally {
      setSubmitting(false)
    }
  }

  const startEdit = () => {
    if (existing) {
      setSelectedRating(existing.rating)
      setFeedbackText(existing.feedback ?? '')
    } else {
      setSelectedRating(0)
      setFeedbackText('')
    }
    setIsEditing(true)
    setSuccess(false)
    setSubmitError(null)
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-sm text-gray-400 py-2">
        <span className="w-3.5 h-3.5 border-2 border-yellow-400 border-t-transparent rounded-full animate-spin" />
        Loading rating…
      </div>
    )
  }

  // Show existing rating (not editing)
  if (existing && !isEditing) {
    return (
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-xs uppercase tracking-widest text-yellow-700 font-semibold mb-2">
          Your Rating
        </p>
        <div className="flex items-center gap-3 mb-2">
          <StarDisplay value={existing.rating} />
          <span className="text-sm font-bold text-black">
            {['', 'Poor', 'Fair', 'Good', 'Very Good', 'Excellent'][existing.rating]}
          </span>
        </div>
        {existing.feedback && (
          <p className="text-sm text-gray-700 italic mb-3">&ldquo;{existing.feedback}&rdquo;</p>
        )}
        <p className="text-xs text-gray-400 mb-3">
          Rated on {new Date(existing.updated_at).toLocaleDateString('en-IN', {
            day: 'numeric', month: 'short', year: 'numeric',
          })}
        </p>
        {success && (
          <p className="text-xs text-green-600 font-semibold mb-2">✓ Rating saved!</p>
        )}
        <button
          onClick={startEdit}
          className="text-xs font-semibold text-yellow-700 hover:text-yellow-900 underline underline-offset-2 transition-colors"
        >
          Edit your rating
        </button>
      </div>
    )
  }

  // Show rating form
  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4">
      <p className="text-xs uppercase tracking-widest text-gray-500 font-semibold mb-3">
        {existing ? 'Update Your Rating' : 'Rate This Lecture'}
      </p>

      <form onSubmit={handleSubmit}>
        {/* Star picker */}
        <div className="mb-4">
          <p className="text-sm text-gray-600 mb-2">How was this lecture?</p>
          <StarRatingInput value={selectedRating} onChange={setSelectedRating} />
        </div>

        {/* Written feedback */}
        <div className="mb-4">
          <label className="block text-xs text-gray-500 mb-1.5">
            Write your feedback (optional)
          </label>
          <textarea
            value={feedbackText}
            onChange={(e) => setFeedbackText(e.target.value)}
            placeholder="Share your thoughts about this lecture…"
            rows={3}
            maxLength={1000}
            className="w-full bg-white text-black text-sm border border-gray-300 rounded px-3 py-2 outline-none focus:border-yellow-500 focus:ring-1 focus:ring-yellow-500 placeholder-gray-400 resize-none transition-colors"
          />
          <p className="text-[10px] text-gray-400 text-right mt-0.5">
            {feedbackText.length}/1000
          </p>
        </div>

        {submitError && (
          <p className="text-xs text-red-600 mb-3">{submitError}</p>
        )}

        <div className="flex items-center gap-2">
          <Button
            type="submit"
            variant="primary"
            size="sm"
            loading={submitting}
            disabled={selectedRating === 0}
          >
            {existing ? 'Update Rating' : 'Submit Rating'}
          </Button>
          {existing && (
            <button
              type="button"
              onClick={() => setIsEditing(false)}
              className="text-xs text-gray-500 hover:text-gray-700 transition-colors px-2 py-1"
            >
              Cancel
            </button>
          )}
        </div>
      </form>
    </div>
  )
}
