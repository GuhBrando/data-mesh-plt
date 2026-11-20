import { useState } from 'react'
import Button from '../../components/ui/Button'
import { TierGlyph } from '../../components/ui/Glyphs'

const TIER_LABELS: Record<number, { name: string; description: string }> = {
  1: { name: 'Critical / Regulated', description: 'Errors can cause legal, regulatory, or material financial consequences.' },
  2: { name: 'Business Important', description: 'Errors can lead to wrong business decisions with measurable financial impact.' },
  3: { name: 'Operational / Internal', description: 'Errors are manageable informally with no material damage.' },
  4: { name: 'Experimental / Sandbox', description: 'Exploration or hypothesis validation. No production consumers allowed.' },
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

function Progress({ step }: { step: number }) {
  return (
    <span className="flex items-center gap-2 text-xs text-tx3">
      Question {step + 1} of {QUESTIONS.length}
      <span className="flex gap-1" aria-hidden="true">
        {QUESTIONS.map((q, i) => (
          <span
            key={q}
            className={`h-1.5 rounded-full transition-[width,background-color] duration-300 ${
              i === step ? 'w-4 bg-accent-fg' : i < step ? 'w-1.5 bg-tx3' : 'w-1.5 bg-line2'
            }`}
          />
        ))}
      </span>
    </span>
  )
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
    <div className="rounded-[10px] border border-line bg-raised/60 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-[13px] font-semibold text-tx">Classify the Tier</h3>
        {!done && <Progress step={step} />}
      </div>

      {!done ? (
        <div key={step} className="mt-3 animate-swap space-y-3">
          <p className="text-[13px] text-tx2">{QUESTIONS[step]}</p>
          <div className="flex gap-2">
            <Button size="sm" onClick={() => handleAnswer(true)}>Yes</Button>
            <Button size="sm" variant="secondary" onClick={() => handleAnswer(false)}>No</Button>
          </div>
        </div>
      ) : (
        <div className="mt-3 animate-swap space-y-3">
          <div className="flex items-start gap-3">
            <span className="grid h-8 w-10 shrink-0 place-items-center rounded-lg border border-line bg-panel">
              <TierGlyph tier={value} />
            </span>
            <div>
              <span className="text-[13px] font-semibold text-tx">
                Tier {value} — {tier.name}
              </span>
              <p className="mt-0.5 text-xs text-tx2">{tier.description}</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label htmlFor="tier-override" className="text-xs text-tx3">Override</label>
            <select
              id="tier-override"
              value={value}
              onChange={(e) => onChange(Number(e.target.value))}
              className="form-input !w-auto !py-1.5"
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
