import { useState } from 'react'
import styles from './motion.module.css'

export const reveal = styles.reveal

export function useReveal(value: unknown) {
  const [initial] = useState(value)
  return value === initial ? undefined : reveal
}
