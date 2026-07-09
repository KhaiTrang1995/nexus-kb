const TOKEN_KEY = 'nexus-jwt'
const USER_KEY = 'nexus-current-user'

export interface NexusUser {
  id: string
  name: string
  role: string
  is_admin?: boolean
  workspace_ids?: string[]
}

interface TokenResponse {
  access_token: string
  token_type: string
  user: NexusUser
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getSavedUser(): NexusUser | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as NexusUser
  } catch {
    return null
  }
}

export function saveUser(user: NexusUser): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

// For multipart/form-data requests (file upload): the browser must set its
// own Content-Type with the multipart boundary, so it must NOT be set here.
export function authHeadersForUpload(): Record<string, string> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }
  return headers
}

export async function loginDev(
  userId: string,
  name: string,
  role: string,
  isAdmin = false,
  workspaceIds: string[] = [],
): Promise<NexusUser> {
  const res = await fetch('/api/v1/auth/dev-token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      name,
      role,
      is_admin: isAdmin,
      workspace_ids: workspaceIds,
    }),
  })
  if (!res.ok) {
    throw new Error(`Login failed: HTTP ${res.status}`)
  }
  const data: TokenResponse = await res.json()
  setToken(data.access_token)
  saveUser(data.user)
  return data.user
}
