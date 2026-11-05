import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)
const SESSION_KEY = 'cloudguard-session'
const TOKEN_KEY = 'cloudguard_jwt'

function readSession() {
  if (!localStorage.getItem(TOKEN_KEY)) return null
  try { return JSON.parse(localStorage.getItem(SESSION_KEY) || 'null') } catch { return null }
}

export function AuthProvider({ children }) {
  const [session, setSession] = useState(readSession)
  const user = session?.user || null
  const workspace = session?.workspace || null

  const login = useCallback(async credentials => {
    const response = await api.post('/api/auth/login', credentials)
    const auth = response.data?.data
    if (!auth?.access_token || !auth.user) throw new Error('The sign-in response was incomplete.')
    const next = { user: auth.user, workspace: auth.workspace || null }
    localStorage.setItem(TOKEN_KEY, auth.access_token)
    localStorage.setItem(SESSION_KEY, JSON.stringify(next))
    setSession(next)
    return auth
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(SESSION_KEY)
    setSession(null)
  }, [])

  const value = useMemo(() => ({
    user,
    workspace,
    workspaceId: workspace?.id || null,
    isAuthenticated: Boolean(user && localStorage.getItem(TOKEN_KEY)),
    login,
    logout,
  }), [user, workspace, login, logout])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used within AuthProvider')
  return value
}
