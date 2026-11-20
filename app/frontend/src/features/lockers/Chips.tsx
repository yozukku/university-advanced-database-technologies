import { useId } from 'react'
import styles from './Chips.module.css'

type Option<T extends string> = { value: T; label: string }

type ChipsProps<T extends string> = {
  legend: string
  options: readonly Option<T>[]
  value: T | null
  onChange: (value: T) => void
}

export function Chips<T extends string>({ legend, options, value, onChange }: ChipsProps<T>) {
  const name = useId()

  return (
    <fieldset className={styles.group}>
      <legend className={styles.legend}>{legend}</legend>
      <div className={styles.options}>
        {options.map(option => (
          <label key={option.value} className={styles.chip}>
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
              className={styles.input}
            />
            {option.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
