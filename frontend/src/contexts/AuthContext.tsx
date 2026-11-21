import { createContext, useContext, useState, type ReactNode } from 'react'
import { authAPI } from '../services/api'

interface User {
  worker_id: string
  name: string
  email?: string
  mobile_number?: string
  district?: string
  phc?: string
  language?: string
  role?: string
}

interface AuthContextType {
  user: User | null
  token: string | null
  login: (identifier: string, password: string) => Promise<void>
  signup: (data: { email: string; password: string; mobile_number: string; name?: string }) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextType>({} as AuthContextType)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(() => {
    const u = sessionStorage.getItem('asha_user')
    return u ? JSON.parse(u) : null
  })
  const [token, setToken] = useState<string | null>(() =>
    sessionStorage.getItem('asha_token')
  )

  async function login(identifier: string, password: string) {
    const res = await authAPI.login(identifier, password)
    const { token: t, user: u } = res.data
    sessionStorage.setItem('asha_token', t)
    sessionStorage.setItem('asha_user', JSON.stringify(u))
    setToken(t)
    setUser(u)
  }

  async function signup(data: { email: string; password: string; mobile_number: string; name?: string }) {
    const res = await authAPI.signup(data)
    const { token: t, user: u } = res.data
    sessionStorage.setItem('asha_token', t)
    sessionStorage.setItem('asha_user', JSON.stringify(u))
    setToken(t)
    setUser(u)
  }

  function logout() {
    authAPI.logout().catch(() => {})
    sessionStorage.removeItem('asha_token')
    sessionStorage.removeItem('asha_user')
    setToken(null)
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, token, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
