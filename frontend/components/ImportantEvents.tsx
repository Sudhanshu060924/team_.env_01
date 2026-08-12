'use client'

import { ImportantEvent } from '@/types/ai'

interface ImportantEventsProps {
  events: ImportantEvent[]
}

export default function ImportantEvents({ events }: ImportantEventsProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 flex flex-col gap-2 flex-1">
      <h2 className="text-xs font-semibold uppercase tracking-wider text-gray-500">Important</h2>
      {events.length > 0 ? (
        <ul className="flex flex-col gap-2 overflow-y-auto max-h-48">
          {events.slice(-8).reverse().map((evt) => (
            <li key={evt.id} className="text-sm">
              <span className="text-gray-500 text-xs mr-2">
                {new Date(evt.timestamp * 1000).toISOString().slice(11, 19)}
              </span>
              <span className={evt.isFormula ? 'text-amber-300 font-mono' : 'text-gray-200'}>
                {evt.content}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-xs text-gray-600 italic">Key concepts &amp; formulas will appear here…</p>
      )}
    </div>
  )
}
