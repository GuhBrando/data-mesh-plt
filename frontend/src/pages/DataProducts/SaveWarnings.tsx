/** What the platform warned about on a successful save, until dismissed. */
export default function SaveWarnings({ warnings, onDismiss }: { warnings: string[]; onDismiss: () => void }) {
  if (warnings.length === 0) return null
  return (
    <div role="status" className="animate-enter rounded-lg border border-warn/30 bg-warn/10 px-4 py-3 text-[13px]">
      <div className="flex items-start justify-between gap-3">
        <p className="font-medium text-warn">
          Saved, with {warnings.length} warning{warnings.length === 1 ? '' : 's'}
        </p>
        <button type="button" onClick={onDismiss} className="text-xs text-tx2 hover:text-tx">
          Dismiss
        </button>
      </div>
      <ul className="mt-1 list-disc pl-5 text-tx2">
        {warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
    </div>
  )
}
