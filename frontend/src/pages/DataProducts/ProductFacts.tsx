import type { ReactNode } from 'react'
import { safeUrl } from '../DataContracts/contractMetadata'
import type { DataProduct } from '../../types'

function Fact({ label, children }: { label: string; children: ReactNode }) {
  return (
    <li className="flex flex-col gap-0.5 border-b border-line py-2.5 last:border-0">
      <span className="text-tx2">{label}</span>
      <span className="text-tx">{children}</span>
    </li>
  )
}

function Channel({ channel, url }: { channel: string; url: string }) {
  // A URL may still hold an unresolved ${VAR}: only a safe scheme becomes a link.
  const href = safeUrl(url)
  if (!href) return <span>{channel}</span>
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="hover:text-accent-fg hover:underline">
      {channel}
    </a>
  )
}

/** The ODPS sections of a product that are filled, in a few lines each. */
export function productFacts(p: DataProduct): ReactNode[] {
  const facts: ReactNode[] = []
  const texts: [string, string | null][] = [
    ['Version', p.version],
    ['Type', p.type],
    ['Tenant', p.tenant],
  ]
  for (const [label, value] of texts) {
    if (value) facts.push(<Fact key={label} label={label}>{value}</Fact>)
  }
  if (p.tags.length > 0) {
    facts.push(
      <Fact key="tags" label="Tags">
        <span className="flex flex-wrap gap-1.5">
          {p.tags.map((tag) => (
            <span key={tag} className="rounded border border-line2 px-1.5 text-[11.5px]">
              {tag}
            </span>
          ))}
        </span>
      </Fact>,
    )
  }
  const members = (p.team.members ?? []).map((m) => m.username)
  if (p.team.name || members.length > 0) {
    facts.push(
      <Fact key="team" label="Team">
        {p.team.name && <span className="block">{p.team.name}</span>}
        {members.length > 0 && <span className="block text-tx2">{members.join(', ')}</span>}
      </Fact>,
    )
  }
  if (p.support.length > 0) {
    facts.push(
      <Fact key="support" label="Support">
        <span className="flex flex-col">
          {p.support.map((s) => (
            <Channel key={`${s.channel}-${s.url}`} channel={s.channel} url={s.url} />
          ))}
        </span>
      </Fact>,
    )
  }
  if (p.management_ports.length > 0) {
    facts.push(
      <Fact key="management" label="Management ports">
        <span className="flex flex-col gap-1">
          {p.management_ports.map((m) => (
            <span key={m.name}>
              <span className="font-mono text-[11.5px]">{m.name}</span>
              <span className="block text-xs text-tx3">{`${m.content} · ${m.type}`}</span>
            </span>
          ))}
        </span>
      </Fact>,
    )
  }
  return facts
}
