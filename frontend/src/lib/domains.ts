import { STATUS_ORDER } from './contracts'
import type { DataContract, DomainWithMembers, DomainAccess, User } from '../types'

export function getDomainAccess(
  domain: DomainWithMembers,
  userId: string,
  userRole?: string,
): DomainAccess {
  if (userRole === 'PLATFORM_ADMIN') return 'admin'
  if (domain.owner_id === userId) return 'owner'
  const member = domain.members.find((m) => m.user_id === userId)
  if (!member) return 'none'
  return member.role
}

/**
 * The contracts a user may build a data product on: those of a domain they
 * belong to, or every one for a platform admin. Active contracts come first.
 * `keepId` (the contract a product already uses) is always kept, at the top,
 * so editing a product never drops its current link from the choices.
 */
export function selectableContracts(
  contracts: DataContract[],
  domains: DomainWithMembers[],
  user: Pick<User, 'id' | 'role'> | null,
  keepId?: string,
): DataContract[] {
  if (!user) return []
  const isAdmin = user.role === 'PLATFORM_ADMIN'
  const reachable = new Set(
    domains.filter((d) => getDomainAccess(d, user.id, user.role) !== 'none').map((d) => d.id),
  )
  const rank = (c: DataContract) => (c.id === keepId ? -1 : STATUS_ORDER.indexOf(c.status))
  return contracts
    .filter((c) => isAdmin || c.id === keepId || reachable.has(c.domain_id))
    .sort((a, b) => rank(a) - rank(b) || a.title.localeCompare(b.title))
}
