import React, { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Users, Search, X, Check, AlertCircle, ShieldAlert, UserCog } from 'lucide-react'
import { listAdminUsers, getAdminUser, updateAdminUserStatus, updateAdminUserRole } from '../api/adminUsers'

const ROLES = ['system_admin', 'student', 'company_admin', 'interviewer', 'candidate']
const PAGE_SIZE = 10

const roleBadge = (role) =>
  ({
    system_admin: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20',
    student: 'bg-blue-400/10 text-blue-400 border-blue-400/20',
    company_admin: 'bg-purple-400/10 text-purple-400 border-purple-400/20',
    interviewer: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    candidate: 'bg-green-400/10 text-green-400 border-green-400/20',
  }[role] || 'bg-gray-400/10 text-gray-400 border-gray-400/20')

const statusBadge = (active) =>
  active
    ? 'bg-green-400/10 text-green-400 border-green-400/20'
    : 'bg-red-400/10 text-red-400 border-red-400/20'

export default function AdminUsers() {
  const [users, setUsers] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('') // '', 'true', 'false'
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [detailUser, setDetailUser] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null) // {type, user, value, label}
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchUsers = useCallback(() => {
    setLoading(true)
    setError('')
    const params = { page, page_size: PAGE_SIZE }
    if (search.trim()) params.q = search.trim()
    if (roleFilter) params.role = roleFilter
    if (statusFilter) params.is_active = statusFilter
    listAdminUsers(params)
      .then(({ data }) => {
        setUsers(data.items)
        setTotal(data.total)
      })
      .catch(() => setError('Unable to load users right now.'))
      .finally(() => setLoading(false))
  }, [page, search, roleFilter, statusFilter])

  useEffect(() => {
    fetchUsers()
  }, [fetchUsers])

  // Reset to page 1 whenever a filter/search changes.
  useEffect(() => {
    setPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, roleFilter, statusFilter])

  const openDetail = (userId) => {
    setActionError('')
    setDetailLoading(true)
    setDetailUser(null)
    getAdminUser(userId)
      .then(({ data }) => setDetailUser(data))
      .catch(() => setActionError('Unable to load user detail.'))
      .finally(() => setDetailLoading(false))
  }

  const runConfirmedAction = async () => {
    if (!confirmAction) return
    setActionLoading(true)
    setActionError('')
    try {
      const { data } =
        confirmAction.type === 'status'
          ? await updateAdminUserStatus(confirmAction.user.id, confirmAction.value)
          : await updateAdminUserRole(confirmAction.user.id, confirmAction.value)
      setConfirmAction(null)
      setDetailUser(data)
      fetchUsers()
    } catch (e) {
      setActionError(e.response?.data?.detail || 'Action failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
            <Users size={20} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-3xl font-black">User Management</h1>
            <p className="text-gray-400 text-sm mt-0.5">
              {total} user{total !== 1 ? 's' : ''} total
            </p>
          </div>
        </motion.div>

        {/* Search & filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or email..."
              className="input-field pl-10"
            />
          </div>
          <select value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)} className="input-field sm:w-48">
            <option value="">All roles</option>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </select>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input-field sm:w-40">
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </div>

        {error && (
          <div className="glass-card p-4 mb-4 flex items-center gap-2 text-sm text-red-400">
            <AlertCircle size={16} /> {error}
          </div>
        )}

        {/* Table */}
        <div className="glass-card overflow-hidden">
          {loading ? (
            <div className="flex justify-center py-20">
              <div className="w-10 h-10 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : users.length === 0 ? (
            <div className="p-14 text-center text-gray-500">No users found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-gray-500 text-xs uppercase tracking-wide">
                    <th className="px-5 py-3 font-medium">Name</th>
                    <th className="px-5 py-3 font-medium">Email</th>
                    <th className="px-5 py-3 font-medium">Role</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Created</th>
                    <th className="px-5 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b border-white/5 last:border-0 hover:bg-white/3">
                      <td className="px-5 py-3 font-medium">{u.name}</td>
                      <td className="px-5 py-3 text-gray-400 truncate max-w-[220px]">{u.email}</td>
                      <td className="px-5 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${roleBadge(u.role)}`}>
                          {u.role}
                        </span>
                      </td>
                      <td className="px-5 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(u.is_active)}`}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-500 text-xs">
                        {new Date(u.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => openDetail(u.id)}
                          className="text-cyan-400 hover:text-cyan-300 text-xs font-medium"
                        >
                          Manage
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 mt-6">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="btn-secondary text-sm py-2 px-4 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-400">
              Page {page} of {totalPages}
            </span>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="btn-secondary text-sm py-2 px-4 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Detail modal */}
      <AnimatePresence>
        {(detailUser || detailLoading) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) {
                setDetailUser(null)
                setActionError('')
              }
            }}
          >
            <motion.div
              initial={{ scale: 0.92, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 20 }}
              className="glass-card p-7 w-full max-w-lg"
            >
              {detailLoading ? (
                <div className="flex justify-center py-10">
                  <div className="w-8 h-8 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                </div>
              ) : (
                detailUser && (
                  <>
                    <div className="flex items-center justify-between mb-6">
                      <h2 className="text-xl font-bold flex items-center gap-2">
                        <UserCog size={20} className="text-cyan-400" /> {detailUser.name}
                      </h2>
                      <button
                        onClick={() => {
                          setDetailUser(null)
                          setActionError('')
                        }}
                        className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white"
                      >
                        <X size={20} />
                      </button>
                    </div>

                    <div className="space-y-3 text-sm mb-6">
                      <div className="flex justify-between">
                        <span className="text-gray-500">Email</span>
                        <span>{detailUser.email}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Role</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${roleBadge(detailUser.role)}`}>
                          {detailUser.role}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Status</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${statusBadge(detailUser.is_active)}`}>
                          {detailUser.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-500">Created</span>
                        <span>{new Date(detailUser.created_at).toLocaleString()}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 block mb-1.5">Organization memberships</span>
                        {detailUser.memberships.length === 0 ? (
                          <p className="text-gray-600 text-xs">No organization memberships.</p>
                        ) : (
                          <div className="space-y-1.5">
                            {detailUser.memberships.map((m, i) => (
                              <div
                                key={i}
                                className="flex justify-between text-xs bg-white/3 border border-white/5 rounded-lg px-3 py-1.5"
                              >
                                <span>
                                  Org #{m.organization_id} · {m.membership_role}
                                </span>
                                <span className={m.is_active ? 'text-green-400' : 'text-red-400'}>
                                  {m.is_active ? 'active' : 'inactive'}
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {actionError && (
                      <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                        <ShieldAlert size={15} className="flex-shrink-0" /> {actionError}
                      </div>
                    )}

                    <div className="space-y-3">
                      <div>
                        <label className="block text-xs text-gray-500 mb-1.5">Change global role</label>
                        <select
                          value={detailUser.role}
                          onChange={(e) => {
                            setActionError('')
                            setConfirmAction({
                              type: 'role',
                              user: detailUser,
                              value: e.target.value,
                              label: `Change ${detailUser.name}'s role from ${detailUser.role} to ${e.target.value}?`,
                            })
                          }}
                          className="input-field w-full"
                        >
                          {ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </div>

                      <button
                        onClick={() => {
                          setActionError('')
                          setConfirmAction({
                            type: 'status',
                            user: detailUser,
                            value: !detailUser.is_active,
                            label: detailUser.is_active
                              ? `Suspend ${detailUser.name}? They will be logged out immediately and unable to log back in until reactivated.`
                              : `Reactivate ${detailUser.name}?`,
                          })
                        }}
                        className={detailUser.is_active ? 'btn-danger w-full py-2.5 text-sm' : 'btn-primary w-full py-2.5 text-sm'}
                      >
                        {detailUser.is_active ? 'Suspend account' : 'Reactivate account'}
                      </button>
                    </div>
                  </>
                )
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Confirmation modal */}
      <AnimatePresence>
        {confirmAction && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget && !actionLoading) setConfirmAction(null)
            }}
          >
            <motion.div
              initial={{ scale: 0.92 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.92 }}
              className="glass-card p-8 w-full max-w-sm text-center"
            >
              <div className="w-14 h-14 rounded-full bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center mx-auto mb-4">
                <ShieldAlert size={24} className="text-yellow-400" />
              </div>
              <h3 className="text-lg font-bold mb-2">Confirm action</h3>
              <p className="text-gray-400 text-sm mb-7">{confirmAction.label}</p>
              <div className="flex gap-3">
                <button
                  disabled={actionLoading}
                  onClick={() => setConfirmAction(null)}
                  className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  disabled={actionLoading}
                  onClick={runConfirmedAction}
                  className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {actionLoading ? (
                    <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Check size={16} />
                  )}
                  Confirm
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
