import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useLocation, useMatch, useNavigate } from 'react-router-dom'
import { useDataContract } from '../hooks/useDataContracts'
import { useDataProduct } from '../hooks/useDataProducts'
import { ChevronRightIcon, SearchIcon } from './icons'

const SECTIONS: [string, string][] = [
  ['/dashboard', 'Overview'],
  ['/data-products', 'Marketplace'],
  ['/data-contracts', 'Data contracts'],
  ['/domains', 'Domains'],
  ['/users', 'Users'],
  ['/profile', 'Profile'],
]

function useCrumbs() {
  const { pathname } = useLocation()
  const contractMatch = useMatch('/data-contracts/:id')
  const productMatch = useMatch('/data-products/:id')
  const contractId = contractMatch && contractMatch.params.id !== 'new' ? contractMatch.params.id ?? '' : ''
  const productId = productMatch?.params.id ?? ''
  const { data: contract } = useDataContract(contractId)
  const { data: product } = useDataProduct(productId)

  const section = SECTIONS.find(([prefix]) => pathname.startsWith(prefix))
  const crumbs: { label: string; to?: string; mono?: boolean }[] = []
  if (section) crumbs.push({ label: section[1], to: section[0] })
  if (contractMatch?.params.id === 'new') crumbs.push({ label: 'New contract' })
  else if (contractId) crumbs.push({ label: contract?.title ?? '…' })
  if (productId) crumbs.push({ label: product?.name ?? '…' })
  return crumbs
}

export default function TopBar() {
  const crumbs = useCrumbs()
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [query, setQuery] = useState('')

  // ⌘K / Ctrl+K jumps to search from anywhere.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  function submit(e: FormEvent) {
    e.preventDefault()
    const q = query.trim()
    navigate(q ? `/data-products?q=${encodeURIComponent(q)}` : '/data-products')
    inputRef.current?.blur()
  }

  return (
    <header className="hidden h-[52px] shrink-0 items-center gap-2.5 border-b border-line px-7 md:flex">
      <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1.5 text-[13px] text-tx3">
        {crumbs.map((c, i) => {
          const last = i === crumbs.length - 1
          return (
            <span key={`${c.label}-${i}`} className="flex min-w-0 items-center gap-1.5">
              {i > 0 && <ChevronRightIcon size={12} />}
              {last || !c.to ? (
                <span className={`truncate ${last ? 'font-medium text-tx' : ''}`} aria-current={last ? 'page' : undefined}>
                  {c.label}
                </span>
              ) : (
                <Link to={c.to} className="truncate transition-colors duration-150 hover:text-tx">
                  {c.label}
                </Link>
              )}
            </span>
          )
        })}
      </nav>

      <form
        role="search"
        onSubmit={submit}
        className="ml-auto flex h-8 w-[340px] max-w-full items-center gap-2 rounded-lg border border-line bg-panel pl-2.5 pr-1.5 text-tx3 transition-shadow duration-150 focus-within:border-accent-fg focus-within:ring-[3px] focus-within:ring-accent/20"
      >
        <SearchIcon size={15} />
        <input
          ref={inputRef}
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search data products…"
          aria-label="Search data products"
          className="min-w-0 flex-1 border-0 bg-transparent text-[13px] text-tx outline-none placeholder:text-tx3"
        />
        <span className="kbd">⌘K</span>
      </form>
    </header>
  )
}
