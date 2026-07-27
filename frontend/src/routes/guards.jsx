import React, { useEffect } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { getHomeRouteForRole } from '../utils/roles'

// These guards are UX-only conveniences. The backend independently
// re-checks role/membership on every request (see backend/app/auth/
// permissions.py) and is the actual security boundary — a guard here
// hiding a link or redirecting away is not what makes the app secure.

export const LoadingScreen = () => (
  <div className="flex items-center justify-center min-h-screen gradient-bg">
    <div className="text-center">
      <div className="w-16 h-16 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
      <p className="neon-text text-lg font-semibold">Loading InterviewIQ...</p>
    </div>
  </div>
)

// An authenticated user whose role isn't one of the five known values
// (should not happen — the backend only ever writes one of the five) is
// failed safely: logged out and sent to /login. Never defaults to /admin.
const UnknownRoleFailSafe = () => {
  const { logout } = useAuth()
  useEffect(() => {
    logout()
  }, [])
  return <Navigate to="/login" replace />
}

export const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, loading, user } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingScreen />
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />
  if (!getHomeRouteForRole(user?.role)) return <UnknownRoleFailSafe />

  return children
}

export const RoleRoute = ({ allowedRoles, children }) => {
  const { user, isAuthenticated, loading } = useAuth()
  const location = useLocation()

  if (loading) return <LoadingScreen />
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location }} />
  if (!getHomeRouteForRole(user?.role)) return <UnknownRoleFailSafe />
  if (!allowedRoles.includes(user.role)) return <Navigate to="/unauthorized" replace />

  return children
}

// For /login and /register: an already-authenticated user is sent to
// their role home instead of seeing the login/register form again.
export const PublicOnlyRoute = ({ children }) => {
  const { user, isAuthenticated, loading } = useAuth()

  if (loading) return <LoadingScreen />
  if (isAuthenticated) {
    const home = getHomeRouteForRole(user?.role)
    if (!home) return <UnknownRoleFailSafe />
    return <Navigate to={home} replace />
  }
  return children
}
