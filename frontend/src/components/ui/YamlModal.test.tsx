import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import YamlModal from './YamlModal'

function renderModal(props: Partial<Parameters<typeof YamlModal>[0]> = {}) {
  render(<YamlModal title="ODPS YAML" open content={'apiVersion: v1.1.0\n'} loading={false} onClose={vi.fn()} {...props} />)
}

afterEach(() => vi.unstubAllGlobals())

describe('YamlModal', () => {
  it('shows the YAML in a dialog', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: 'ODPS YAML' })).toHaveTextContent('apiVersion: v1.1.0')
  })

  it('shows a spinner while loading', () => {
    renderModal({ loading: true, content: undefined })
    expect(screen.getByLabelText('Loading')).toBeInTheDocument()
  })

  it('offers no copy or download without a file name', () => {
    renderModal()
    expect(screen.queryByRole('button', { name: /Copy/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /Download/ })).not.toBeInTheDocument()
  })

  it('copies the YAML to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    vi.stubGlobal('navigator', { clipboard: { writeText } })
    renderModal({ fileName: 'risk.odps.yaml' })
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    expect(writeText).toHaveBeenCalledWith('apiVersion: v1.1.0\n')
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument()
  })

  it('downloads the YAML under the file name', async () => {
    const createObjectURL = vi.fn().mockReturnValue('blob:odps')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL })
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
      expect(this.download).toBe('risk.odps.yaml')
      expect(this.href).toBe('blob:odps')
    })
    renderModal({ fileName: 'risk.odps.yaml' })
    fireEvent.click(screen.getByRole('button', { name: 'Download' }))
    await waitFor(() => expect(click).toHaveBeenCalledOnce())
    const blob = createObjectURL.mock.calls[0][0] as Blob
    expect(await blob.text()).toBe('apiVersion: v1.1.0\n')
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:odps')
  })

  it('offers no actions while the YAML is loading', () => {
    renderModal({ fileName: 'risk.odps.yaml', loading: true, content: undefined })
    expect(screen.queryByRole('button', { name: 'Copy' })).not.toBeInTheDocument()
  })
})
