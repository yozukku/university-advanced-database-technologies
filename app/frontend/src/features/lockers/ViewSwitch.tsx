import styles from './ViewSwitch.module.css'

export type View = 'list' | 'map'

const VIEWS: { value: View; label: string }[] = [
  { value: 'list', label: 'Lista' },
  { value: 'map', label: 'Mapa' },
]

export function ViewSwitch({ value, onChange }: { value: View; onChange: (view: View) => void }) {
  return (
    <div role="group" aria-label="Widok" className={styles.switch}>
      {VIEWS.map(view => (
        <button key={view.value} type="button" aria-pressed={view.value === value} onClick={() => onChange(view.value)} className={styles.option}>
          {view.label}
        </button>
      ))}
    </div>
  )
}
