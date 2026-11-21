import { createHash, randomBytes } from 'node:crypto'
import { request } from '@playwright/test'

export type User = 'anna' | 'jan'
export type Size = 'S' | 'M' | 'L'
export type Offer = { size: Size; free: number; price: number }
export type Lockermat = { id: number; name: string; address: string; lng: number; lat: number; sizes: Offer[] }
export type NewOrder = { lockermatId: number; size: Size; from: string; to: string }
export type Order = Omit<NewOrder, 'lockermatId'> & {
  id: number
  number: string
  status: string
  price: number
  paymentDeadline: string
  reservationId: number
  cellNumber: number
}
export type AccessCode = { purpose: 'DROP_OFF' | 'PICK_UP'; pin: string; validFrom: string; validTo: string }
export type Opening = { id: number; purpose: AccessCode['purpose']; result: 'OPENED' | 'DOOR_FAILED' | 'PENDING' }
export type OrderEvent = { id: number; at: string; entity: string; action: string; actorKind: string }
export type IncomingShipment = {
  orderId: number
  reservationId: number
  status: string
  lockermatName: string
  lockermatAddress: string
  cellNumber: number
  from: string
  to: string
}

const APP_URL = 'http://localhost:5173'
const REALM_URL = 'http://localhost:8081/realms/bagazomat'
const CLIENT_ID = 'bagazomat-web'
const REDIRECT_URI = `${APP_URL}/`

export function resetData() {
  return call<void>('anna', 'POST', '/api/dev/reset')
}

export function findLockermats(user: User, from: string, to: string, q = '') {
  return call<Lockermat[]>(user, 'GET', `/api/lockermats?${new URLSearchParams({ q, from, to })}`)
}

export function bookStorage(user: User, order: NewOrder) {
  return call<Order>(user, 'POST', '/api/orders', order)
}

export function findOrder(user: User, orderId: number) {
  return call<Order>(user, 'GET', `/api/orders/${orderId}`)
}

export function findCodes(user: User, orderId: number) {
  return call<AccessCode[]>(user, 'GET', `/api/orders/${orderId}/codes`)
}

export function payOrder(user: User, orderId: number) {
  return call<unknown>(user, 'POST', `/api/orders/${orderId}/payments`, { result: 'SUCCESS' })
}

export function cancelOrder(user: User, orderId: number) {
  return call<unknown>(user, 'POST', `/api/orders/${orderId}/cancel`)
}

export function openCell(user: User, reservationId: number) {
  return call<Opening>(user, 'POST', `/api/reservations/${reservationId}/open`)
}

export function findHistory(user: User, orderId: number) {
  return call<OrderEvent[]>(user, 'GET', `/api/orders/${orderId}/history`)
}

export function findIncoming(user: User) {
  return call<IncomingShipment[]>(user, 'GET', '/api/shipments/incoming')
}

export function simulateShipment(user: User) {
  return call<IncomingShipment>(user, 'POST', '/api/dev/shipments')
}

async function call<T>(user: User, method: 'GET' | 'POST', path: string, data?: unknown) {
  const context = await request.newContext({
    baseURL: APP_URL,
    extraHTTPHeaders: { Authorization: `Bearer ${await accessToken(user)}` },
  })
  try {
    const response = await context.fetch(path, { method, data })
    if (!response.ok()) {
      throw new Error(`${method} ${path}: ${response.status()} ${await response.text()}`)
    }
    return (response.status() === 204 ? undefined : await response.json()) as T
  } finally {
    await context.dispose()
  }
}

async function accessToken(user: User) {
  const context = await request.newContext()
  try {
    const verifier = randomBytes(32).toString('base64url')
    const authorization = await context.get(`${REALM_URL}/protocol/openid-connect/auth`, {
      params: {
        client_id: CLIENT_ID,
        redirect_uri: REDIRECT_URI,
        response_type: 'code',
        scope: 'openid profile email',
        code_challenge: createHash('sha256').update(verifier).digest('base64url'),
        code_challenge_method: 'S256',
      },
    })
    const signIn = await context.post(loginAction(await authorization.text()), {
      form: { username: user, password: 'demo' },
      maxRedirects: 0,
    })
    const code = new URL(signIn.headers().location ?? '', APP_URL).searchParams.get('code')
    if (!code) {
      throw new Error(`Keycloak nie zalogował użytkownika ${user}: ${signIn.status()}`)
    }
    const token = await context.post(`${REALM_URL}/protocol/openid-connect/token`, {
      form: { grant_type: 'authorization_code', client_id: CLIENT_ID, redirect_uri: REDIRECT_URI, code, code_verifier: verifier },
    })
    if (!token.ok()) {
      throw new Error(`Keycloak nie wydał tokenu dla ${user}: ${token.status()} ${await token.text()}`)
    }
    return (await token.json()).access_token as string
  } finally {
    await context.dispose()
  }
}

function loginAction(html: string) {
  const formStart = html.lastIndexOf('<form', html.indexOf('kc-form-login'))
  const form = html.slice(formStart, html.indexOf('>', formStart))
  const actionStart = form.indexOf('action="')
  if (formStart < 0 || actionStart < 0) {
    throw new Error('Brak formularza logowania Keycloak')
  }
  const valueStart = actionStart + 'action="'.length
  return form.slice(valueStart, form.indexOf('"', valueStart)).replaceAll('&amp;', '&')
}
