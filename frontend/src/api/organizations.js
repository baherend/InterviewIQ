import api from './axios'

// Thin wrappers around the organization endpoints. No new business logic —
// just named calls so pages don't hand-build URLs.
export const getMyMemberships = () => api.get('/organizations/me/memberships')
export const getOrganization = (organizationId) => api.get(`/organizations/${organizationId}`)

// Phase 2C: always returns the enriched, paginated
// {items, total, page, page_size} shape (each item includes a nested
// `user` summary) — this replaced the earlier plain-array response for
// every caller, not just system_admin. Params: q, membership_role,
// is_active, page, page_size (all optional).
export const getOrganizationMembers = (organizationId, params) =>
  api.get(`/organizations/${organizationId}/members`, { params })

// Membership management (Phase 2C) — system_admin, or an active
// owner/admin member of the organization. See
// backend/app/routers/organizations.py for the full authorization policy
// (owner membership is always immutable/undeletable through these calls).
export const addOrganizationMember = (organizationId, payload) =>
  api.post(`/organizations/${organizationId}/members`, payload)
export const updateMembershipRole = (organizationId, membershipId, membershipRole) =>
  api.patch(`/organizations/${organizationId}/members/${membershipId}/role`, {
    membership_role: membershipRole,
  })
export const updateMembershipStatus = (organizationId, membershipId, isActive) =>
  api.patch(`/organizations/${organizationId}/members/${membershipId}/status`, {
    is_active: isActive,
  })
export const removeOrganizationMember = (organizationId, membershipId) =>
  api.delete(`/organizations/${organizationId}/members/${membershipId}`)

// For system_admin, the backend returns a paginated
// {items, total, page, page_size} shape for this same endpoint (params:
// q, status, page, page_size). Non-admin callers get a plain array — see
// backend/app/routers/organizations.py.
export const listOrganizations = (params) => api.get('/organizations', { params })

export const createOrganization = (payload) => api.post('/organizations', payload)
export const updateOrganization = (organizationId, payload) =>
  api.patch(`/organizations/${organizationId}`, payload)
export const updateOrganizationStatus = (organizationId, status) =>
  api.patch(`/organizations/${organizationId}/status`, { status })
