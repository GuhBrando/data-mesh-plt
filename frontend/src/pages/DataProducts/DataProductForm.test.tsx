import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { beforeEach, describe, it, expect, vi } from 'vitest'
import DataProductForm from './DataProductForm'
import { useSelectableContracts } from '../../hooks/useSelectableContracts'
import { useDataContracts } from '../../hooks/useDataContracts'
import { useDataProducts } from '../../hooks/useDataProducts'
import { useAllDomains } from '../../hooks/useDomains'
import { useAuth } from '../../contexts/AuthContext'
import { makeContract, makeDomain, makeInput, makeOutput, makeProduct, makeUser } from '../../test/fixtures'
import type { DomainWithMembers } from '../../types'

vi.mock('../../hooks/useSelectableContracts', () => ({ useSelectableContracts: vi.fn() }))
vi.mock('../../hooks/useDataContracts', () => ({ useDataContracts: vi.fn() }))
vi.mock('../../hooks/useDataProducts', () => ({ useDataProducts: vi.fn() }))
vi.mock('../../hooks/useDomains', () => ({ useAllDomains: vi.fn() }))
vi.mock('../../contexts/AuthContext', () => ({ useAuth: vi.fn() }))

const orders = makeContract({ id: 'c1', title: 'Orders', version: '1.2.0', domain_id: 'd1' })
const sales = makeDomain({ id: 'd1', name: 'Sales', owner_id: 'u1', members: [] })
const risk = makeDomain({ id: 'd2', name: 'Risk', owner_id: 'u1', members: [] })

function query(data: unknown) {
  return { data, isLoading: false, error: null } as never
}

function setup({ domains = [sales] as DomainWithMembers[] } = {}) {
  vi.mocked(useAuth).mockReturnValue({ user: makeUser({ id: 'u1', role: 'DATA_OWNER' }) } as never)
  vi.mocked(useAllDomains).mockReturnValue(query(domains))
  vi.mocked(useSelectableContracts).mockReturnValue({ contracts: [orders], isLoading: false, error: null })
  vi.mocked(useDataContracts).mockReturnValue(query([orders]))
  vi.mocked(useDataProducts).mockReturnValue(query([]))
}

function renderForm(props: Partial<Parameters<typeof DataProductForm>[0]> = {}) {
  const onSubmit = vi.fn()
  const onCancel = vi.fn()
  render(<DataProductForm onSubmit={onSubmit} onCancel={onCancel} isSubmitting={false} {...props} />)
  return { onSubmit, onCancel }
}

function fillAbout() {
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Risk Hub' } })
  fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Credit exposure by client' } })
}

function outputsSection() {
  return screen.getByRole('group', { name: /Outputs/ })
}

beforeEach(() => setup())

describe('DataProductForm — create', () => {
  it('starts as a draft with one empty output', () => {
    renderForm()
    expect(screen.getByRole('button', { name: 'Create Product' })).toBeInTheDocument()
    expect(screen.getByLabelText('Status')).toHaveValue('draft')
    expect(within(outputsSection()).getAllByLabelText('Output name')).toHaveLength(1)
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(
      expect.arrayContaining(['Proposed', 'Draft', 'Active', 'Deprecated', 'Retired']),
    )
  })

  it('preselects the only domain the user belongs to', () => {
    renderForm()
    expect(screen.getByLabelText('Domain')).toHaveValue('d1')
  })

  it('asks for a domain when the user belongs to several', async () => {
    setup({ domains: [sales, risk] })
    const { onSubmit } = renderForm()
    expect(screen.getByLabelText('Domain')).toHaveValue('')
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    expect(await screen.findByText('Choose a domain')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('asks for a port name and shows rule 1 on the Outputs section', async () => {
    const { onSubmit } = renderForm()
    fillAbout()
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    expect(await within(outputsSection()).findByRole('alert')).toHaveTextContent('Every port needs a name')
    fireEvent.click(within(outputsSection()).getByRole('button', { name: 'Remove' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    await waitFor(() =>
      expect(within(outputsSection()).getByRole('alert')).toHaveTextContent('A data product needs at least one output'),
    )
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('refuses two outputs with the same name and version', async () => {
    const { onSubmit } = renderForm()
    fillAbout()
    fireEvent.change(screen.getByLabelText('Output name'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add output' }))
    fireEvent.change(screen.getAllByLabelText('Output name')[1], { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    expect(await within(outputsSection()).findByRole('alert')).toHaveTextContent(
      'Two outputs share the name x and version (none)',
    )
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits the product with its ports', async () => {
    const { onSubmit } = renderForm()
    fillAbout()
    fireEvent.change(screen.getByLabelText('Output name'), { target: { value: 'alerts' } })
    fireEvent.click(screen.getByRole('button', { name: 'External source' }))
    fireEvent.change(screen.getByLabelText('Input name'), { target: { value: 'core' } })
    fireEvent.change(screen.getByLabelText('Source link'), { target: { value: 'https://wiki/core' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0]).toEqual({
      name: 'Risk Hub',
      description: { purpose: 'Credit exposure by client', usage: '', limitations: '' },
      domain_id: 'd1',
      status: 'draft',
      version: null,
      type: null,
      tenant: null,
      tags: [],
      synonyms: [],
      context: {},
      team: {},
      support: [],
      custom_properties: [],
      authoritative_definitions: [],
      management_ports: [],
      input_ports: [
        {
          name: 'core',
          contract_id: null,
          version: null,
          deprecated: false,
          authoritative_definitions: [{ type: 'implementation', url: 'https://wiki/core' }],
          tags: [],
          custom_properties: [],
        },
      ],
      output_ports: [
        {
          name: 'alerts',
          contract_id: null,
          version: null,
          type: 'tables',
          description: null,
          deprecated: false,
          authoritative_definitions: [],
          input_contracts: [],
          tags: [],
          custom_properties: [],
          synonyms: [],
          context: {},
          sbom: [],
        },
      ],
    })
  })

  it('submits an output contract picked from the domains of the user', async () => {
    const { onSubmit } = renderForm()
    fillAbout()
    fireEvent.click(screen.getByRole('button', { name: 'Add a contract' }))
    fireEvent.click(screen.getByRole('radio', { name: 'Orders' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Product' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    expect(onSubmit.mock.calls[0][0].output_ports[0]).toMatchObject({ name: 'orders', contract_id: 'c1', version: '1.2.0' })
    expect(onSubmit.mock.calls[0][0].output_ports[0]).not.toHaveProperty('contract')
  })

  it('calls onCancel', () => {
    const { onCancel } = renderForm()
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(onCancel).toHaveBeenCalledOnce()
  })
})

describe('DataProductForm — edit', () => {
  const existing = makeProduct({
    name: 'Existing Product',
    description: { purpose: 'An existing data product description', usage: 'Daily', limitations: '' },
    domain_id: 'd2',
    input_ports: [makeInput({ id: 'i1', name: 'cad', version: '1.0.0' })],
    output_ports: [
      makeOutput({ id: 'o1', name: 'exp', version: '1.0.0', input_contracts: [{ contract_id: 'c1', version: '1.0.0' }] }),
      makeOutput({ id: 'o2', name: 'exp', version: '1.1.0' }),
    ],
  })

  beforeEach(() => setup({ domains: [sales, risk] }))

  it('keeps the product domain and lists newer versions first', () => {
    renderForm({ defaultValues: existing })
    expect(screen.getByRole('button', { name: 'Save Changes' })).toBeInTheDocument()
    expect(screen.getByLabelText('Domain')).toHaveValue('d2')
    expect(screen.getByLabelText('Name')).toHaveValue('Existing Product')
    expect(screen.getAllByText('older version')).toHaveLength(1)
  })

  it('shows the product domain once the domain list arrives after the form opens', () => {
    vi.mocked(useAllDomains).mockReturnValue(query(undefined))
    const props = { defaultValues: existing, onSubmit: vi.fn(), onCancel: vi.fn(), isSubmitting: false }
    const { rerender } = render(<DataProductForm {...props} />)
    vi.mocked(useAllDomains).mockReturnValue(query([sales, risk]))
    rerender(<DataProductForm {...props} />)
    expect(screen.getByLabelText('Domain')).toHaveValue('d2')
  })

  it('submits pinned versions and nothing the API computes', async () => {
    const { onSubmit } = renderForm({ defaultValues: existing })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    const values = onSubmit.mock.calls[0][0]
    expect(values.output_ports.map((p: { version: string }) => p.version)).toEqual(['1.1.0', '1.0.0'])
    expect(values.output_ports[1].input_contracts).toEqual([{ contract_id: 'c1', version: '1.0.0' }])
    expect(values.input_ports[0]).toEqual({
      name: 'cad',
      contract_id: 'c1',
      version: '1.0.0',
      deprecated: false,
      authoritative_definitions: [],
      tags: [],
      custom_properties: [],
    })
    expect(values.description).toEqual({ purpose: 'An existing data product description', usage: 'Daily', limitations: '' })
  })

  it('sends back the ODPS sections it does not show, unchanged', async () => {
    const team = { name: 'Risk', members: [{ username: 'ana', name: '', role: 'owner', date_in: '2026-01-01' }] }
    const support = [{ channel: '#risk', url: '${SUPPORT_URL}', invitation_url: 'https://join' }]
    const writable = { name: 'metrics', content: 'observability', type: 'rest', deprecated: false, tags: ['ops'] }
    const metrics = { id: 'm1', ...writable }
    const { onSubmit } = renderForm({
      defaultValues: { ...existing, team, support, tenant: 'acme', management_ports: [metrics] },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }))
    await waitFor(() => expect(onSubmit).toHaveBeenCalledOnce())
    const values = onSubmit.mock.calls[0][0]
    expect([values.team, values.support, values.tenant]).toEqual([team, support, 'acme'])
    // The id is the API's; it never goes back.
    expect(values.management_ports).toEqual([writable])
  })
})
