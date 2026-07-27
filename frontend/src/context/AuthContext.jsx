import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../api/axios'

const AuthContext = createContext(null)

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('token'))
  const [loading, setLoading] = useState(true)

  // Re-fetches the authoritative current user from the database via
  // /auth/me. Used both on mount and as an exposed manual refresh. Never
  // trusts localStorage as the final answer — it's only an optimistic
  // placeholder until this resolves.
  const refreshUser = useCallback(async () => {
    try {
      const { data } = await api.get('/auth/me')
      setUser(data)
      localStorage.setItem('user', JSON.stringify(data))
      return data
    } catch (err) {
      // Invalid/expired token or network failure: do not grant access on
      // a failure. The axios response interceptor already clears storage
      // and redirects to /login on a genuine 401; other failures (e.g.
      // network) are surfaced to the caller instead of silently
      // pretending the user is authenticated.
      throw err
    }
  }, [])

  useEffect(() => {
    if (!token) {
      setLoading(false)
      return
    }

    const storedUser = localStorage.getItem('user')
    if (storedUser) {
      // Optimistic restore so the UI has something to render immediately;
      // refreshUser() below replaces it with the authoritative DB record.
      setUser(JSON.parse(storedUser))
    }
    api.defaults.headers.common['Authorization'] = `Bearer ${token}`

    refreshUser()
      .catch(() => {})
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const login = (accessToken, userData) => {
    localStorage.setItem('token', accessToken)
    localStorage.setItem('user', JSON.stringify(userData))
    api.defaults.headers.common['Authorization'] = `Bearer ${accessToken}`
    setToken(accessToken)
    setUser(userData)
  }

  const register = async (payload) => {
    const { data } = await api.post('/auth/register', payload)
    login(data.access_token, data.user)
    return data.user
  }

  const logout = () => {
    localStorage.removeItem('token')
    localStorage.removeItem('user')
    delete api.defaults.headers.common['Authorization']
    setToken(null)
    setUser(null)
  }

  const isAuthenticated = Boolean(user)

  return (
    <AuthContext.Provider
      value={{ user, token, loading, isAuthenticated, login, register, logout, refreshUser }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
