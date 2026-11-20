import { useId, useRef, type KeyboardEvent, type ReactNode } from 'react'
import styles from './Tabs.module.css'

type Tab<T extends string> = { value: T; label: string }

type TabsProps<T extends string> = {
  label: string
  tabs: Tab<T>[]
  value: T
  onChange: (value: T) => void
  children: ReactNode
}

const STEPS: Record<string, number> = { ArrowLeft: -1, ArrowRight: 1 }

export function Tabs<T extends string>({ label, tabs, value, onChange, children }: TabsProps<T>) {
  const id = useId()
  const buttons = useRef<Array<HTMLButtonElement | null>>([])

  function onKeyDown(event: KeyboardEvent, index: number) {
    const step = STEPS[event.key]
    if (!step) {
      return
    }
    event.preventDefault()
    const next = (index + step + tabs.length) % tabs.length
    buttons.current[next]?.focus()
    onChange(tabs[next].value)
  }

  return (
    <div className={styles.tabs}>
      <div role="tablist" aria-label={label} className={styles.list}>
        {tabs.map((tab, index) => (
          <button
            key={tab.value}
            ref={button => {
              buttons.current[index] = button
            }}
            id={`${id}-${tab.value}`}
            type="button"
            role="tab"
            aria-selected={tab.value === value}
            aria-controls={`${id}-panel`}
            tabIndex={tab.value === value ? 0 : -1}
            className={styles.tab}
            onClick={() => onChange(tab.value)}
            onKeyDown={event => onKeyDown(event, index)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div id={`${id}-panel`} role="tabpanel" aria-labelledby={`${id}-${value}`}>
        {children}
      </div>
    </div>
  )
}
