import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import SaveWarnings from './SaveWarnings'

describe('SaveWarnings', () => {
  it('lists what the platform warned about and can be dismissed', () => {
    const onDismiss = vi.fn()
    render(<SaveWarnings warnings={['Contract A is deprecated', 'Contract B belongs to domain X']} onDismiss={onDismiss} />)
    const notice = screen.getByRole('status')
    expect(notice).toHaveTextContent('Saved, with 2 warnings')
    expect(screen.getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      'Contract A is deprecated',
      'Contract B belongs to domain X',
    ])
    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }))
    expect(onDismiss).toHaveBeenCalledOnce()
  })

  it('says warning once for one', () => {
    render(<SaveWarnings warnings={['x']} onDismiss={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Saved, with 1 warning')
  })

  it('renders nothing without warnings', () => {
    const { container } = render(<SaveWarnings warnings={[]} onDismiss={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
  })
})
