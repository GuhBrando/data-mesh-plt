import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import Mark from './Mark'

describe('Mark', () => {
  it('is decorative by default', () => {
    const { container } = render(<Mark />)
    const svg = container.querySelector('svg')
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '24')
  })

  it('becomes an image when it has a title', () => {
    render(<Mark size={40} title="DataMesh" />)
    const svg = screen.getByRole('img', { name: 'DataMesh' })
    expect(svg).toHaveAttribute('width', '40')
    expect(svg).not.toHaveAttribute('aria-hidden')
  })
})
