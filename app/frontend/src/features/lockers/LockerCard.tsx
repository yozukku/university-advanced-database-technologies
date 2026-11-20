import { Card, cx, formatPrice } from '../../ui'
import styles from './LockerCard.module.css'
import type { Lockermat, Offer } from './lockermats'

const plural = new Intl.PluralRules('pl-PL')
const FREE_FORMS: Record<string, string> = { one: 'wolna skrytka', few: 'wolne skrytki' }

export function LockerCard({ lockermat, offer }: { lockermat: Lockermat; offer: Offer }) {
  return (
    <Card className={styles.card}>
      <div className={styles.place}>
        <h2 className={styles.name}>{lockermat.name}</h2>
        <p className={styles.address}>{lockermat.address}</p>
      </div>
      <div className={styles.offer}>
        <p className={styles.price}>{formatPrice(offer.price)}</p>
        <p className={cx(styles.free, offer.free === 0 && styles.none)}>{freeLabel(offer.free)}</p>
      </div>
    </Card>
  )
}

function freeLabel(free: number) {
  if (free === 0) {
    return 'Brak wolnych skrytek'
  }
  return `${free} ${FREE_FORMS[plural.select(free)] ?? 'wolnych skrytek'}`
}
