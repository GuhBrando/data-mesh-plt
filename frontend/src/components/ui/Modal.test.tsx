import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'
import Modal from './Modal'

afterEach(() => {
  document.body.style.overflow = ''
})

describe('Modal', () => {
  it('renders nothing when closed', () => {
    render(
      <Modal open={false} onClose={vi.fn()} title="Hidden">
        body
      </Modal>,
    )
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders title and children when open', () => {
    render(
      <Modal open onClose={vi.fn()} title="Visible">
        body content
      </Modal>,
    )
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('Visible')).toBeInTheDocument()
    expect(screen.getByText('body content')).toBeInTheDocument()
  })

  it('locks body scroll while open and restores it on close', () => {
    const { rerender } = render(
      <Modal open onClose={vi.fn()} title="T">
        body
      </Modal>,
    )
    expect(document.body.style.overflow).toBe('hidden')
    rerender(
      <Modal open={false} onClose={vi.fn()} title="T">
        body
      </Modal>,
    )
    expect(document.body.style.overflow).toBe('')
  })

  it('calls onClose when the close button is clicked', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="T">
        body
      </Modal>,
    )
    fireEvent.click(screen.getByLabelText('Close modal'))
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when the backdrop is clicked', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="T">
        body
      </Modal>,
    )
    fireEvent.click(screen.getByRole('dialog').querySelector('[aria-hidden="true"]')!)
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when Escape is pressed', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="T">
        body
      </Modal>,
    )
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledOnce()
  })

  it('ignores non-Escape keys', () => {
    const onClose = vi.fn()
    render(
      <Modal open onClose={onClose} title="T">
        body
      </Modal>,
    )
    fireEvent.keyDown(window, { key: 'Enter' })
    expect(onClose).not.toHaveBeenCalled()
  })

  it('renders on <body>, outside a transformed ancestor that would trap the fixed overlay', () => {
    const { container } = render(
      <div style={{ transform: 'translateY(0)' }}>
        <Modal open onClose={vi.fn()} title="T">
          body
        </Modal>
      </div>,
    )
    const dialog = screen.getByRole('dialog')
    expect(container).not.toContainElement(dialog)
    expect(dialog.parentElement).toBe(document.body)
  })

  it('applies the large size class', () => {
    render(
      <Modal open onClose={vi.fn()} title="T" size="lg">
        body
      </Modal>,
    )
    expect(screen.getByRole('dialog').querySelector('.max-w-2xl')).toBeInTheDocument()
  })
})
