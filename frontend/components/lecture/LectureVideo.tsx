'use client'

import { forwardRef } from 'react'

interface LectureVideoProps {
  src?: string
  onTimeUpdate?: (currentTime: number) => void
  onEnded?: () => void
}

const LectureVideo = forwardRef<HTMLVideoElement | null, LectureVideoProps>(
  function LectureVideo({ src, onTimeUpdate, onEnded }, ref) {
    return (
      <div className="relative w-full bg-black overflow-hidden flex items-center justify-center border border-neutral-800 aspect-video lg:aspect-auto lg:h-full">
        {src ? (
          <video
            ref={ref}
            className="w-full h-full object-contain"
            src={src}
            controls
            onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
            onEnded={onEnded}
            aria-label="Lecture video"
          />
        ) : (
          <div className="text-center text-neutral-600 select-none">
            <div
              className="text-5xl mb-3 opacity-30"
              aria-hidden="true"
            >
              ▶
            </div>
            <p className="text-sm text-neutral-500">No video loaded</p>
          </div>
        )}
      </div>
    )
  }
)

export default LectureVideo
