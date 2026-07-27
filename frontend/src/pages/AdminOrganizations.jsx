import React, { useEffect, useState, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Building2, Search, X, Check, AlertCircle, ShieldAlert, Plus, Pencil,
  Users, UserPlus, UserMinus, Crown, Trash2, Mail, Send, Copy, Ban, Clock,
} from 'lucide-react'
import {
  listOrganizations,
  getOrganization,
  createOrganization,
  updateOrganization,
  updateOrganizationStatus,
  getOrganizationMembers,
  addOrganizationMember,
  updateMembershipRole,
  updateMembershipStatus,
  removeOrganizationMember,
} from '../api/organizations'
import { listInvitations, createInvitation, revokeInvitation } from '../api/invitations'
import { listAdminUsers } from '../api/adminUsers'

const ASSIGNABLE_MEMBERSHIP_ROLES = ['admin', 'interviewer', 'candidate']
const MEMBER_PAGE_SIZE = 10
const INVITATION_STATUSES = ['pending', 'accepted', 'revoked', 'expired']
const INVITATION_PAGE_SIZE = 10

const invitationStatusBadge = (status) =>
  ({
    pending: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    accepted: 'bg-green-400/10 text-green-400 border-green-400/20',
    revoked: 'bg-red-400/10 text-red-400 border-red-400/20',
    expired: 'bg-gray-400/10 text-gray-500 border-gray-400/20',
  }[status] || 'bg-gray-400/10 text-gray-400 border-gray-400/20')

const STATUSES = ['pending', 'active', 'suspended']
const PAGE_SIZE = 10

const statusBadge = (status) =>
  ({
    active: 'bg-green-400/10 text-green-400 border-green-400/20',
    pending: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    suspended: 'bg-red-400/10 text-red-400 border-red-400/20',
  }[status] || 'bg-gray-400/10 text-gray-400 border-gray-400/20')

// Next allowed statuses for a given current status — mirrors the backend
// transition policy (backend/app/routers/organizations.py) exactly, purely
// for UI convenience (only offering buttons for transitions that will
// actually succeed). The backend independently enforces this regardless.
const NEXT_STATUSES = {
  pending: ['active', 'suspended'],
  active: ['suspended'],
  suspended: ['active'],
}

const EMPTY_CREATE_FORM = { name: '', slug: '', description: '', owner_user_id: null }

export default function AdminOrganizations() {
  const [organizations, setOrganizations] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const [detailOrg, setDetailOrg] = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editForm, setEditForm] = useState({ name: '', slug: '', description: '' })
  const [actionLoading, setActionLoading] = useState(false)
  const [actionError, setActionError] = useState('')

  const [confirmAction, setConfirmAction] = useState(null) // {type, org, value, label}

  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState(EMPTY_CREATE_FORM)
  const [createError, setCreateError] = useState('')
  const [creating, setCreating] = useState(false)
  const [ownerSearch, setOwnerSearch] = useState('')
  const [ownerResults, setOwnerResults] = useState([])
  const [ownerSearchLoading, setOwnerSearchLoading] = useState(false)
  const [selectedOwner, setSelectedOwner] = useState(null)

  // Members section (Phase 2C) — lives inside the organization detail modal.
  const [members, setMembers] = useState([])
  const [membersTotal, setMembersTotal] = useState(0)
  const [membersPage, setMembersPage] = useState(1)
  const [membersLoading, setMembersLoading] = useState(false)
  const [membersError, setMembersError] = useState('')
  const [memberSearch, setMemberSearch] = useState('')
  const [memberRoleFilter, setMemberRoleFilter] = useState('')
  const [memberRowBusyId, setMemberRowBusyId] = useState(null)
  const [memberRowError, setMemberRowError] = useState('')
  const [confirmRemoveMember, setConfirmRemoveMember] = useState(null) // membership item

  const [addMemberOpen, setAddMemberOpen] = useState(false)
  const [addMemberSearch, setAddMemberSearch] = useState('')
  const [addMemberResults, setAddMemberResults] = useState([])
  const [addMemberSearchLoading, setAddMemberSearchLoading] = useState(false)
  const [addMemberSelectedUser, setAddMemberSelectedUser] = useState(null)
  const [addMemberRole, setAddMemberRole] = useState('interviewer')
  const [addMemberError, setAddMemberError] = useState('')
  const [addMemberLoading, setAddMemberLoading] = useState(false)

  // Invitations section (Phase 2D) — lives inside the same detail modal.
  const [invitations, setInvitations] = useState([])
  const [invitationsTotal, setInvitationsTotal] = useState(0)
  const [invitationsPage, setInvitationsPage] = useState(1)
  const [invitationsLoading, setInvitationsLoading] = useState(false)
  const [invitationsError, setInvitationsError] = useState('')
  const [invitationSearch, setInvitationSearch] = useState('')
  const [invitationStatusFilter, setInvitationStatusFilter] = useState('')
  const [inviteRowBusyId, setInviteRowBusyId] = useState(null)
  const [inviteRowError, setInviteRowError] = useState('')

  const [createInviteOpen, setCreateInviteOpen] = useState(false)
  const [createInviteEmail, setCreateInviteEmail] = useState('')
  const [createInviteRole, setCreateInviteRole] = useState('interviewer')
  const [createInviteError, setCreateInviteError] = useState('')
  const [createInviteLoading, setCreateInviteLoading] = useState(false)
  const [justCreatedInvite, setJustCreatedInvite] = useState(null) // {accept_url, email, membership_role}
  const [copyFeedback, setCopyFeedback] = useState(false)

  const invitationsTotalPages = Math.max(1, Math.ceil(invitationsTotal / INVITATION_PAGE_SIZE))

  const membersTotalPages = Math.max(1, Math.ceil(membersTotal / MEMBER_PAGE_SIZE))

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const fetchOrganizations = useCallback(() => {
    setLoading(true)
    setError('')
    const params = { page, page_size: PAGE_SIZE }
    if (search.trim()) params.q = search.trim()
    if (statusFilter) params.status = statusFilter
    listOrganizations(params)
      .then(({ data }) => {
        // system_admin always gets the paginated {items, total, ...} shape.
        setOrganizations(data.items || [])
        setTotal(data.total ?? 0)
      })
      .catch(() => setError('Unable to load organizations right now.'))
      .finally(() => setLoading(false))
  }, [page, search, statusFilter])

  useEffect(() => {
    fetchOrganizations()
  }, [fetchOrganizations])

  useEffect(() => {
    setPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter])

  // Owner search for the create form (reuses the existing admin users
  // endpoint — no new public user-search endpoint is created). Only
  // active users are offered.
  useEffect(() => {
    if (!createOpen) return
    setOwnerSearchLoading(true)
    const handle = setTimeout(() => {
      listAdminUsers({ q: ownerSearch || undefined, is_active: true, page_size: 8 })
        .then(({ data }) => setOwnerResults(data.items))
        .catch(() => setOwnerResults([]))
        .finally(() => setOwnerSearchLoading(false))
    }, 250)
    return () => clearTimeout(handle)
  }, [ownerSearch, createOpen])

  const fetchMembers = useCallback(
    (organizationId) => {
      if (!organizationId) return
      setMembersLoading(true)
      setMembersError('')
      const params = { page: membersPage, page_size: MEMBER_PAGE_SIZE }
      if (memberSearch.trim()) params.q = memberSearch.trim()
      if (memberRoleFilter) params.membership_role = memberRoleFilter
      getOrganizationMembers(organizationId, params)
        .then(({ data }) => {
          setMembers(data.items || [])
          setMembersTotal(data.total ?? 0)
        })
        .catch(() => setMembersError('Unable to load members right now.'))
        .finally(() => setMembersLoading(false))
    },
    [membersPage, memberSearch, memberRoleFilter]
  )

  useEffect(() => {
    if (detailOrg) fetchMembers(detailOrg.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailOrg?.id, membersPage, memberSearch, memberRoleFilter])

  useEffect(() => {
    setMembersPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [memberSearch, memberRoleFilter, detailOrg?.id])

  // Owner-only user search for the add-member picker (reuses the same
  // admin users endpoint as the create-organization owner search — no new
  // user-directory endpoint is created).
  useEffect(() => {
    if (!addMemberOpen) return
    setAddMemberSearchLoading(true)
    const handle = setTimeout(() => {
      listAdminUsers({ q: addMemberSearch || undefined, is_active: true, page_size: 8 })
        .then(({ data }) => setAddMemberResults(data.items))
        .catch(() => setAddMemberResults([]))
        .finally(() => setAddMemberSearchLoading(false))
    }, 250)
    return () => clearTimeout(handle)
  }, [addMemberSearch, addMemberOpen])

  const fetchInvitations = useCallback(
    (organizationId) => {
      if (!organizationId) return
      setInvitationsLoading(true)
      setInvitationsError('')
      const params = { page: invitationsPage, page_size: INVITATION_PAGE_SIZE }
      if (invitationSearch.trim()) params.q = invitationSearch.trim()
      if (invitationStatusFilter) params.status = invitationStatusFilter
      listInvitations(organizationId, params)
        .then(({ data }) => {
          setInvitations(data.items || [])
          setInvitationsTotal(data.total ?? 0)
        })
        .catch(() => setInvitationsError('Unable to load invitations right now.'))
        .finally(() => setInvitationsLoading(false))
    },
    [invitationsPage, invitationSearch, invitationStatusFilter]
  )

  useEffect(() => {
    if (detailOrg) fetchInvitations(detailOrg.id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detailOrg?.id, invitationsPage, invitationSearch, invitationStatusFilter])

  useEffect(() => {
    setInvitationsPage(1)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [invitationSearch, invitationStatusFilter, detailOrg?.id])

  const openCreateInvite = () => {
    setCreateInviteEmail('')
    setCreateInviteRole('interviewer')
    setCreateInviteError('')
    setJustCreatedInvite(null)
    setCopyFeedback(false)
    setCreateInviteOpen(true)
  }

  const submitCreateInvite = async (e) => {
    e.preventDefault()
    if (!detailOrg || !createInviteEmail.trim()) return
    setCreateInviteLoading(true)
    setCreateInviteError('')
    try {
      const { data } = await createInvitation(detailOrg.id, {
        email: createInviteEmail.trim(),
        membership_role: createInviteRole,
      })
      setJustCreatedInvite(data)
      fetchInvitations(detailOrg.id)
    } catch (e) {
      setCreateInviteError(e.response?.data?.detail || 'Could not create invitation. Please try again.')
    } finally {
      setCreateInviteLoading(false)
    }
  }

  const copyInviteUrl = async () => {
    if (!justCreatedInvite?.accept_url) return
    try {
      await navigator.clipboard.writeText(justCreatedInvite.accept_url)
      setCopyFeedback(true)
      setTimeout(() => setCopyFeedback(false), 2000)
    } catch {
      // Clipboard API unavailable/denied — the URL is still visible and
      // selectable in the input below, so this is a soft failure only.
    }
  }

  const handleRevokeInvite = async (invitation) => {
    if (!detailOrg) return
    setInviteRowBusyId(invitation.id)
    setInviteRowError('')
    try {
      await revokeInvitation(detailOrg.id, invitation.id)
      fetchInvitations(detailOrg.id)
    } catch (e) {
      setInviteRowError(e.response?.data?.detail || 'Could not revoke invitation. Please try again.')
    } finally {
      setInviteRowBusyId(null)
    }
  }

  const openDetail = (organizationId) => {
    setActionError('')
    setEditMode(false)
    setDetailLoading(true)
    setDetailOrg(null)
    setMembers([])
    setMembersTotal(0)
    setMembersPage(1)
    setMemberSearch('')
    setMemberRoleFilter('')
    setMemberRowError('')
    setInvitations([])
    setInvitationsTotal(0)
    setInvitationsPage(1)
    setInvitationSearch('')
    setInvitationStatusFilter('')
    setInviteRowError('')
    getOrganization(organizationId)
      .then(({ data }) => {
        setDetailOrg(data)
        setEditForm({ name: data.name, slug: data.slug, description: data.description || '' })
      })
      .catch(() => setActionError('Unable to load organization detail.'))
      .finally(() => setDetailLoading(false))
  }

  const closeDetail = () => {
    setDetailOrg(null)
    setEditMode(false)
    setActionError('')
    setAddMemberOpen(false)
    setCreateInviteOpen(false)
  }

  const openAddMember = () => {
    setAddMemberSearch('')
    setAddMemberResults([])
    setAddMemberSelectedUser(null)
    setAddMemberRole('interviewer')
    setAddMemberError('')
    setAddMemberOpen(true)
  }

  const submitAddMember = async () => {
    if (!detailOrg || !addMemberSelectedUser) return
    setAddMemberLoading(true)
    setAddMemberError('')
    try {
      await addOrganizationMember(detailOrg.id, {
        user_id: addMemberSelectedUser.id,
        membership_role: addMemberRole,
      })
      setAddMemberOpen(false)
      fetchMembers(detailOrg.id)
      fetchOrganizations()
    } catch (e) {
      setAddMemberError(e.response?.data?.detail || 'Could not add member. Please try again.')
    } finally {
      setAddMemberLoading(false)
    }
  }

  const changeMemberRole = async (membership, newRole) => {
    if (!detailOrg || newRole === membership.membership_role) return
    setMemberRowBusyId(membership.id)
    setMemberRowError('')
    try {
      await updateMembershipRole(detailOrg.id, membership.id, newRole)
      fetchMembers(detailOrg.id)
    } catch (e) {
      setMemberRowError(e.response?.data?.detail || 'Could not change role. Please try again.')
    } finally {
      setMemberRowBusyId(null)
    }
  }

  const toggleMemberStatus = async (membership) => {
    if (!detailOrg) return
    setMemberRowBusyId(membership.id)
    setMemberRowError('')
    try {
      await updateMembershipStatus(detailOrg.id, membership.id, !membership.is_active)
      fetchMembers(detailOrg.id)
    } catch (e) {
      setMemberRowError(e.response?.data?.detail || 'Could not update status. Please try again.')
    } finally {
      setMemberRowBusyId(null)
    }
  }

  const runConfirmedRemoveMember = async () => {
    if (!detailOrg || !confirmRemoveMember) return
    setMemberRowBusyId(confirmRemoveMember.id)
    setMemberRowError('')
    try {
      await removeOrganizationMember(detailOrg.id, confirmRemoveMember.id)
      setConfirmRemoveMember(null)
      fetchMembers(detailOrg.id)
      fetchOrganizations()
    } catch (e) {
      setMemberRowError(e.response?.data?.detail || 'Could not remove member. Please try again.')
      setConfirmRemoveMember(null)
    } finally {
      setMemberRowBusyId(null)
    }
  }

  const saveEdit = async () => {
    if (!detailOrg) return
    setActionLoading(true)
    setActionError('')
    try {
      const { data } = await updateOrganization(detailOrg.id, {
        name: editForm.name,
        slug: editForm.slug,
        description: editForm.description || null,
      })
      setDetailOrg({ ...detailOrg, ...data })
      setEditMode(false)
      fetchOrganizations()
    } catch (e) {
      setActionError(e.response?.data?.detail || 'Update failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const runConfirmedStatusChange = async () => {
    if (!confirmAction) return
    setActionLoading(true)
    setActionError('')
    try {
      const { data } = await updateOrganizationStatus(confirmAction.org.id, confirmAction.value)
      setConfirmAction(null)
      setDetailOrg((prev) => (prev && prev.id === data.id ? { ...prev, ...data } : prev))
      fetchOrganizations()
    } catch (e) {
      setActionError(e.response?.data?.detail || 'Status change failed. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const openCreate = () => {
    setCreateForm(EMPTY_CREATE_FORM)
    setSelectedOwner(null)
    setOwnerSearch('')
    setCreateError('')
    setCreateOpen(true)
  }

  const submitCreate = async () => {
    if (!createForm.name.trim() || !selectedOwner) return
    setCreating(true)
    setCreateError('')
    try {
      await createOrganization({
        name: createForm.name.trim(),
        slug: createForm.slug.trim() || undefined,
        description: createForm.description.trim() || null,
        owner_user_id: selectedOwner.id,
      })
      setCreateOpen(false)
      fetchOrganizations()
    } catch (e) {
      setCreateError(e.response?.data?.detail || 'Could not create organization. Please try again.')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8"
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
              <Building2 size={20} className="text-cyan-400" />
            </div>
            <div>
              <h1 className="text-3xl font-black">Organizations</h1>
              <p className="text-gray-400 text-sm mt-0.5">
                {total} organization{total !== 1 ? 's' : ''} total
              </p>
            </div>
          </div>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2 text-sm py-2.5 px-5 shrink-0">
            <Plus size={16} /> New Organization
          </button>
        </motion.div>

        {/* Search & filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or slug..."
              className="input-field pl-10"
            />
          </div>
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="input-field sm:w-48">
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
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
          ) : organizations.length === 0 ? (
            <div className="p-14 text-center text-gray-500">No organizations found.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/5 text-left text-gray-500 text-xs uppercase tracking-wide">
                    <th className="px-5 py-3 font-medium">Name</th>
                    <th className="px-5 py-3 font-medium">Slug</th>
                    <th className="px-5 py-3 font-medium">Status</th>
                    <th className="px-5 py-3 font-medium">Owner</th>
                    <th className="px-5 py-3 font-medium">Members</th>
                    <th className="px-5 py-3 font-medium">Created</th>
                    <th className="px-5 py-3 font-medium text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {organizations.map((org) => (
                    <tr key={org.id} className="border-b border-white/5 last:border-0 hover:bg-white/3">
                      <td className="px-5 py-3 font-medium truncate max-w-[200px]">{org.name}</td>
                      <td className="px-5 py-3 text-gray-400 text-xs">{org.slug}</td>
                      <td className="px-5 py-3">
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${statusBadge(org.status)}`}>
                          {org.status}
                        </span>
                      </td>
                      <td className="px-5 py-3 text-gray-400 text-xs truncate max-w-[180px]">
                        {org.owner ? org.owner.name : '—'}
                      </td>
                      <td className="px-5 py-3 text-gray-400 text-xs">{org.member_count}</td>
                      <td className="px-5 py-3 text-gray-500 text-xs">
                        {new Date(org.created_at).toLocaleDateString()}
                      </td>
                      <td className="px-5 py-3 text-right">
                        <button
                          onClick={() => openDetail(org.id)}
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

      {/* Detail / edit modal */}
      <AnimatePresence>
        {(detailOrg || detailLoading) && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget) closeDetail()
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
                detailOrg && (
                  <>
                    <div className="flex items-center justify-between mb-6">
                      <h2 className="text-xl font-bold flex items-center gap-2">
                        <Building2 size={20} className="text-cyan-400" /> {detailOrg.name}
                      </h2>
                      <button onClick={closeDetail} className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white">
                        <X size={20} />
                      </button>
                    </div>

                    {actionError && (
                      <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                        <ShieldAlert size={15} className="flex-shrink-0" /> {actionError}
                      </div>
                    )}

                    {editMode ? (
                      <div className="space-y-4 mb-6">
                        <div>
                          <label className="block text-xs text-gray-500 mb-1.5">Name</label>
                          <input
                            value={editForm.name}
                            onChange={(e) => setEditForm((f) => ({ ...f, name: e.target.value }))}
                            className="input-field w-full"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1.5">Slug</label>
                          <input
                            value={editForm.slug}
                            onChange={(e) => setEditForm((f) => ({ ...f, slug: e.target.value }))}
                            className="input-field w-full"
                          />
                        </div>
                        <div>
                          <label className="block text-xs text-gray-500 mb-1.5">Description</label>
                          <textarea
                            value={editForm.description}
                            onChange={(e) => setEditForm((f) => ({ ...f, description: e.target.value }))}
                            rows={3}
                            className="input-field w-full resize-none"
                          />
                        </div>
                        <div className="flex gap-3">
                          <button
                            disabled={actionLoading}
                            onClick={() => setEditMode(false)}
                            className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                          >
                            Cancel
                          </button>
                          <button
                            disabled={actionLoading || !editForm.name.trim()}
                            onClick={saveEdit}
                            className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                          >
                            {actionLoading ? (
                              <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                            ) : (
                              <Check size={16} />
                            )}
                            Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-3 text-sm mb-6">
                        <div className="flex justify-between">
                          <span className="text-gray-500">Slug</span>
                          <span>{detailOrg.slug}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Status</span>
                          <span className={`text-xs px-2 py-0.5 rounded-full border font-medium capitalize ${statusBadge(detailOrg.status)}`}>
                            {detailOrg.status}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Owner</span>
                          <span className="text-right">
                            {detailOrg.owner ? `${detailOrg.owner.name} (${detailOrg.owner.email})` : '—'}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Members</span>
                          <span>{detailOrg.member_count}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-500">Created</span>
                          <span>{new Date(detailOrg.created_at).toLocaleString()}</span>
                        </div>
                        {detailOrg.description && (
                          <div>
                            <span className="text-gray-500 block mb-1">Description</span>
                            <p className="text-gray-300 text-xs leading-relaxed">{detailOrg.description}</p>
                          </div>
                        )}
                      </div>
                    )}

                    {!editMode && (
                      <div className="space-y-3">
                        <button onClick={() => setEditMode(true)} className="btn-secondary w-full py-2.5 text-sm flex items-center justify-center gap-2">
                          <Pencil size={14} /> Edit name / slug / description
                        </button>

                        {(NEXT_STATUSES[detailOrg.status] || []).map((nextStatus) => (
                          <button
                            key={nextStatus}
                            onClick={() =>
                              setConfirmAction({
                                type: 'status',
                                org: detailOrg,
                                value: nextStatus,
                                label:
                                  nextStatus === 'suspended'
                                    ? `Suspend "${detailOrg.name}"? Members will lose access until it is reactivated.`
                                    : nextStatus === 'active'
                                    ? `${detailOrg.status === 'pending' ? 'Approve' : 'Reactivate'} "${detailOrg.name}"?`
                                    : `Change "${detailOrg.name}" to ${nextStatus}?`,
                              })
                            }
                            className={nextStatus === 'suspended' ? 'btn-danger w-full py-2.5 text-sm' : 'btn-primary w-full py-2.5 text-sm'}
                          >
                            {nextStatus === 'suspended'
                              ? 'Suspend organization'
                              : detailOrg.status === 'pending'
                              ? 'Approve organization'
                              : 'Reactivate organization'}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Members (Phase 2C) */}
                    <div className="mt-7 pt-6 border-t border-white/10">
                      <div className="flex items-center gap-2 mb-3">
                        <Users size={16} className="text-cyan-400" />
                        <h3 className="text-sm font-bold">Members</h3>
                        <span className="text-xs text-gray-500">({membersTotal})</span>
                        <button
                          onClick={openAddMember}
                          className="ml-auto flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-medium"
                        >
                          <UserPlus size={13} /> Add
                        </button>
                      </div>

                      <div className="flex gap-2 mb-3">
                        <div className="relative flex-1">
                          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                          <input
                            value={memberSearch}
                            onChange={(e) => setMemberSearch(e.target.value)}
                            placeholder="Search members..."
                            className="input-field pl-7 text-xs py-1.5"
                          />
                        </div>
                        <select
                          value={memberRoleFilter}
                          onChange={(e) => setMemberRoleFilter(e.target.value)}
                          className="input-field text-xs py-1.5 w-32"
                        >
                          <option value="">All roles</option>
                          <option value="owner">Owner</option>
                          {ASSIGNABLE_MEMBERSHIP_ROLES.map((r) => (
                            <option key={r} value={r}>
                              {r}
                            </option>
                          ))}
                        </select>
                      </div>

                      {memberRowError && (
                        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-3">
                          <ShieldAlert size={13} className="flex-shrink-0" /> {memberRowError}
                        </div>
                      )}

                      {membersError && (
                        <div className="flex items-center gap-2 text-xs text-red-400 mb-3">
                          <AlertCircle size={13} /> {membersError}
                        </div>
                      )}

                      {membersLoading ? (
                        <div className="flex justify-center py-6">
                          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                        </div>
                      ) : members.length === 0 ? (
                        <p className="text-xs text-gray-600 text-center py-4">No members found.</p>
                      ) : (
                        <div className="space-y-1.5 max-h-64 overflow-y-auto">
                          {members.map((m) => (
                            <div
                              key={m.id}
                              className="flex items-center justify-between gap-2 bg-white/3 border border-white/5 rounded-lg px-3 py-2"
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-medium truncate flex items-center gap-1">
                                  {m.membership_role === 'owner' && <Crown size={11} className="text-yellow-400 flex-shrink-0" />}
                                  {m.user.name}
                                </p>
                                <p className="text-[11px] text-gray-500 truncate">{m.user.email}</p>
                              </div>
                              <div className="flex items-center gap-1.5 flex-shrink-0">
                                <span
                                  className={`text-[10px] px-1.5 py-0.5 rounded-full border ${
                                    m.is_active
                                      ? 'bg-green-400/10 text-green-400 border-green-400/20'
                                      : 'bg-gray-400/10 text-gray-500 border-gray-400/20'
                                  }`}
                                >
                                  {m.is_active ? 'active' : 'inactive'}
                                </span>
                                {m.membership_role === 'owner' ? (
                                  <span className="text-[11px] text-gray-500 capitalize px-1">owner</span>
                                ) : (
                                  <>
                                    <select
                                      value={m.membership_role}
                                      disabled={memberRowBusyId === m.id}
                                      onChange={(e) => changeMemberRole(m, e.target.value)}
                                      className="input-field text-[11px] py-1 px-1.5 disabled:opacity-50"
                                    >
                                      {ASSIGNABLE_MEMBERSHIP_ROLES.map((r) => (
                                        <option key={r} value={r}>
                                          {r}
                                        </option>
                                      ))}
                                    </select>
                                    <button
                                      disabled={memberRowBusyId === m.id}
                                      onClick={() => toggleMemberStatus(m)}
                                      title={m.is_active ? 'Deactivate' : 'Activate'}
                                      className="p-1 rounded hover:bg-white/10 text-gray-400 hover:text-white disabled:opacity-50"
                                    >
                                      <UserMinus size={13} />
                                    </button>
                                    <button
                                      disabled={memberRowBusyId === m.id}
                                      onClick={() => setConfirmRemoveMember(m)}
                                      title="Remove"
                                      className="p-1 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-400 disabled:opacity-50"
                                    >
                                      <Trash2 size={13} />
                                    </button>
                                  </>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {membersTotalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 mt-3">
                          <button
                            disabled={membersPage <= 1}
                            onClick={() => setMembersPage((p) => p - 1)}
                            className="text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            Previous
                          </button>
                          <span className="text-[11px] text-gray-500">
                            {membersPage} / {membersTotalPages}
                          </span>
                          <button
                            disabled={membersPage >= membersTotalPages}
                            onClick={() => setMembersPage((p) => p + 1)}
                            className="text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            Next
                          </button>
                        </div>
                      )}
                    </div>

                    {/* Invitations (Phase 2D) */}
                    <div className="mt-7 pt-6 border-t border-white/10">
                      <div className="flex items-center gap-2 mb-3">
                        <Mail size={16} className="text-cyan-400" />
                        <h3 className="text-sm font-bold">Invitations</h3>
                        <span className="text-xs text-gray-500">({invitationsTotal})</span>
                        <button
                          onClick={openCreateInvite}
                          className="ml-auto flex items-center gap-1 text-xs text-cyan-400 hover:text-cyan-300 font-medium"
                        >
                          <Send size={13} /> Invite
                        </button>
                      </div>

                      <div className="flex gap-2 mb-3">
                        <div className="relative flex-1">
                          <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                          <input
                            value={invitationSearch}
                            onChange={(e) => setInvitationSearch(e.target.value)}
                            placeholder="Search by email..."
                            className="input-field pl-7 text-xs py-1.5"
                          />
                        </div>
                        <select
                          value={invitationStatusFilter}
                          onChange={(e) => setInvitationStatusFilter(e.target.value)}
                          className="input-field text-xs py-1.5 w-32"
                        >
                          <option value="">All statuses</option>
                          {INVITATION_STATUSES.map((s) => (
                            <option key={s} value={s}>
                              {s}
                            </option>
                          ))}
                        </select>
                      </div>

                      {inviteRowError && (
                        <div className="flex items-center gap-2 text-xs text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-3">
                          <ShieldAlert size={13} className="flex-shrink-0" /> {inviteRowError}
                        </div>
                      )}
                      {invitationsError && (
                        <div className="flex items-center gap-2 text-xs text-red-400 mb-3">
                          <AlertCircle size={13} /> {invitationsError}
                        </div>
                      )}

                      {invitationsLoading ? (
                        <div className="flex justify-center py-6">
                          <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                        </div>
                      ) : invitations.length === 0 ? (
                        <p className="text-xs text-gray-600 text-center py-4">No invitations found.</p>
                      ) : (
                        <div className="space-y-1.5 max-h-64 overflow-y-auto">
                          {invitations.map((inv) => (
                            <div
                              key={inv.id}
                              className="flex items-center justify-between gap-2 bg-white/3 border border-white/5 rounded-lg px-3 py-2"
                            >
                              <div className="min-w-0">
                                <p className="text-xs font-medium truncate">{inv.email}</p>
                                <p className="text-[11px] text-gray-500 capitalize">
                                  {inv.membership_role}
                                  {inv.status === 'pending' && (
                                    <span className="text-gray-600">
                                      {' '}
                                      · expires {new Date(inv.expires_at).toLocaleDateString()}
                                    </span>
                                  )}
                                </p>
                              </div>
                              <div className="flex items-center gap-1.5 flex-shrink-0">
                                <span
                                  className={`text-[10px] px-1.5 py-0.5 rounded-full border capitalize ${invitationStatusBadge(inv.status)}`}
                                >
                                  {inv.status}
                                </span>
                                {inv.status === 'pending' && (
                                  <button
                                    disabled={inviteRowBusyId === inv.id}
                                    onClick={() => handleRevokeInvite(inv)}
                                    title="Revoke"
                                    className="p-1 rounded hover:bg-red-500/10 text-gray-400 hover:text-red-400 disabled:opacity-50"
                                  >
                                    <Ban size={13} />
                                  </button>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {invitationsTotalPages > 1 && (
                        <div className="flex items-center justify-center gap-2 mt-3">
                          <button
                            disabled={invitationsPage <= 1}
                            onClick={() => setInvitationsPage((p) => p - 1)}
                            className="text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            Previous
                          </button>
                          <span className="text-[11px] text-gray-500">
                            {invitationsPage} / {invitationsTotalPages}
                          </span>
                          <button
                            disabled={invitationsPage >= invitationsTotalPages}
                            onClick={() => setInvitationsPage((p) => p + 1)}
                            className="text-xs text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            Next
                          </button>
                        </div>
                      )}
                      <p className="text-[11px] text-gray-600 mt-3">
                        No email is sent — copy the one-time link shown after creating an invitation and deliver it manually.
                      </p>
                    </div>
                  </>
                )
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Create-invitation modal */}
      <AnimatePresence>
        {createInviteOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget && !createInviteLoading) setCreateInviteOpen(false)
            }}
          >
            <motion.div initial={{ scale: 0.92, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 20 }} className="glass-card p-7 w-full max-w-md">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold">{justCreatedInvite ? 'Invitation created' : 'Invite by email'}</h2>
                <button
                  onClick={() => !createInviteLoading && setCreateInviteOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              {justCreatedInvite ? (
                <div>
                  <div className="flex items-start gap-2 text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/25 rounded-lg px-3 py-3 mb-4">
                    <ShieldAlert size={16} className="flex-shrink-0 mt-0.5" />
                    <span>
                      This link is shown <strong>once</strong> and is not stored anywhere retrievable — copy it now
                      and deliver it to <strong>{justCreatedInvite.email}</strong> manually. No email is sent.
                    </span>
                  </div>
                  <label className="block text-xs text-gray-500 mb-1.5">One-time acceptance link</label>
                  <div className="flex gap-2 mb-2">
                    <input
                      readOnly
                      value={justCreatedInvite.accept_url}
                      onClick={(e) => e.target.select()}
                      className="input-field flex-1 text-xs font-mono"
                    />
                    <button
                      onClick={copyInviteUrl}
                      className="btn-secondary px-3 flex items-center gap-1.5 text-xs flex-shrink-0"
                    >
                      {copyFeedback ? <Check size={14} /> : <Copy size={14} />}
                      {copyFeedback ? 'Copied' : 'Copy'}
                    </button>
                  </div>
                  <p className="text-[11px] text-gray-600 mb-6 flex items-center gap-1.5">
                    <Clock size={11} /> Expires {new Date(justCreatedInvite.expires_at).toLocaleString()}
                  </p>
                  <button
                    onClick={() => setCreateInviteOpen(false)}
                    className="btn-primary w-full py-2.5 text-sm"
                  >
                    Done
                  </button>
                </div>
              ) : (
                <form onSubmit={submitCreateInvite}>
                  {createInviteError && (
                    <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                      <ShieldAlert size={15} className="flex-shrink-0" /> {createInviteError}
                    </div>
                  )}
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1.5">Email</label>
                      <div className="relative">
                        <Mail size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" />
                        <input
                          type="email"
                          value={createInviteEmail}
                          onChange={(e) => setCreateInviteEmail(e.target.value)}
                          placeholder="person@example.com"
                          className="input-field pl-9"
                          required
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1.5">Organization role</label>
                      <select
                        value={createInviteRole}
                        onChange={(e) => setCreateInviteRole(e.target.value)}
                        className="input-field w-full"
                      >
                        {ASSIGNABLE_MEMBERSHIP_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="flex gap-3 mt-7">
                    <button
                      type="button"
                      disabled={createInviteLoading}
                      onClick={() => setCreateInviteOpen(false)}
                      className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                    >
                      Cancel
                    </button>
                    <button
                      type="submit"
                      disabled={createInviteLoading || !createInviteEmail.trim()}
                      className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                    >
                      {createInviteLoading ? (
                        <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                      ) : (
                        <Send size={14} />
                      )}
                      Send Invitation
                    </button>
                  </div>
                </form>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Remove-member confirmation modal */}
      <AnimatePresence>
        {confirmRemoveMember && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget && memberRowBusyId !== confirmRemoveMember.id) setConfirmRemoveMember(null)
            }}
          >
            <motion.div initial={{ scale: 0.92 }} animate={{ scale: 1 }} exit={{ scale: 0.92 }} className="glass-card p-8 w-full max-w-sm text-center">
              <div className="w-14 h-14 rounded-full bg-red-400/10 border border-red-400/20 flex items-center justify-center mx-auto mb-4">
                <ShieldAlert size={24} className="text-red-400" />
              </div>
              <h3 className="text-lg font-bold mb-2">Remove member?</h3>
              <p className="text-gray-400 text-sm mb-7">
                Remove {confirmRemoveMember.user.name} ({confirmRemoveMember.membership_role}) from this organization? This only removes
                their organization membership — their platform account is unaffected.
              </p>
              <div className="flex gap-3">
                <button
                  disabled={memberRowBusyId === confirmRemoveMember.id}
                  onClick={() => setConfirmRemoveMember(null)}
                  className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  disabled={memberRowBusyId === confirmRemoveMember.id}
                  onClick={runConfirmedRemoveMember}
                  className="btn-danger flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {memberRowBusyId === confirmRemoveMember.id ? (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Trash2 size={14} />
                  )}
                  Remove
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Add-member modal */}
      <AnimatePresence>
        {addMemberOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/80 backdrop-blur-sm z-[60] flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget && !addMemberLoading) setAddMemberOpen(false)
            }}
          >
            <motion.div initial={{ scale: 0.92, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 20 }} className="glass-card p-7 w-full max-w-md">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-bold">Add Member</h2>
                <button
                  onClick={() => !addMemberLoading && setAddMemberOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              {addMemberError && (
                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                  <ShieldAlert size={15} className="flex-shrink-0" /> {addMemberError}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">User (active users only)</label>
                  {addMemberSelectedUser ? (
                    <div className="flex items-center justify-between bg-white/5 border border-white/10 rounded-lg px-3 py-2.5">
                      <div>
                        <p className="text-sm font-medium">{addMemberSelectedUser.name}</p>
                        <p className="text-xs text-gray-500">{addMemberSelectedUser.email}</p>
                      </div>
                      <button
                        onClick={() => setAddMemberSelectedUser(null)}
                        className="text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="relative mb-2">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                        <input
                          value={addMemberSearch}
                          onChange={(e) => setAddMemberSearch(e.target.value)}
                          placeholder="Search active users by name or email..."
                          className="input-field pl-9 text-sm"
                        />
                      </div>
                      <div className="max-h-40 overflow-y-auto space-y-1.5">
                        {addMemberSearchLoading ? (
                          <div className="flex justify-center py-4">
                            <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                          </div>
                        ) : addMemberResults.length === 0 ? (
                          <p className="text-xs text-gray-600 text-center py-3">No active users found.</p>
                        ) : (
                          addMemberResults.map((u) => (
                            <button
                              key={u.id}
                              onClick={() => setAddMemberSelectedUser(u)}
                              className="w-full text-left flex items-center justify-between bg-white/3 hover:bg-white/8 border border-white/5 rounded-lg px-3 py-2 transition-colors"
                            >
                              <div>
                                <p className="text-sm">{u.name}</p>
                                <p className="text-xs text-gray-500">{u.email}</p>
                              </div>
                              <span className="text-xs text-gray-500 capitalize">{u.role}</span>
                            </button>
                          ))
                        )}
                      </div>
                    </>
                  )}
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Organization role</label>
                  <select
                    value={addMemberRole}
                    onChange={(e) => setAddMemberRole(e.target.value)}
                    className="input-field w-full"
                  >
                    {ASSIGNABLE_MEMBERSHIP_ROLES.map((r) => (
                      <option key={r} value={r}>
                        {r}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex gap-3 mt-7">
                <button
                  disabled={addMemberLoading}
                  onClick={() => setAddMemberOpen(false)}
                  className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  disabled={addMemberLoading || !addMemberSelectedUser}
                  onClick={submitAddMember}
                  className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {addMemberLoading ? (
                    <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Check size={16} />
                  )}
                  Add Member
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Status-change confirmation modal */}
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
            <motion.div initial={{ scale: 0.92 }} animate={{ scale: 1 }} exit={{ scale: 0.92 }} className="glass-card p-8 w-full max-w-sm text-center">
              <div className="w-14 h-14 rounded-full bg-yellow-400/10 border border-yellow-400/20 flex items-center justify-center mx-auto mb-4">
                <ShieldAlert size={24} className="text-yellow-400" />
              </div>
              <h3 className="text-lg font-bold mb-2">Confirm status change</h3>
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
                  onClick={runConfirmedStatusChange}
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

      {/* Create organization modal */}
      <AnimatePresence>
        {createOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={(e) => {
              if (e.target === e.currentTarget && !creating) setCreateOpen(false)
            }}
          >
            <motion.div initial={{ scale: 0.92, y: 20 }} animate={{ scale: 1, y: 0 }} exit={{ scale: 0.92, y: 20 }} className="glass-card p-7 w-full max-w-lg">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold">New Organization</h2>
                <button
                  onClick={() => !creating && setCreateOpen(false)}
                  className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white"
                >
                  <X size={20} />
                </button>
              </div>

              {createError && (
                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                  <ShieldAlert size={15} className="flex-shrink-0" /> {createError}
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Name</label>
                  <input
                    value={createForm.name}
                    onChange={(e) => setCreateForm((f) => ({ ...f, name: e.target.value }))}
                    className="input-field w-full"
                    placeholder="Acme Corp"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Slug (optional — generated from name if left blank)</label>
                  <input
                    value={createForm.slug}
                    onChange={(e) => setCreateForm((f) => ({ ...f, slug: e.target.value }))}
                    className="input-field w-full"
                    placeholder="acme-corp"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Description (optional)</label>
                  <textarea
                    value={createForm.description}
                    onChange={(e) => setCreateForm((f) => ({ ...f, description: e.target.value }))}
                    rows={2}
                    className="input-field w-full resize-none"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Owner (active users only)</label>
                  {selectedOwner ? (
                    <div className="flex items-center justify-between bg-white/5 border border-white/10 rounded-lg px-3 py-2.5">
                      <div>
                        <p className="text-sm font-medium">{selectedOwner.name}</p>
                        <p className="text-xs text-gray-500">{selectedOwner.email}</p>
                      </div>
                      <button
                        onClick={() => setSelectedOwner(null)}
                        className="text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        Change
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="relative mb-2">
                        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
                        <input
                          value={ownerSearch}
                          onChange={(e) => setOwnerSearch(e.target.value)}
                          placeholder="Search active users by name or email..."
                          className="input-field pl-9 text-sm"
                        />
                      </div>
                      <div className="max-h-40 overflow-y-auto space-y-1.5">
                        {ownerSearchLoading ? (
                          <div className="flex justify-center py-4">
                            <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                          </div>
                        ) : ownerResults.length === 0 ? (
                          <p className="text-xs text-gray-600 text-center py-3">No active users found.</p>
                        ) : (
                          ownerResults.map((u) => (
                            <button
                              key={u.id}
                              onClick={() => setSelectedOwner(u)}
                              className="w-full text-left flex items-center justify-between bg-white/3 hover:bg-white/8 border border-white/5 rounded-lg px-3 py-2 transition-colors"
                            >
                              <div>
                                <p className="text-sm">{u.name}</p>
                                <p className="text-xs text-gray-500">{u.email}</p>
                              </div>
                              <span className="text-xs text-gray-500 capitalize">{u.role}</span>
                            </button>
                          ))
                        )}
                      </div>
                    </>
                  )}
                </div>
              </div>

              <div className="flex gap-3 mt-7">
                <button
                  disabled={creating}
                  onClick={() => setCreateOpen(false)}
                  className="btn-secondary flex-1 py-2.5 text-sm disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  disabled={creating || !createForm.name.trim() || !selectedOwner}
                  onClick={submitCreate}
                  className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {creating ? (
                    <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <Check size={16} />
                  )}
                  Create
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
