import type { ButtonHTMLAttributes } from 'react'
import styles from './Button.module.css'
import { cx } from './cx'

type Variant = 'primary' | 'secondary' | 'ghost'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }

export function Button({ variant = 'primary', type = 'button', className, ...props }: ButtonProps) {
  return <button type={type} className={cx(styles.button, styles[variant], className)} {...props} />
}
