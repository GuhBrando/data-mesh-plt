import type { ReactNode, SVGProps } from 'react'

/**
 * The app's own icon set: 16px grid, 1.5 stroke, round joins, currentColor.
 * Sized with `size`; colour comes from the surrounding text colour.
 */
export interface IconProps extends Omit<SVGProps<SVGSVGElement>, 'children'> {
  size?: number
}

function icon(paths: ReactNode, displayName: string) {
  function Icon({ size = 16, className = '', ...props }: IconProps) {
    return (
      <svg
        width={size}
        height={size}
        viewBox="0 0 16 16"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        className={`shrink-0 ${className}`}
        {...props}
      >
        {paths}
      </svg>
    )
  }
  Icon.displayName = displayName
  return Icon
}

export const OverviewIcon = icon(
  <>
    <rect x="2" y="2.5" width="12" height="11" rx="2" />
    <path d="M4.75 10 6.75 7.75 8.5 9.25 11.25 6" />
  </>,
  'OverviewIcon',
)

export const MarketplaceIcon = icon(
  <>
    <path d="M2.75 6.75v6.5h10.5v-6.5" />
    <path d="M2 6.25 3.25 2.75h9.5L14 6.25" />
    <path d="M2 6.25c0 1.1.9 1.75 2 1.75s2-.65 2-1.75c0 1.1.9 1.75 2 1.75s2-.65 2-1.75c0 1.1.9 1.75 2 1.75s2-.65 2-1.75" />
    <path d="M6.5 13.25v-3h3v3" />
  </>,
  'MarketplaceIcon',
)

export const ContractIcon = icon(
  <>
    <path d="M4 1.75h5.5l3 3v9.5H4z" />
    <path d="M9.5 1.75v3h3" />
    <path d="M6.25 7h3.5" />
    <path d="m6.25 10.5 1.25 1.25 2.5-2.5" />
  </>,
  'ContractIcon',
)

export const NewContractIcon = icon(
  <>
    <path d="M4 1.75h5.5l3 3v9.5H4z" />
    <path d="M9.5 1.75v3h3" />
    <path d="M8 7v4M6 9h4" />
  </>,
  'NewContractIcon',
)

export const ProductIcon = icon(
  <>
    <path d="M8 1.75 13.5 4.75v6.5L8 14.25 2.5 11.25v-6.5z" />
    <path d="M2.5 4.75 8 7.75l5.5-3M8 7.75v6.5" />
  </>,
  'ProductIcon',
)

export const DomainIcon = icon(
  <>
    <circle cx="8" cy="8" r="6.25" />
    <circle cx="8" cy="5.6" r="1" />
    <circle cx="5.7" cy="9.8" r="1" />
    <circle cx="10.3" cy="9.8" r="1" />
  </>,
  'DomainIcon',
)

export const UsersIcon = icon(
  <>
    <circle cx="6" cy="5.5" r="2.25" />
    <path d="M2 13.25c.4-2.2 2-3.5 4-3.5s3.6 1.3 4 3.5" />
    <path d="M10.25 3.4a2.25 2.25 0 0 1 0 4.2" />
    <path d="M11.75 9.9c1.1.5 1.9 1.6 2.25 3.35" />
  </>,
  'UsersIcon',
)

export const UserPlusIcon = icon(
  <>
    <circle cx="6" cy="5.5" r="2.25" />
    <path d="M2 13.25c.4-2.2 2-3.5 4-3.5s3.6 1.3 4 3.5" />
    <path d="M11.5 4.5v4M9.5 6.5h4" />
  </>,
  'UserPlusIcon',
)

export const SearchIcon = icon(
  <>
    <circle cx="7" cy="7" r="4.25" />
    <path d="m10.25 10.25 3.25 3.25" />
  </>,
  'SearchIcon',
)

export const FilterIcon = icon(<path d="M2.5 3.5h11L9.5 8.25v4.25l-3 1.25V8.25z" />, 'FilterIcon')

export const PlusIcon = icon(<path d="M8 3.25v9.5M3.25 8h9.5" />, 'PlusIcon')

export const ChevronRightIcon = icon(<path d="m6 3.5 4.5 4.5L6 12.5" />, 'ChevronRightIcon')

export const ChevronDownIcon = icon(<path d="m4.5 6.5 3.5 3.5 3.5-3.5" />, 'ChevronDownIcon')

export const ArrowRightIcon = icon(<path d="M3 8h10M9 4l4 4-4 4" />, 'ArrowRightIcon')

export const ArrowUpRightIcon = icon(<path d="M5 11 11 5M6 5h5v5" />, 'ArrowUpRightIcon')

export const SunIcon = icon(
  <>
    <circle cx="8" cy="8" r="2.75" />
    <path d="M8 1.75v1.5M8 12.75v1.5M1.75 8h1.5M12.75 8h1.5M3.6 3.6l1.05 1.05M11.35 11.35l1.05 1.05M3.6 12.4l1.05-1.05M11.35 4.65l1.05-1.05" />
  </>,
  'SunIcon',
)

export const MoonIcon = icon(<path d="M13.25 9.6A5.5 5.5 0 1 1 6.4 2.75a4.4 4.4 0 0 0 6.85 6.85z" />, 'MoonIcon')

export const SignOutIcon = icon(
  <>
    <path d="M6.5 2.75H3.75v10.5H6.5" />
    <path d="M10 5l3 3-3 3M13 8H6.75" />
  </>,
  'SignOutIcon',
)

export const RepoIcon = icon(
  <>
    <circle cx="4.75" cy="3.75" r="1.5" />
    <circle cx="4.75" cy="12.25" r="1.5" />
    <circle cx="11.25" cy="5.75" r="1.5" />
    <path d="M4.75 5.25v5.5M11.25 7.25c0 2.5-2.5 3-6.5 3.5" />
  </>,
  'RepoIcon',
)

export const PendingIcon = icon(<circle cx="8" cy="8" r="5.25" strokeDasharray="22 11" />, 'PendingIcon')

export const AlertIcon = icon(
  <>
    <path d="M8 2.25 14.25 13.25H1.75z" />
    <path d="M8 6.5v3" />
    <path d="M8 11.5v.01" />
  </>,
  'AlertIcon',
)

export const ShieldIcon = icon(
  <>
    <path d="M8 1.75 13 3.5v4c0 3.2-2.1 5.6-5 6.75C5.1 13.1 3 10.7 3 7.5v-4z" />
    <path d="m5.9 8 1.5 1.5 2.7-2.7" />
  </>,
  'ShieldIcon',
)

export const ShieldAlertIcon = icon(
  <>
    <path d="M8 1.75 13 3.5v4c0 3.2-2.1 5.6-5 6.75C5.1 13.1 3 10.7 3 7.5v-4z" />
    <path d="M8 5.5v3" />
    <path d="M8 10.5v.01" />
  </>,
  'ShieldAlertIcon',
)

export const GridIcon = icon(
  <>
    <rect x="2.25" y="2.25" width="4.75" height="4.75" rx="1" />
    <rect x="9" y="2.25" width="4.75" height="4.75" rx="1" />
    <rect x="2.25" y="9" width="4.75" height="4.75" rx="1" />
    <rect x="9" y="9" width="4.75" height="4.75" rx="1" />
  </>,
  'GridIcon',
)

export const ListIcon = icon(
  <>
    <path d="M5.5 4h8M5.5 8h8M5.5 12h8" />
    <path d="M2.5 4h.01M2.5 8h.01M2.5 12h.01" />
  </>,
  'ListIcon',
)

export const TrashIcon = icon(
  <>
    <path d="M2.75 4.25h10.5" />
    <path d="M6.25 4.25v-1.5h3.5v1.5" />
    <path d="M4 4.25l.6 9h6.8l.6-9" />
  </>,
  'TrashIcon',
)

export const SchemaIcon = icon(
  <>
    <rect x="2.25" y="2.75" width="11.5" height="10.5" rx="1.75" />
    <path d="M2.25 6.25h11.5M6.25 6.25v7" />
  </>,
  'SchemaIcon',
)

export const ServerIcon = icon(
  <>
    <path d="M8 1.75 14 5 8 8.25 2 5z" />
    <path d="m2 8 6 3.25L14 8" />
    <path d="m2 11 6 3.25L14 11" />
  </>,
  'ServerIcon',
)

export const ClockIcon = icon(
  <>
    <circle cx="8" cy="8" r="6.25" />
    <path d="M8 4.75V8l2.25 1.5" />
  </>,
  'ClockIcon',
)

export const EditIcon = icon(<path d="M10.5 2.5 13.5 5.5 6 13H3v-3z" />, 'EditIcon')

export const CodeFileIcon = icon(
  <>
    <path d="M4 1.75h5.5l3 3v9.5H4z" />
    <path d="M9.5 1.75v3h3" />
    <path d="m7 8.25-1.5 1.5L7 11.25M9 8.25l1.5 1.5L9 11.25" />
  </>,
  'CodeFileIcon',
)

export const SupportIcon = icon(<path d="M2.5 3.5h11v7.5H7l-3 2.5v-2.5H2.5z" />, 'SupportIcon')
