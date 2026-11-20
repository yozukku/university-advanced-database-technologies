import { useCallback } from 'react'
import { useAuth } from 'react-oidc-context'

const NETWORK_MESSAGE = 'Brak połączenia z serwerem. Sprawdź połączenie i spróbuj ponownie.'
const SESSION_MESSAGE = 'Sesja wygasła. Zaloguj się ponownie.'
const UNKNOWN_MESSAGE = 'Wystąpił nieoczekiwany błąd. Spróbuj ponownie później.'

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

type RequestOptions = {
  method?: 'GET' | 'POST'
  body?: unknown
  signal?: AbortSignal
}

export function useApi() {
  const token = useAuth().user?.access_token
  return useCallback(<T>(path: string, options?: RequestOptions) => request<T>(token, path, options), [token])
}

export function errorMessage(error: unknown) {
  return error instanceof ApiError ? error.message : UNKNOWN_MESSAGE
}

async function request<T>(token: string | undefined, path: string, { method = 'GET', body, signal }: RequestOptions = {}) {
  const headers = new Headers({ Accept: 'application/json' })
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (body !== undefined) {
    headers.set('Content-Type', 'application/json')
  }
  let response: Response
  try {
    response = await fetch(path, { method, headers, signal, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch (error) {
    if (signal?.aborted) {
      throw error
    }
    throw new ApiError(0, 'NETWORK', NETWORK_MESSAGE)
  }
  if (!response.ok) {
    throw await toApiError(response)
  }
  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}

async function toApiError(response: Response) {
  if (response.status === 401) {
    return new ApiError(401, 'UNAUTHORIZED', SESSION_MESSAGE)
  }
  const body = await response.json().catch(() => null)
  if (typeof body?.code === 'string' && typeof body?.message === 'string') {
    return new ApiError(response.status, body.code, body.message)
  }
  return new ApiError(response.status, 'UNKNOWN', UNKNOWN_MESSAGE)
}
