import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Avatar, DomainChip, StatusGlyph, TierGlyph } from './Glyphs'
import { domainColor } from '../../lib/contracts'

describe('StatusGlyph', () => {
  it('labels the status and carries its shape class', () => {
    render(<StatusGlyph status="in_review" />)
    const el = screen.getByText('In review')
    expect(el).toHaveClass('st', 'st-in_review')
  })
})

describe('TierGlyph', () => {
  it('shows the tier with its full name as a tooltip', () => {
    render(<TierGlyph tier={1} />)
    const el = screen.getByTitle('Tier 1 · Critical / Regulated')
    expect(el).toHaveTextContent('T1')
    expect(el.querySelector('.tier-1')).not.toBeNull()
  })

  it('can spell the name out', () => {
    render(<TierGlyph tier={4} showName />)
    expect(screen.getByText(/T4 · Experimental \/ Sandbox/)).toBeInTheDocument()
  })
})

describe('DomainChip', () => {
  it('colours the marker from the domain name', () => {
    render(<DomainChip name="Riscos" />)
    const el = screen.getByText('Riscos')
    expect(el).toHaveClass('dom')
    expect(el.style.getPropertyValue('--dc')).toBe(domainColor('Riscos'))
  })
})

describe('Avatar', () => {
  it('shows initials and stays out of the accessibility tree', () => {
    const { container } = render(<Avatar name="ana.ribeiro" size={28} />)
    const el = container.firstElementChild as HTMLElement
    expect(el).toHaveTextContent('AR')
    expect(el).toHaveAttribute('aria-hidden', 'true')
    expect(el.style.width).toBe('28px')
  })
})
