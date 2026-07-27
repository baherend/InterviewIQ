import React from 'react'
import { Link } from 'react-router-dom'
import { ShieldAlert } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getHomeRouteForRole } from '../utils/roles'

export default function Unauthorized() {
  const { user } = useAuth()
  const home = getHomeRouteForRole(user?.role) || '/login'

  return (
    <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
      <div className="glass-card p-10 max-w-md text-center">
        <ShieldAlert size={44} className="text-yellow-400 mx-auto mb-4" />
        <h2 className="text-xl font-bold mb-3">You don't have access to this page</h2>
        <p className="text-gray-400 text-sm mb-6 leading-relaxed">
          Your account doesn't have permission to view that area. If you think this is a
          mistake, contact your administrator.
        </p>
        <Link to={home} className="btn-primary inline-flex items-center justify-center">
          Go to my dashboard
        </Link>
      </div>
    </div>
  )
}
