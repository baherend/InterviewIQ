import React, { useEffect, useState } from 'react'
import { useSearchParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  Mail, CheckCircle2, XCircle, Clock, ShieldAlert, Building2, UserPlus, LogIn, Lock, User as UserIcon,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { getHomeRouteForRole } from '../utils/roles'
import { inspectInvitation, acceptInvitation, registerAndAcceptInvitation } from '../api/invitations'

const REASON_COPY = {
  not_found: {
    title: 'Invalid invitation link',
    body: 'This invitation link is not valid. Double-check the link, or ask the person who invited you to send a new one.',
  },
  expired: {
    title: 'Invitation expired',
    body: 'This invitation has expired. Ask an organization owner or admin to send a new one.',
  },
  revoked: {
    title: 'Invitation revoked',
    body: 'This invitation was revoked and can no longer be used.',
  },
  accepted: {
    title: 'Already accepted',
    body: 'This invitation has already been accepted. If this was you, just log in as usual.',
  },
  organization_suspended: {
    title: 'Organization unavailable',
    body: 'This organization is currently suspended and cannot accept new members right now.',
  },
}

const Shell = ({ children }) => (
  <div className="gradient-bg min-h-screen flex items-center justify-center px-4 pt-16">
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="w-full max-w-md glass-card p-8 md:p-10"
    >
      {children}
    </motion.div>
  </div>
)

export default function InvitationAccept() {
  const [searchParams, setSearchParams] = useSearchParams()
  const token = searchParams.get('token') || ''
  const navigate = useNavigate()
  const { user, isAuthenticated, login } = useAuth()

  const [state, setState] = useState('loading') // loading | invalid | valid | success
  const [invite, setInvite] = useState(null)
  const [invalidReason, setInvalidReason] = useState('not_found')
  const [actionError, setActionError] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [form, setForm] = useState({ name: '', password: '' })

  useEffect(() => {
    if (!token) {
      setInvalidReason('not_found')
      setState('invalid')
      return
    }
    let cancelled = false
    inspectInvitation(token)
      .then(({ data }) => {
        if (cancelled) return
        if (!data.valid) {
          setInvalidReason(data.reason || 'not_found')
          setState('invalid')
        } else {
          setInvite(data)
          setState('valid')
        }
      })
      .catch(() => {
        if (!cancelled) {
          setInvalidReason('not_found')
          setState('invalid')
        }
      })
    return () => {
      cancelled = true
    }
  }, [token])

  // Once the invitation is consumed (accepted), the raw token in the URL
  // is no longer usable — strip it from the visible address bar / history
  // rather than leaving a dead (or worse, reusable-looking) token exposed.
  const clearTokenFromUrl = () => setSearchParams({}, { replace: true })

  useEffect(() => {
    if (state !== 'success') return
    const home = getHomeRouteForRole(user?.role)
    const t = setTimeout(() => navigate(home || '/login', { replace: true }), 1600)
    return () => clearTimeout(t)
  }, [state, user, navigate])

  const handleAcceptExisting = async () => {
    setActionLoading(true)
    setActionError('')
    try {
      await acceptInvitation(token)
      clearTokenFromUrl()
      setState('success')
    } catch (e) {
      setActionError(e.response?.data?.detail || 'Could not accept this invitation. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleRegisterAndAccept = async (e) => {
    e.preventDefault()
    setActionLoading(true)
    setActionError('')
    try {
      const { data } = await registerAndAcceptInvitation({ token, name: form.name, password: form.password })
      login(data.access_token, data.user)
      clearTokenFromUrl()
      setState('success')
    } catch (e) {
      setActionError(e.response?.data?.detail || 'Could not complete registration. Please try again.')
    } finally {
      setActionLoading(false)
    }
  }

  if (state === 'loading') {
    return (
      <Shell>
        <div className="flex flex-col items-center py-6">
          <div className="w-10 h-10 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-400 text-sm">Checking your invitation...</p>
        </div>
      </Shell>
    )
  }

  if (state === 'invalid') {
    const copy = REASON_COPY[invalidReason] || REASON_COPY.not_found
    return (
      <Shell>
        <div className="text-center">
          <div className="w-14 h-14 rounded-full bg-red-400/10 border border-red-400/20 flex items-center justify-center mx-auto mb-4">
            <XCircle size={26} className="text-red-400" />
          </div>
          <h1 className="text-xl font-bold mb-2">{copy.title}</h1>
          <p className="text-gray-400 text-sm leading-relaxed">{copy.body}</p>
        </div>
      </Shell>
    )
  }

  if (state === 'success') {
    return (
      <Shell>
        <div className="text-center">
          <div className="w-14 h-14 rounded-full bg-green-400/10 border border-green-400/20 flex items-center justify-center mx-auto mb-4">
            <CheckCircle2 size={26} className="text-green-400" />
          </div>
          <h1 className="text-xl font-bold mb-2">Invitation accepted</h1>
          <p className="text-gray-400 text-sm leading-relaxed">Taking you to your dashboard...</p>
        </div>
      </Shell>
    )
  }

  // state === 'valid'
  const emailMismatch =
    isAuthenticated && user?.email && invite.email && user.email.toLowerCase() !== invite.email.toLowerCase()

  return (
    <Shell>
      <div className="text-center mb-6">
        <div className="w-14 h-14 rounded-full bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center mx-auto mb-4">
          <Building2 size={24} className="text-cyan-400" />
        </div>
        <h1 className="text-xl font-bold mb-1">You're invited</h1>
        <p className="text-gray-400 text-sm">
          Join <span className="text-white font-medium">{invite.organization_name}</span> as{' '}
          <span className="text-cyan-400 capitalize font-medium">{invite.membership_role}</span>
        </p>
        <p className="text-gray-500 text-xs mt-2 flex items-center justify-center gap-1.5">
          <Mail size={12} /> {invite.email}
        </p>
        <p className="text-gray-600 text-xs mt-1 flex items-center justify-center gap-1.5">
          <Clock size={12} /> Expires {new Date(invite.expires_at).toLocaleString()}
        </p>
      </div>

      {actionError && (
        <div className="flex items-center gap-2 text-sm text-red-400 bg-red-500/10 border border-red-500/25 rounded-lg px-3 py-2 mb-5">
          <ShieldAlert size={15} className="flex-shrink-0" /> {actionError}
        </div>
      )}

      {emailMismatch ? (
        <div className="text-center">
          <div className="flex items-center gap-2 text-sm text-yellow-400 bg-yellow-500/10 border border-yellow-500/25 rounded-lg px-3 py-3 mb-4 text-left">
            <ShieldAlert size={16} className="flex-shrink-0 mt-0.5" />
            <span>
              You're signed in as <strong>{user.email}</strong>, but this invitation was sent to{' '}
              <strong>{invite.email}</strong>. Log out and sign in with the invited email to accept it.
            </span>
          </div>
        </div>
      ) : invite.existing_account ? (
        isAuthenticated ? (
          <button
            onClick={handleAcceptExisting}
            disabled={actionLoading}
            className="btn-primary w-full py-3 flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {actionLoading ? (
              <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
            ) : (
              <LogIn size={16} />
            )}
            Accept as {user.name}
          </button>
        ) : (
          <div className="text-center">
            <p className="text-gray-400 text-sm mb-4">
              An account already exists for this email. Log in, then come back to this link to accept.
            </p>
            <Link to="/login" className="btn-primary w-full py-3 inline-flex items-center justify-center gap-2">
              <LogIn size={16} /> Go to login
            </Link>
            <p className="text-gray-600 text-xs mt-3">
              This invitation link stays valid until it expires — you can return to it after logging in.
            </p>
          </div>
        )
      ) : (
        <form onSubmit={handleRegisterAndAccept} className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Your name</label>
            <div className="relative">
              <UserIcon size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="input-field pl-10"
                required
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1.5">Choose a password</label>
            <div className="relative">
              <Lock size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500" />
              <input
                type="password"
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
                className="input-field pl-10"
                required
                autoComplete="new-password"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={actionLoading}
            className="btn-primary w-full py-3 flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {actionLoading ? (
              <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
            ) : (
              <UserPlus size={16} />
            )}
            Create account and join
          </button>
        </form>
      )}
    </Shell>
  )
}
