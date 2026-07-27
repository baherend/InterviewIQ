import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Shield, Users, Building2, FileQuestion, ClipboardList, Activity,
  ChevronRight, Clock, AlertCircle,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { listOrganizations } from '../api/organizations'

const statusBadge = (status) =>
  ({
    active: 'bg-green-400/10 text-green-400 border-green-400/20',
    pending: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    suspended: 'bg-red-400/10 text-red-400 border-red-400/20',
  }[status] || 'bg-gray-400/10 text-gray-400 border-gray-400/20')

const ComingSoonCard = ({ icon, title, note }) => (
  <div className="glass-card p-6">
    <div className="flex items-center gap-2 mb-2">
      {icon}
      <h3 className="text-lg font-bold">{title}</h3>
      <span className="text-xs bg-white/5 border border-white/10 text-gray-400 px-2 py-0.5 rounded-full ml-auto">
        Coming soon
      </span>
    </div>
    <p className="text-gray-400 text-sm leading-relaxed">{note}</p>
  </div>
)

export default function AdminDashboard() {
  const { user } = useAuth()
  const [orgState, setOrgState] = useState('loading') // loading | error | ready
  const [organizations, setOrganizations] = useState([])
  const [orgTotal, setOrgTotal] = useState(0)

  useEffect(() => {
    let cancelled = false
    // system_admin (this page is system_admin-only) gets the paginated
    // {items, total, ...} shape from this endpoint — see
    // backend/app/routers/organizations.py and frontend/src/api/organizations.js.
    listOrganizations({ page: 1, page_size: 5 })
      .then(({ data }) => {
        if (!cancelled) {
          setOrganizations(data.items || [])
          setOrgTotal(data.total ?? 0)
          setOrgState('ready')
        }
      })
      .catch(() => {
        if (!cancelled) setOrgState('error')
      })
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
            <Shield size={20} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-3xl font-black">System Admin</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              Signed in as {user?.name} · platform-wide access
            </p>
          </div>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-5 mb-6">
          {/* Organizations — real data */}
          <div className="glass-card p-6">
            <div className="flex items-center gap-2 mb-4">
              <Building2 size={20} className="text-cyan-400" />
              <h3 className="text-lg font-bold">Organizations</h3>
              <Link
                to="/admin/organizations"
                className="text-xs text-cyan-400 hover:text-cyan-300 ml-auto flex items-center gap-1"
              >
                View all <ChevronRight size={12} />
              </Link>
            </div>
            {orgState === 'loading' && (
              <div className="flex justify-center py-6">
                <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            {orgState === 'error' && (
              <div className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle size={16} /> Unable to load organizations right now.
              </div>
            )}
            {orgState === 'ready' && (
              <>
                <p className="text-3xl font-black text-white mb-4">{orgTotal}</p>
                {organizations.length === 0 ? (
                  <p className="text-gray-500 text-sm">No organizations have been created yet.</p>
                ) : (
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {organizations.map((org) => (
                      <div
                        key={org.id}
                        className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/3 border border-white/5 text-sm"
                      >
                        <span className="truncate">{org.name}</span>
                        <span
                          className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize ml-2 flex-shrink-0 ${statusBadge(org.status)}`}
                        >
                          {org.status}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-xs text-gray-600 mt-4">
                  Create, approve, suspend, and edit organizations from the full management page.
                </p>
              </>
            )}
          </div>

          {/* Platform question bank — real link */}
          <Link
            to="/admin/questions"
            className="glass-card p-6 hover:border-cyan-400/30 transition-all group flex flex-col"
          >
            <div className="flex items-center gap-2 mb-2">
              <FileQuestion size={20} className="text-cyan-400" />
              <h3 className="text-lg font-bold">Platform Question Bank</h3>
              <ChevronRight
                size={18}
                className="ml-auto text-gray-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all"
              />
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              Manage the global technical, HR, and leadership question bank used by all students.
            </p>
          </Link>

          {/* User management — real link (Phase 2A) */}
          <Link
            to="/admin/users"
            className="glass-card p-6 hover:border-cyan-400/30 transition-all group flex flex-col"
          >
            <div className="flex items-center gap-2 mb-2">
              <Users size={20} className="text-cyan-400" />
              <h3 className="text-lg font-bold">User Management</h3>
              <ChevronRight
                size={18}
                className="ml-auto text-gray-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all"
              />
            </div>
            <p className="text-gray-400 text-sm leading-relaxed">
              List, search, activate/suspend, and change the global role of any platform user.
            </p>
          </Link>
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          <ComingSoonCard
            icon={<ClipboardList size={20} className="text-cyan-400" />}
            title="Assessments / Sessions"
            note="Cross-user visibility into interview sessions and assessment activity."
          />
          <ComingSoonCard
            icon={<Activity size={20} className="text-cyan-400" />}
            title="Service Health"
            note="Live backend/database health indicators for this admin area."
          />
          <ComingSoonCard
            icon={<Clock size={20} className="text-cyan-400" />}
            title="Storage & Logs"
            note="Upload storage usage and application logs."
          />
        </div>
      </div>
    </div>
  )
}
