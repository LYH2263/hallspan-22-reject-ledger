export class ApiError extends Error {
  status: number
  body: any
  constructor(status: number, body: any) {
    super(typeof body === 'string' ? body : JSON.stringify(body))
    this.status = status
    this.body = body
  }
}

export async function api<T = any>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch('/api' + path, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  })
  if (!res.ok) {
    const text = await res.text()
    let body: any = text
    try { body = JSON.parse(text) } catch { /* 非 JSON 原样抛出 */ }
    throw new ApiError(res.status, body)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}
