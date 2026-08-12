'use client'

import { forwardRef } from 'react'

interface VideoPlayerProps {
  src?: string
  onTimeUpdate?: (currentTime: number) => void
  onEnded?: () => void
}

const VideoPlayer = forwardRef<HTMLVideoElement, VideoPlayerProps>(
  function VideoPlayer({ src, onTimeUpdate, onEnded }, ref) {
    return (
      <div className="relative w-full aspect-video bg-black rounded-lg overflow-hidden flex items-center justify-center">
        {src ? (
          <video
            ref={ref}
            className="w-full h-full"
            src={src}
            controls
            onTimeUpdate={(e) => onTimeUpdate?.(e.currentTarget.currentTime)}
            onEnded={onEnded}
            aria-label="Lecture video"
          />
        ) : (
          <div className="text-center text-gray-500 select-none">
            <div className="text-5xl mb-3 opacity-40">▶</div>
            <p className="text-sm">No video loaded</p>
            <p className="text-xs text-gray-600 mt-1">
              Place <code className="text-gray-500">demo.mp4</code> in{' '}
              <code className="text-gray-500">frontend/public/lectures/</code>
            </p>
          </div>
        )}
      </div>
    )
  }
)

export default VideoPlayer
