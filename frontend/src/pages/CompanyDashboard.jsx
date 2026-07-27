import React, { useEffect, useState, useCallback } from 'react'
import { motion } from 'framer-motion'
import {
  Building2, Users, FileQuestion, ClipboardList, UserCog, AlertCircle,
  Mail, Send, Copy, Check, Ban, ShieldAlert,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import OrganizationMembershipSummary from '../components/OrganizationMembershipSummary'
import { getMyMemberships, getOrganizationMembers, getOrganization } from '../api/organizations'
import { listInvitations, createInvitation, revokeInvitation } from '../api/invitations'

const ASSIGNABLE_MEMBERSHIP_ROLES = ['admin', 'interviewer', 'candidate']

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

export default function CompanyDashboard() {
  const { user } = useAuth()
  const [membersState, setMembersState] = useState('loading') // loading | empty | error | ready
  const [members, setMembers] = useState([])

  // Invitations (Phase 2D) — only meaningful once we know the caller's own
  // membership role and their organization's status, so this stays a
  // separate, dependent piece of state rather than merging into the
  // members-loading effect above.
  const [myOrgId, setMyOrgId] = useState(null)
  const [myMembershipRole, setMyMembershipRole] = useState(null)
  const [myOrgStatus, setMyOrgStatus] = useState(null)
  const [invitations, setInvitations] = useState([])
  const [invitationsState, setInvitationsState] = useState('idle') // idle | loading | error | ready
  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState('interviewer')
  const [inviteError, setInviteError] = useState('')
  const [inviteLoading, setInviteLoading] = useState(false)
  const [justCreatedInvite, setJustCreatedInvite] = useState(null)
  const [copyFeedback, setCopyFeedback] = useState(false)
  const [inviteRowBusyId, setInviteRowBusyId] = useState(null)

  const canManageInvitations =
    (myMembershipRole === 'owner' || myMembershipRole === 'admin') && myOrgStatus !== 'suspended'

  const fetchInvitations = useCallback(() => {
    if (!myOrgId) return
    setInvitationsState('loading')
    listInvitations(myOrgId, { page: 1, page_size: 20 })
      .then(({ data }) => {
        setInvitations(data.items || [])
        setInvitationsState('ready')
      })
      .catch(() => setInvitationsState('error'))
  }, [myOrgId])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const { data: memberships } = await getMyMemberships()
        if (cancelled) return
        if (!memberships.length) {
          setMembersState('empty')
          return
        }
        const orgId = memberships[0].organization_id
        setMyOrgId(orgId)
        setMyMembershipRole(memberships[0].membership_role)

        // Use the first active membership's organization for the member list.
        // Phase 2C: this endpoint now always returns the enriched, paginated
        // {items, total, ...} shape (each item includes a nested `user`
        // summary) — previously a plain array of bare membership rows.
        const [membersRes, orgRes] = await Promise.all([
          getOrganizationMembers(orgId),
          getOrganization(orgId).catch(() => ({ data: null })),
        ])
        if (cancelled) return
        setMembers(membersRes.data.items || [])
        setMembersState('ready')
        if (orgRes.data) setMyOrgStatus(orgRes.data.status)
      } catch {
        if (!cancelled) setMembersState('error')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    if (canManageInvitations) fetchInvitations()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canManageInvitations, fetchInvitations])

  const submitInvite = async (e) => {
    e.preventDefault()
    if (!myOrgId || !inviteEmail.trim()) return
    setInviteLoading(true)
    setInviteError('')
    try {
      const { data } = await createInvitation(myOrgId, { email: inviteEmail.trim(), membership_role: inviteRole })
      setJustCreatedInvite(data)
      setInviteEmail('')
      fetchInvitations()
    } catch (e) {
      setInviteError(e.response?.data?.detail || 'Could not create invitation. Please try again.')
    } finally {
      setInviteLoading(false)
    }
  }

  const copyInviteUrl = async () => {
    if (!justCreatedInvite?.accept_url) return
    try {
      await navigator.clipboard.writeText(justCreatedInvite.accept_url)
      setCopyFeedback(true)
      setTimeout(() => setCopyFeedback(false), 2000)
    } catch {
      // Clipboard API unavailable/denied — URL remains visible/selectable.
    }
  }

  const handleRevoke = async (invitation) => {
    if (!myOrgId) return
    setInviteRowBusyId(invitation.id)
    try {
      await revokeInvitation(myOrgId, invitation.id)
      fetchInvitations()
    } finally {
      setInviteRowBusyId(null)
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
            <Building2 size={20} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-3xl font-black">Company Admin</h1>
            <p className="text-gray-400 text-sm mt-0.5">Signed in as {user?.name}</p>
          </div>
        </motion.div>

        {/* Organization summary — real data, handles empty/pending/error */}
        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3">
            Your Organization
          </h2>
          <OrganizationMembershipSummary />
        </div>

        {/* Members — real data when an org membership exists */}
        <div className="glass-card p-6 mb-6">
          <div className="flex items-center gap-2 mb-4">
            <Users size={20} className="text-cyan-400" />
            <h3 className="text-lg font-bold">Members</h3>
          </div>
          {membersState === 'loading' && (
            <div className="flex justify-center py-6">
              <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
            </div>
          )}
          {membersState === 'error' && (
            <div className="flex items-center gap-2 text-sm text-red-400">
              <AlertCircle size={16} /> Unable to load members right now.
            </div>
          )}
          {membersState === 'empty' && (
            <p className="text-gray-500 text-sm">
              No organization membership found — members will appear here once you belong to an
              active organization.
            </p>
          )}
          {membersState === 'ready' && (
            <div className="space-y-2">
              {members.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/3 border border-white/5 text-sm"
                >
                  <span className="text-gray-300">{m.user.name} <span className="text-gray-500">({m.user.email})</span></span>
                  <span className="text-xs text-gray-500 capitalize">
                    {m.membership_role} · {m.is_active ? 'active' : 'inactive'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Invitations — minimal owner/admin UI (Phase 2D). Backend
            authorization is authoritative; this only renders when the
            caller's own membership role and organization status already
            qualify, matching what the backend would allow anyway. No
            broad user directory is exposed here — invites are by email
            only. */}
        {canManageInvitations && (
          <div className="glass-card p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <Mail size={20} className="text-cyan-400" />
              <h3 className="text-lg font-bold">Invitations</h3>
            </div>

            <form onSubmit={submitInvite} className="flex flex-col sm:flex-row gap-2 mb-4">
              <input
                type="email"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="person@example.com"
                className="input-field flex-1 text-sm"
                required
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value)}
                className="input-field text-sm sm:w-36"
              >
                {ASSIGNABLE_MEMBERSHIP_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
              <button
                type="submit"
                disabled={inviteLoading || !inviteEmail.trim()}
                className="btn-primary text-sm px-4 flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {inviteLoading ? (
                  <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                ) : (
                  <Send size={14} />
                )}
                Invite
              </button>
            </form>

            {inviteError && (
              <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-4">
                <ShieldAlert size={15} className="flex-shrink-0" /> {inviteError}
              </div>
            )}

            {justCreatedInvite && (
              <div className="mb-4">
                <div className="flex items-start gap-2 text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/25 rounded-lg px-3 py-3 mb-2">
                  <ShieldAlert size={15} className="flex-shrink-0 mt-0.5" />
                  <span>
                    This link is shown <strong>once</strong> and not stored anywhere retrievable — copy it now and
                    deliver it to <strong>{justCreatedInvite.email}</strong> manually. No email is sent.
                  </span>
                </div>
                <div className="flex gap-2">
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
              </div>
            )}

            {invitationsState === 'loading' && (
              <div className="flex justify-center py-4">
                <div className="w-5 h-5 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
              </div>
            )}
            {invitationsState === 'error' && (
              <div className="flex items-center gap-2 text-sm text-red-400">
                <AlertCircle size={16} /> Unable to load invitations right now.
              </div>
            )}
            {invitationsState === 'ready' && invitations.length === 0 && (
              <p className="text-gray-500 text-sm">No invitations yet.</p>
            )}
            {invitationsState === 'ready' && invitations.length > 0 && (
              <div className="space-y-1.5">
                {invitations.map((inv) => (
                  <div
                    key={inv.id}
                    className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/3 border border-white/5 text-sm"
                  >
                    <span className="text-gray-300 truncate">{inv.email}</span>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <span className="text-xs text-gray-500 capitalize">
                        {inv.membership_role} · {inv.status}
                      </span>
                      {inv.status === 'pending' && (
                        <button
                          disabled={inviteRowBusyId === inv.id}
                          onClick={() => handleRevoke(inv)}
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
          </div>
        )}

        <div className="grid md:grid-cols-3 gap-5">
          <ComingSoonCard
            icon={<FileQuestion size={20} className="text-cyan-400" />}
            title="Company Question Bank"
            note="Organization-owned questions are not implemented yet — the platform question bank remains global."
          />
          <ComingSoonCard
            icon={<ClipboardList size={20} className="text-cyan-400" />}
            title="Assessments"
            note="Assign and track candidate assessments for your organization."
          />
          <ComingSoonCard
            icon={<UserCog size={20} className="text-cyan-400" />}
            title="Candidates & Interviewers"
            note="Dedicated management views for candidate and interviewer members."
          />
        </div>
      </div>
    </div>
  )
}
