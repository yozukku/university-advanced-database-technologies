export type Size = 'S' | 'M' | 'L'

export type Window = { from: string; to: string }

export type Filters = Window & { size: Size }

export const SIZES: Size[] = ['S', 'M', 'L']

export const PRESETS = [
  { value: '4h', label: '+ 4 h', hours: 4 },
  { value: '1d', label: '+ 1 dzień', hours: 24 },
  { value: '3d', label: '+ 3 dni', hours: 72 },
] as const

export type Preset = (typeof PRESETS)[number]['value']

const DEFAULT_SIZE: Size = 'M'
const MINUTE_MS = 60_000
const HOUR_MS = 3_600_000

export function readFilters(params: URLSearchParams, now: number): Filters | null {
  const size = readSize(params)
  const window = readWindow(params, now)
  return size && window ? { size, ...window } : null
}

export function completeFilters(params: URLSearchParams, now: number): Filters {
  return { size: readSize(params) ?? DEFAULT_SIZE, ...(readWindow(params, now) ?? presetWindow(PRESETS[0].value, now)) }
}

export function presetWindow(preset: Preset, now: number): Window {
  const hours = PRESETS.find(candidate => candidate.value === preset)?.hours ?? PRESETS[0].hours
  const from = Math.floor(now / MINUTE_MS) * MINUTE_MS
  return { from: toInstant(from), to: toInstant(from + hours * HOUR_MS) }
}

export function presetOf({ from, to }: Window): Preset | null {
  const hours = (Date.parse(to) - Date.parse(from)) / HOUR_MS
  return PRESETS.find(preset => preset.hours === hours)?.value ?? null
}

export function toParams({ size, from, to }: Filters) {
  return new URLSearchParams({ rozmiar: size, od: from, do: to })
}

function readSize(params: URLSearchParams) {
  const size = params.get('rozmiar')
  return SIZES.find(candidate => candidate === size) ?? null
}

function readWindow(params: URLSearchParams, now: number): Window | null {
  const from = Date.parse(params.get('od') ?? '')
  const to = Date.parse(params.get('do') ?? '')
  if (!(from < to && to > now)) {
    return null
  }
  return { from: toInstant(from), to: toInstant(to) }
}

function toInstant(epochMs: number) {
  return new Date(epochMs).toISOString().replace('.000Z', 'Z')
}
