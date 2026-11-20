import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'
import { Button, EmptyState, Loading, Page, formatWindow } from '../../ui'
import { Chips } from './Chips'
import { PRESETS, SIZES, completeFilters, presetOf, presetWindow, readFilters, toParams, type Filters, type Size } from './filters'
import { LockerCard } from './LockerCard'
import { useLockermats } from './lockermats'
import styles from './LockersPage.module.css'
import { useDebouncedValue } from './useDebouncedValue'

const SIZE_OPTIONS = SIZES.map(size => ({ value: size, label: size }))
const SEARCH_DELAY_MS = 250

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
  const search = useDebouncedValue(query.trim(), SEARCH_DELAY_MS)
  const lockermats = useLockermats(search, filters)

  return (
    <div className={styles.lockers}>
      <div className={styles.filters}>
        <input
          type="search"
          aria-label="Szukaj punktu"
          placeholder="Miasto, adres lub nazwa punktu"
          value={query}
          onChange={event => setQuery(event.target.value)}
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
      <LockerList lockermats={lockermats} size={filters.size} />
    </div>
  )
}

function LockerList({ lockermats, size }: { lockermats: ReturnType<typeof useLockermats>; size: Size }) {
  if (!lockermats.data) {
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
  const offers = lockermats.data.flatMap(lockermat => {
    const offer = lockermat.sizes.find(candidate => candidate.size === size)
    return offer ? [{ lockermat, offer }] : []
  })
  if (offers.length === 0) {
    return <EmptyState title="Nie znaleziono punktów.">Zmień wyszukiwaną frazę.</EmptyState>
  }
  return (
    <ul aria-label="Punkty" className={styles.list}>
      {offers.map(({ lockermat, offer }) => (
        <li key={lockermat.id}>
          <LockerCard lockermat={lockermat} offer={offer} />
        </li>
      ))}
    </ul>
  )
}
