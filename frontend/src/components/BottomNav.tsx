import { NavLink } from 'react-router-dom'
import { ContractIcon, DomainIcon, MarketplaceIcon, OverviewIcon, UsersIcon } from './icons'

const navItems = [
  { to: '/dashboard', icon: OverviewIcon, label: 'Overview' },
  { to: '/data-products', icon: MarketplaceIcon, label: 'Market' },
  { to: '/data-contracts', icon: ContractIcon, label: 'Contracts' },
  { to: '/domains', icon: DomainIcon, label: 'Domains' },
  { to: '/users', icon: UsersIcon, label: 'Users' },
]

export default function BottomNav() {
  return (
    <nav
      aria-label="Mobile navigation"
      className="fixed bottom-0 left-0 right-0 z-50 flex h-16 items-stretch border-t border-line bg-side md:hidden"
    >
      {navItems.map(({ to, icon: Icon, label }) => (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex flex-1 flex-col items-center justify-center gap-1 text-[11px] transition-colors ${
              isActive ? 'text-tx' : 'text-tx3 hover:text-tx2'
            }`
          }
        >
          {({ isActive }) => (
            <>
              <Icon size={18} className={isActive ? 'text-accent-fg' : ''} />
              <span>{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
