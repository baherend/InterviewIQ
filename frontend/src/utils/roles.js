// Exact global-role -> role-home route mapping. Keep in sync with backend
// app.models.user.UserRole. An unrecognized/missing role must never
// silently fall through to an admin route — callers must treat a null
// return as "fail safe" (log out, redirect to /login), never assume /admin.
const ROLE_HOME_ROUTES = {
  system_admin: '/admin',
  student: '/student',
  company_admin: '/company',
  interviewer: '/interviewer',
  candidate: '/candidate',
}

export function getHomeRouteForRole(role) {
  return ROLE_HOME_ROUTES[role] || null
}

// Roles that are organization-facing (as opposed to the platform-wide
// system_admin or the student self-practice flow) — used only to decide
// whether to show an organization-membership summary in a dashboard.
export const ORGANIZATION_FACING_ROLES = ['company_admin', 'interviewer', 'candidate']
