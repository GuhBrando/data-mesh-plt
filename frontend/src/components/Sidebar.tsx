import { useEffect, useRef, useState, type ComponentType } from 'react'
import { NavLink, Link, useNavigate } from 'react-router-dom'
import { useTheme } from '../contexts/ThemeContext'
import { useAuth } from '../contexts/AuthContext'
import { post } from '../lib/api'
import { getRefreshToken } from '../lib/auth'
import { useDataProducts } from '../hooks/useDataProducts'
import { useDataContracts } from '../hooks/useDataContracts'
import { useAllDomains } from '../hooks/useDomains'
import { useUsers } from '../hooks/useUsers'
import Mark from './brand/Mark'
import { Avatar } from './ui/Glyphs'
import {
  ContractIcon,
  DomainIcon,
  MarketplaceIcon,
  MoonIcon,
  NewContractIcon,
  OverviewIcon,
  PlusIcon,
  ProductIcon,
  SignOutIcon,
  SunIcon,
  UsersIcon,
  type IconProps,
} from './icons'

interface NavItem {
  to: string
  label: string
  icon: ComponentType<IconProps>
  count?: number
}

function NavItemLink({ to, label, icon: Icon, count }: NavItem) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) =>
        `group flex h-[30px] items-center gap-2.5 rounded-[7px] px-2.5 text-[13px] transition-colors duration-150 ${
          isActive
            ? 'bg-raised font-medium text-tx shadow-[inset_0_0_0_1px_rgb(var(--line))]'
            : 'text-tx2 hover:bg-hover hover:text-tx'
        }`
      }
    >
      {({ isActive }) => (
        <>
          <Icon
            className={`transition-colors duration-150 ${
              isActive ? 'text-accent-fg' : 'text-tx3 group-hover:text-tx2'
            }`}
          />
          <span className="truncate">{label}</span>
          {count !== undefined && (
            <span className="ml-auto font-mono text-[11px] font-medium text-tx3">{count}</span>
          )}
        </>
      )}
    </NavLink>
  )
}

function NewMenu() {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const go = (to: string) => {
    setOpen(false)
    navigate(to)
  }

  return (
    <div ref={ref} className="relative mb-1.5">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-haspopup="menu"
        className="flex h-8 w-full items-center gap-2 rounded-lg border border-line2 bg-panel px-2.5 text-[13px] font-medium text-tx transition-colors duration-150 hover:border-tx3 hover:bg-hover"
      >
        <PlusIcon className="text-accent-fg" />
        New
      </button>
      {open && (
        <div
          role="menu"
          className="absolute left-0 right-0 top-[calc(100%+4px)] z-30 animate-swap rounded-lg border border-line bg-panel p-1 shadow-[var(--shadow)]"
        >
          <button
            type="button"
            role="menuitem"
            onClick={() => go('/data-contracts/new')}
            className="flex h-8 w-full items-center gap-2.5 rounded-md px-2 text-[13px] text-tx2 hover:bg-hover hover:text-tx"
          >
            <NewContractIcon className="text-tx3" />
            Data contract
          </button>
          <button
            type="button"
            role="menuitem"
            onClick={() => go('/data-products?new=1')}
            className="flex h-8 w-full items-center gap-2.5 rounded-md px-2 text-[13px] text-tx2 hover:bg-hover hover:text-tx"
          >
            <ProductIcon className="text-tx3" />
            Data product
          </button>
        </div>
      )}
    </div>
  )
}

export default function Sidebar() {
  const { theme, toggle } = useTheme()
  const { user, logout } = useAuth()
  const [isLoggingOut, setIsLoggingOut] = useState(false)

  const { data: products } = useDataProducts()
  const { data: contracts } = useDataContracts()
  const { data: domains } = useAllDomains()
  const { data: users } = useUsers()

  async function handleLogout() {
    setIsLoggingOut(true)
    try {
      const refreshToken = getRefreshToken()
      if (refreshToken) {
        await post('/auth/logout', { refresh_token: refreshToken })
      }
    } finally {
      logout()
    }
  }

  return (
    <aside className="hidden w-[232px] shrink-0 flex-col border-r border-line bg-side px-2.5 py-3 md:flex">
      {/* Brand */}
      <Link to="/dashboard" className="mb-3.5 flex items-center gap-2.5 rounded-lg px-1.5 py-1">
        <Mark size={24} />
        <span className="min-w-0">
          <span className="block text-[13px] font-semibold leading-tight text-tx">DataMesh</span>
          <span className="block font-mono text-[11px] leading-tight text-tx3">platform</span>
        </span>
      </Link>

      <NewMenu />

      <nav aria-label="Main navigation" className="flex flex-col gap-px">
        <NavItemLink to="/dashboard" label="Overview" icon={OverviewIcon} />
        <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-medium text-tx3">Catalog</p>
        <NavItemLink to="/data-products" label="Marketplace" icon={MarketplaceIcon} count={products?.length} />
        <NavItemLink to="/data-contracts" label="Data contracts" icon={ContractIcon} count={contracts?.length} />
        <NavItemLink to="/domains" label="Domains" icon={DomainIcon} count={domains?.length} />
        <p className="px-2.5 pb-1.5 pt-4 text-[11px] font-medium text-tx3">Admin</p>
        <NavItemLink to="/users" label="Users" icon={UsersIcon} count={users?.length} />
      </nav>

      {/* Footer */}
      <div className="mt-auto flex items-center gap-0.5 border-t border-line pt-2.5">
        {user && (
          <Link
            to="/profile"
            className="flex min-w-0 flex-1 items-center gap-2 rounded-lg p-1.5 transition-colors duration-150 hover:bg-hover"
            title="View profile"
          >
            <Avatar name={user.username} />
            <span className="min-w-0">
              <span className="block truncate text-[12.5px] font-medium leading-tight text-tx">{user.username}</span>
              <span className="block text-[11px] leading-tight text-tx3">{user.role}</span>
            </span>
          </Link>
        )}
        <button
          type="button"
          onClick={toggle}
          className="grid h-[30px] w-[30px] place-items-center rounded-[7px] text-tx2 transition-colors duration-150 hover:bg-hover hover:text-tx"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
          title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
        >
          {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
        </button>
        <button
          type="button"
          onClick={handleLogout}
          disabled={isLoggingOut}
          className="grid h-[30px] w-[30px] place-items-center rounded-[7px] text-tx2 transition-colors duration-150 hover:bg-bad/10 hover:text-bad disabled:cursor-not-allowed disabled:opacity-50"
          aria-label={isLoggingOut ? 'Signing out' : 'Sign out'}
          title="Sign out"
        >
          <SignOutIcon />
        </button>
      </div>
    </aside>
  )
}
