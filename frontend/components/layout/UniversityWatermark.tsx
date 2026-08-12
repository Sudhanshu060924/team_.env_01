'use client'

/**
 * UniversityWatermark
 * Large, faint university logo fixed in the background of every page.
 * pointer-events-none, never affects layout, never creates scroll.
 */
export default function UniversityWatermark() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none select-none fixed inset-0 z-0 flex items-center justify-center overflow-hidden"
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/logo.jpg"
        alt=""
        className="w-[520px] h-[520px] object-contain opacity-[0.04]"
      />
    </div>
  )
}
