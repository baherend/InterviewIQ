import api from './axios'

// Thin wrappers around the invitation endpoints (Phase 2D). No token
// logging anywhere here — a raw invitation token only ever passes through
// as a function argument / response field, is held transiently in
// component state, and is never written to localStorage.

// --- Organization-scoped management (system_admin, or active owner/admin) ---
export const listInvitations = (organizationId, params) =>
  api.get(`/organizations/${organizationId}/invitations`, { params })
export const createInvitation = (organizationId, payload) =>
  api.post(`/organizations/${organizationId}/invitations`, payload)
export const revokeInvitation = (organizationId, invitationId) =>
  api.patch(`/organizations/${organizationId}/invitations/${invitationId}/revoke`)
export const rotateInvitation = (organizationId, invitationId) =>
  api.post(`/organizations/${organizationId}/invitations/${invitationId}/rotate`)

// --- Public (token-based) ---
export const inspectInvitation = (token) => api.get('/invitations/inspect', { params: { token } })
export const acceptInvitation = (token) => api.post('/invitations/accept', { token })
export const registerAndAcceptInvitation = (payload) => api.post('/invitations/register-and-accept', payload)
