import { useState } from 'react'
import Button from '../../components/ui/Button'

const TIER_LABELS: Record<number, { name: string; description: string; color: string }> = {
  1: { name: 'Critical / Regulated', description: 'Errors can cause legal, regulatory, or material financial consequences.', color: 'text-red-600 dark:text-red-400' },
  2: { name: 'Business Important', description: 'Errors can lead to wrong business decisions with measurable financial impact.', color: 'text-orange-600 dark:text-orange-400' },
  3: { name: 'Operational / Internal', description: 'Errors are manageable informally with no material damage.', color: 'text-accent-fg dark:text-accent-fg' },
  4: { name: 'Experimental / Sandbox', description: 'Exploration or hypothesis validation. No production consumers allowed.', color: 'text-gray-600 dark:text-gray-400' },
}

const QUESTIONS = [
  'Could an error in this data cause a regulatory, legal, or financial consequence?',
  'Could an error lead to a wrong business decision with measurable financial impact?',
  'Is the impact of an error manageable informally, with no material damage?',
]

interface TierWizardProps {
  value: number
  onChange: (tier: number) => void
}

export default function TierWizard({ value, onChange }: TierWizardProps) {
  const [step, setStep] = useState(0)
  const [done, setDone] = useState(false)

  const handleAnswer = (yes: boolean) => {
    const assignedTier = step + 1
    if (yes) {
      onChange(assignedTier)
      setDone(true)
      return
    }
    if (step < QUESTIONS.length - 1) {
      setStep(step + 1)
    } else {
      onChange(4)
      setDone(true)
    }
  }

  const reset = () => {
    setStep(0)
    setDone(false)
  }

  const tier = TIER_LABELS[value]

  return (
    <div className="rounded-lg border border-gray-200 dark:border-slate-700 p-4 space-y-4">
      <h3 className="text-sm font-semibold text-gray-700 dark:text-slate-200">
        Classify the Tier
      </h3>

      {!done ? (
        <div className="space-y-3">
          <p className="text-sm text-gray-600 dark:text-slate-300">
            {QUESTIONS[step]}
          </p>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => handleAnswer(true)}>Yes</Button>
            <Button size="sm" variant="secondary" onClick={() => handleAnswer(false)}>No</Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div>
            <span className={`text-sm font-semibold ${tier.color}`}>
              Tier {value} — {tier.name}
            </span>
            <p className="text-xs text-gray-500 dark:text-slate-400 mt-1">{tier.description}</p>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-xs text-gray-500 dark:text-slate-400">Override:</label>
            <select
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              className="text-sm border border-gray-300 dark:border-slate-600 rounded px-2 py-1 bg-white dark:bg-slate-800 text-gray-700 dark:text-slate-200"
            >
              {[1, 2, 3, 4].map((t) => (
                <option key={t} value={t}>
                  Tier {t} — {TIER_LABELS[t].name}
                </option>
              ))}
            </select>
            <Button variant="ghost" size="sm" onClick={reset}>
              Restart
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
