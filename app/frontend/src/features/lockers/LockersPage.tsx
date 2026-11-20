import { useEffect, useMemo, useRef, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button, EmptyState, Loading, Page, cx, formatWindow } from '../../ui'
import { Chips } from './Chips'
import { PRESETS, SIZES, completeFilters, presetOf, presetWindow, readFilters, toParams, type Filters, type Size } from './filters'
import { LockerCard } from './LockerCard'
import { LockerMap } from './LockerMap'
import { useLockermats, type Lockermat, type Offer } from './lockermats'
import styles from './LockersPage.module.css'
import { useDebouncedValue } from './useDebouncedValue'
import { ViewSwitch, type View } from './ViewSwitch'

const SIZE_OPTIONS = SIZES.map(size => ({ value: size, label: size }))
const SEARCH_DELAY_MS = 250

type Place = { lockermat: Lockermat; offer: Offer }

export function LockersPage() {
  const [params, setParams] = useSearchParams()
  const filters = readFilters(params, Date.now())
  const complete = filters !== null

  useEffect(() => {
    if (!complete) {
      setParams(toParams(completeFilters(params, Date.now())), { replace: true })
    }
  }, [complete, params, setParams])

  return (
    <Page title="Punkty">
      {filters ? <Lockers filters={filters} onChange={next => setParams(toParams(next), { replace: true, flushSync: true })} /> : <Loading />}
    </Page>
  )
}

function Lockers({ filters, onChange }: { filters: Filters; onChange: (next: Filters) => void }) {
  const [query, setQuery] = useState('')
  const [view, setView] = useState<View>('list')
  const [activeId, setActiveId] = useState<number | null>(null)
  const search = useDebouncedValue(query.trim(), SEARCH_DELAY_MS)
  const lockermats = useLockermats(search, filters)
  const places = useMemo(() => lockermats.data && placesOf(lockermats.data, filters.size), [lockermats.data, filters.size])
  const points = useMemo(() => places?.map(place => place.lockermat) ?? [], [places])
  const active = places?.find(place => place.lockermat.id === activeId)

  return (
    <div className={styles.lockers}>
      <div className={styles.side}>
        <div className={styles.filters}>
          <input
            type="search"
            aria-label="Szukaj punktu"
            placeholder="Miasto, adres lub nazwa punktu"
            value={query}
            onChange={event => {
              setQuery(event.target.value)
              setActiveId(null)
            }}
            className={styles.search}
          />
          <div className={styles.choices}>
            <Chips<Size> legend="Rozmiar" options={SIZE_OPTIONS} value={filters.size} onChange={size => onChange({ ...filters, size })} />
            <Chips
              legend="Od teraz"
              options={PRESETS}
              value={presetOf(filters)}
              onChange={preset => onChange({ size: filters.size, ...presetWindow(preset, Date.now()) })}
            />
          </div>
          <p className={styles.window}>{formatWindow(filters.from, filters.to)}</p>
        </div>
        <ViewSwitch value={view} onChange={setView} />
        <div className={cx(view !== 'list' && styles.away)}>
          <LockerList lockermats={lockermats} places={places} activeId={activeId} onSelect={setActiveId} />
        </div>
      </div>
      <section aria-label="Mapa punktów" className={cx(styles.mapPanel, view !== 'map' && styles.away)}>
        <LockerMap points={points} activeId={activeId} onSelect={setActiveId} className={styles.map} />
        {view === 'map' && active && (
          <div className={styles.mapCard}>
            <LockerCard lockermat={active.lockermat} offer={active.offer} />
          </div>
        )}
      </section>
    </div>
  )
}

type LockerListProps = {
  lockermats: ReturnType<typeof useLockermats>
  places: Place[] | undefined
  activeId: number | null
  onSelect: (id: number) => void
}

function LockerList({ lockermats, places, activeId, onSelect }: LockerListProps) {
  if (!places) {
    if (lockermats.isError) {
      return (
        <EmptyState title="Nie udało się wczytać punktów.">
          <Button variant="secondary" onClick={() => void lockermats.refetch()}>
            Spróbuj ponownie
          </Button>
        </EmptyState>
      )
    }
    return <Loading />
  }
  if (places.length === 0) {
    return <EmptyState title="Nie znaleziono punktów.">Zmień wyszukiwaną frazę.</EmptyState>
  }
  return (
    <ul aria-label="Punkty" className={styles.list}>
      {places.map(place => (
        <LockerRow key={place.lockermat.id} place={place} active={place.lockermat.id === activeId} onSelect={onSelect} />
      ))}
    </ul>
  )
}

function LockerRow({ place: { lockermat, offer }, active, onSelect }: { place: Place; active: boolean; onSelect: (id: number) => void }) {
  const row = useRef<HTMLLIElement>(null)

  useEffect(() => {
    if (active) {
      row.current?.scrollIntoView({ block: 'nearest' })
    }
  }, [active])

  return (
    <li ref={row} className={styles.row}>
      <LockerCard lockermat={lockermat} offer={offer} active={active} onSelect={() => onSelect(lockermat.id)} />
    </li>
  )
}

function placesOf(lockermats: Lockermat[], size: Size) {
  return lockermats.flatMap(lockermat => {
    const offer = lockermat.sizes.find(candidate => candidate.size === size)
    return offer ? [{ lockermat, offer }] : []
  })
}
