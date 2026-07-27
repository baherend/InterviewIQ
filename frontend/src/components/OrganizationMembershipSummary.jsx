import React, { useEffect, useState } from 'react'
import { Building2, AlertCircle } from 'lucide-react'
import { getMyMemberships, getOrganization } from '../api/organizations'

const statusBadge = (status) =>
  ({
    active: 'bg-green-400/10 text-green-400 border-green-400/20',
    pending: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20',
    suspended: 'bg-red-400/10 text-red-400 border-red-400/20',
  }[status] || 'bg-gray-400/10 text-gray-400 border-gray-400/20')

// Shown on organization-facing dashboards (company_admin, interviewer,
// candidate). Calls GET /organizations/me/memberships, then GET
// /organizations/{id} for each to show a name/status. Handles: no
// memberships, a pending organization, and API/network errors — a
// suspended organization is already excluded from /me/memberships by the
// backend (Phase 1E policy), so it surfaces here as "no memberships"
// rather than a distinct suspended state.
export default function OrganizationMembershipSummary() {
  const [state, setState] = useState('loading') // loading | empty | error | ready
  const [memberships, setMemberships] = useState([])

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      try {
        const { data: rows } = await getMyMemberships()
        if (cancelled) return
        if (!rows.length) {
          setState('empty')
          return
        }
        const enriched = await Promise.all(
          rows.map(async (m) => {
            try {
              const { data: organization } = await getOrganization(m.organization_id)
              return { ...m, organization }
            } catch {
              return { ...m, organization: null }
            }
          })
        )
        if (cancelled) return
        setMemberships(enriched)
        setState('ready')
      } catch {
        if (!cancelled) setState('error')
      }
    }

    load()
    return () => {
      cancelled = true
    }
  }, [])

  if (state === 'loading') {
    return (
      <div className="glass-card p-6 flex items-center justify-center">
        <div className="w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (state === 'error') {
    return (
      <div className="glass-card p-6 flex items-center gap-3 text-sm text-red-400">
        <AlertCircle size={18} className="flex-shrink-0" />
        Unable to load your organization membership right now. Please try again later.
      </div>
    )
  }

  if (state === 'empty') {
    return (
      <div className="glass-card p-8 text-center text-gray-400 text-sm">
        <Building2 size={28} className="text-gray-600 mx-auto mb-3" />
        You are not currently an active member of any organization.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {memberships.map((m) => (
        <div key={m.id} className="glass-card p-5 flex items-center justify-between gap-4">
          <div>
            <p className="font-semibold text-sm">
              {m.organization?.name || `Organization #${m.organization_id}`}
            </p>
            <p className="text-xs text-gray-500 mt-0.5 capitalize">{m.membership_role} membership</p>
          </div>
          {m.organization && (
            <span
              className={`text-xs px-2.5 py-1 rounded-full border font-medium capitalize flex-shrink-0 ${statusBadge(
                m.organization.status
              )}`}
            >
              {m.organization.status}
            </span>
          )}
        </div>
      ))}
    </div>
  )
}
