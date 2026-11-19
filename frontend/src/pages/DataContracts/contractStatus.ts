import type { DataContract } from '../../types'

type StatusColor = 'gray' | 'yellow' | 'green' | 'red' | 'purple'

// Keyed by the status union, so a new status cannot be left without a color.
export const STATUS_COLORS: Record<DataContract['status'], StatusColor> = {
  draft: 'gray',
  in_review: 'yellow',
  active: 'green',
  deprecated: 'red',
  retired: 'purple',
}
