/** Always display / compare times in East Asia (UTC+8), regardless of server or browser locale. */
export const EAST_ASIA_TZ = 'Asia/Shanghai'

/** Parse API datetimes: naive ISO strings are treated as UTC (backend stores utcnow). */
export function parseApiDate(input: string | Date | null | undefined): Date | null {
  if (!input) return null
  if (input instanceof Date) {
    return Number.isNaN(input.getTime()) ? null : input
  }
  const raw = String(input).trim()
  if (!raw) return null
  const hasTz = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(raw)
  const normalized = hasTz ? raw : `${raw.replace(/\s/, 'T')}Z`
  const d = new Date(normalized)
  return Number.isNaN(d.getTime()) ? null : d
}

function partsInShanghai(d: Date) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: EAST_ASIA_TZ,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    weekday: 'short',
  })
  const bag: Record<string, string> = {}
  for (const p of fmt.formatToParts(d)) {
    if (p.type !== 'literal') bag[p.type] = p.value
  }
  return {
    year: bag.year,
    month: bag.month,
    day: bag.day,
    hour: bag.hour === '24' ? '00' : bag.hour,
    minute: bag.minute,
    second: bag.second,
    weekday: bag.weekday,
  }
}

function shanghaiDayKey(d: Date) {
  const p = partsInShanghai(d)
  return `${p.year}-${p.month}-${p.day}`
}

export function formatDateShanghai(
  input: string | Date | null | undefined,
  style: 'date' | 'datetime' | 'time' | 'chat' = 'datetime',
  localeLabels?: { yesterday: string },
): string {
  const d = parseApiDate(input)
  if (!d) return ''
  const p = partsInShanghai(d)
  if (style === 'date') return `${p.year}-${p.month}-${p.day}`
  if (style === 'time') return `${p.hour}:${p.minute}`
  if (style === 'datetime') return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`

  const nowKey = shanghaiDayKey(new Date())
  const dayKey = shanghaiDayKey(d)
  const hm = `${p.hour}:${p.minute}`
  if (dayKey === nowKey) return hm
  const yest = new Date()
  yest.setTime(yest.getTime() - 24 * 60 * 60 * 1000)
  if (dayKey === shanghaiDayKey(yest)) {
    return `${localeLabels?.yesterday || '昨天'} ${hm}`
  }
  return `${Number(p.month)}/${Number(p.day)} ${hm}`
}

export function shanghaiYear(d: Date = new Date()): number {
  return Number(partsInShanghai(d).year)
}
