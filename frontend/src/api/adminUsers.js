import api from './axios'

// Thin wrappers around the admin user-management endpoints. No token
// logging, no new axios instance — reuses the existing client (which
// already attaches the Authorization header and handles 401 globally via
// its response interceptor).
export const listAdminUsers = (params) => api.get('/admin/users', { params })
export const getAdminUser = (userId) => api.get(`/admin/users/${userId}`)
export const updateAdminUserStatus = (userId, isActive) =>
  api.patch(`/admin/users/${userId}/status`, { is_active: isActive })
export const updateAdminUserRole = (userId, role) =>
  api.patch(`/admin/users/${userId}/role`, { role })
