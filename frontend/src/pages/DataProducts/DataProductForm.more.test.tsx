import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import DataProductForm from './DataProductForm'
import { useSelectableContracts } from '../../hooks/useSelectableContracts'
import { useDataContracts } from '../../hooks/useDataContracts'
import { useDataProducts } from '../../hooks/useDataProducts'
import { useAllDomains } from '../../hooks/useDomains'
import { useAuth } from '../../contexts/AuthContext'
import { makeDomain, makeOutput, makeProduct, makeUser } from '../../test/fixtures'
import type { DataProduct } from '../../types'

vi.mock('../../hooks/useSelectableContracts', () => ({ useSelectableContracts: vi.fn() }))
vi.mock('../../hooks/useDataContracts', () => ({ useDataContracts: vi.fn() }))
vi.mock('../../hooks/useDataProducts', () => ({ useDataProducts: vi.fn() }))
vi.mock('../../hooks/useDomains', () => ({ useAllDomains: vi.fn() }))
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }))

const query = (data: unknown) => ({ data, isLoading: false, error: null }) as never

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({ user: makeUser({ id: 'u1', role: 'DATA_OWNER' }) } as never)
  vi.mocked(useAllDomains).mockReturnValue(query([makeDomain({ id: 'd1', owner_id: 'u1', members: [] })]))
  vi.mocked(useSelectableContracts).mockReturnValue({ contracts: [], isLoading: false, error: null })
  vi.mocked(useDataContracts).mockReturnValue(query([]))
  vi.mocked(useDataProducts).mockReturnValue(query([]))
})

function renderForm(defaultValues?: DataProduct) {
  const onSubmit = vi.fn()
  render(<DataProductForm defaultValues={defaultValues} onSubmit={onSubmit} onCancel={vi.fn()} isSubmitting={false} />)
  return onSubmit
}

const existing = makeProduct({ id: 'p1', description: { purpose: 'Credit exposure by client', usage: '', limitations: '' } })

function type(label: string, value: string, scope: HTMLElement = document.body) {
  fireEvent.change(within(scope).getByLabelText(label), { target: { value } })
}

function group(name: RegExp) {
  return screen.getByRole('group', { name })
}

async function save(onSubmit: ReturnType<typeof vi.fn>) {
  fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
  await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
  return onSubmit.mock.calls[0][0]
}

describe('More ODPS fields', () => {
  it('stays out of the short path until opened', () => {
    renderForm()
    const toggle = screen.getByRole('button', { name: /More ODPS fields/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByLabelText('Version')).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByLabelText('Version')).toBeInTheDocument()
    for (const name of [/About/, /People/, /For AI agents/, /Links/, /Management ports/]) {
      expect(group(name)).toBeInTheDocument()
    }
  })

  it('edits the About group', async () => {
    const onSubmit = renderForm(existing)
    fireEvent.click(screen.getByRole('button', { name: /More ODPS fields/ }))
    type('Version', '${VERSION:-1.2.0}')
    type('Type', 'consumerAligned')
    type('Tenant', 'acme')
    type('Usage', 'Daily batch')
    type('Limitations', 'No intraday')
    type('Tags', 'risk, credit , ')
    fireEvent.click(within(group(/About/)).getByRole('button', { name: 'Add synonym' }))
    type('Synonym', 'credit exposure', group(/About/))
    const values = await save(onSubmit)
    expect([values.version, values.type, values.tenant]).toEqual(['${VERSION:-1.2.0}', 'consumerAligned', 'acme'])
    expect(values.description).toMatchObject({ usage: 'Daily batch', limitations: 'No intraday' })
    expect(values.tags).toEqual(['risk', 'credit'])
    expect(values.synonyms).toEqual([{ synonym: 'credit exposure' }])
  })

  it('edits the People group with the shared team and support editors', async () => {
    const onSubmit = renderForm(existing)
    fireEvent.click(screen.getByRole('button', { name: /More ODPS fields/ }))
    const people = group(/People/)
    type('Team name', 'Risk', people)
    fireEvent.click(within(people).getByRole('button', { name: 'Add team member' }))
    fireEvent.change(within(people).getByPlaceholderText('Username'), { target: { value: 'ana' } })
    fireEvent.click(within(people).getByRole('button', { name: 'Add support channel' }))
    fireEvent.change(within(people).getByPlaceholderText('Channel'), { target: { value: '#risk' } })
    fireEvent.change(within(people).getByPlaceholderText('URL'), { target: { value: '${SUPPORT_URL}' } })
    const values = await save(onSubmit)
    expect(values.team).toMatchObject({ name: 'Risk', members: [{ username: 'ana' }] })
    expect(values.support).toEqual([{ channel: '#risk', url: '${SUPPORT_URL}', tool: '', scope: '' }])
  })

  it('edits the For AI agents group', async () => {
    const onSubmit = renderForm(existing)
    fireEvent.click(screen.getByRole('button', { name: /More ODPS fields/ }))
    const ai = group(/For AI agents/)
    type('Instructions', 'Use for credit risk only', ai)
    fireEvent.click(within(ai).getByRole('button', { name: 'Add constraint' }))
    type('Constraint', 'Never join with PII', ai)
    fireEvent.click(within(ai).getByRole('button', { name: 'Add verified statement' }))
    type('Question', 'Total exposure?', ai)
    type('Answer', 'sum(amount)', ai)
    const values = await save(onSubmit)
    expect(values.context).toEqual({
      instructions: 'Use for credit risk only',
      constraints: [{ constraint: 'Never join with PII' }],
      verified_statements: [{ question: 'Total exposure?', answer: 'sum(amount)' }],
    })
  })

  it('edits the Links group and the management ports', async () => {
    const onSubmit = renderForm(existing)
    fireEvent.click(screen.getByRole('button', { name: /More ODPS fields/ }))
    const links = group(/Links/)
    fireEvent.click(within(links).getByRole('button', { name: 'Add definition' }))
    type('Definition type', 'businessDefinition', links)
    type('Definition URL', 'https://wiki/risk', links)
    fireEvent.click(within(links).getByRole('button', { name: 'Add custom property' }))
    type('Property', 'cost_center', links)
    type('Value', '42', links)
    const ports = group(/Management ports/)
    fireEvent.click(within(ports).getByRole('button', { name: 'Add management port' }))
    type('Management port name', 'metrics', ports)
    type('Content', 'observability', ports)
    fireEvent.change(within(ports).getByLabelText('Management port type'), { target: { value: 'topic' } })
    type('Management port URL', 'https://metrics', ports)
    const values = await save(onSubmit)
    expect(values.authoritative_definitions).toEqual([{ type: 'businessDefinition', url: 'https://wiki/risk' }])
    expect(values.custom_properties).toEqual([{ property: 'cost_center', value: '42' }])
    expect(values.management_ports).toEqual([
      { name: 'metrics', content: 'observability', type: 'topic', url: 'https://metrics', deprecated: false },
    ])
  })

  it('refuses a support channel without a URL and opens itself to show why', async () => {
    const onSubmit = renderForm({ ...existing, support: [{ channel: '#risk', url: '' }] })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    const people = await screen.findByRole('group', { name: /People/ })
    expect(within(people).getByRole('alert')).toHaveTextContent('Every support channel needs a URL')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuses a management port without a content', async () => {
    const onSubmit = renderForm({
      ...existing,
      management_ports: [{ name: 'metrics', content: '', type: 'rest', deprecated: false }],
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    const ports = await screen.findByRole('group', { name: /Management ports/ })
    expect(within(ports).getByRole('alert')).toHaveTextContent('Every management port needs a content')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits nested ODPS fields it does not edit unchanged', async () => {
    const onSubmit = renderForm({
      ...existing,
      team: { name: 'Risk', members: [{ username: 'ana', name: 'Ana', role: 'owner', date_in: '2026-01-01' }] },
      support: [{ channel: '#risk', url: 'https://chat', tool: 'slack', scope: '', invitation_url: 'https://join' }],
    })
    fireEvent.click(screen.getByRole('button', { name: /More ODPS fields/ }))
    type('Team name', 'Credit Risk', group(/People/))
    const values = await save(onSubmit)
    expect(values.team).toEqual({
      name: 'Credit Risk',
      members: [{ username: 'ana', name: 'Ana', role: 'owner', date_in: '2026-01-01' }],
    })
    expect(values.support[0].invitation_url).toBe('https://join')
  })
})

describe('Port extras', () => {
  it('an output carries tags, SBOM links and context', async () => {
    const onSubmit = renderForm({ ...existing, output_ports: [makeOutput({ name: 'exposure', contract_id: null, version: null })] })
    const outputs = screen.getByRole('group', { name: /Outputs/ })
    fireEvent.click(within(outputs).getByRole('button', { name: 'More about exposure' }))
    type('Output tags', 'gold', outputs)
    type('Output context', 'Aggregated daily', outputs)
    fireEvent.click(within(outputs).getByRole('button', { name: 'Add SBOM link' }))
    type('SBOM URL', 'https://sbom/exposure', outputs)
    const values = await save(onSubmit)
    expect(values.output_ports[0]).toMatchObject({
      tags: ['gold'],
      context: { instructions: 'Aggregated daily' },
      sbom: [{ type: 'external', url: 'https://sbom/exposure' }],
    })
  })
})
