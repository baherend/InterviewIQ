import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import { ProtectedRoute, RoleRoute, PublicOnlyRoute } from './routes/guards'
import { getHomeRouteForRole } from './utils/roles'
import Navbar from './components/Navbar'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import AdminDashboard from './pages/AdminDashboard'
import CompanyDashboard from './pages/CompanyDashboard'
import InterviewerDashboard from './pages/InterviewerDashboard'
import CandidateDashboard from './pages/CandidateDashboard'
import InterviewTypeSelection from './pages/InterviewTypeSelection'
import TechnicalTrackSelection from './pages/TechnicalTrackSelection'
import InterviewRoom from './pages/InterviewRoom'
import Processing from './pages/Processing'
import Report from './pages/Report'
import History from './pages/History'
import AdminQuestions from './pages/AdminQuestions'
import AdminOrganizations from './pages/AdminOrganizations'
import AdminUsers from './pages/AdminUsers'
import InvitationAccept from './pages/InvitationAccept'
import Unauthorized from './pages/Unauthorized'
import FusionTest from './pages/FusionTest'

// Backward-compatible /dashboard: redirects to the caller's role home
// rather than being a destination itself.
const DashboardRedirect = () => {
  const { user } = useAuth()
  const home = getHomeRouteForRole(user?.role)
  return <Navigate to={home || '/login'} replace />
}

const AppRoutes = () => {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/fusion-test" element={<FusionTest />} />
        <Route path="/login" element={<PublicOnlyRoute><Login /></PublicOnlyRoute>} />
        <Route path="/register" element={<PublicOnlyRoute><Register /></PublicOnlyRoute>} />

        {/* Role homes */}
        <Route
          path="/admin"
          element={<RoleRoute allowedRoles={['system_admin']}><AdminDashboard /></RoleRoute>}
        />
        <Route
          path="/student"
          element={<RoleRoute allowedRoles={['student']}><Dashboard /></RoleRoute>}
        />
        <Route
          path="/company"
          element={<RoleRoute allowedRoles={['company_admin']}><CompanyDashboard /></RoleRoute>}
        />
        <Route
          path="/interviewer"
          element={<RoleRoute allowedRoles={['interviewer']}><InterviewerDashboard /></RoleRoute>}
        />
        <Route
          path="/candidate"
          element={<RoleRoute allowedRoles={['candidate']}><CandidateDashboard /></RoleRoute>}
        />

        {/* Backward-compatible generic dashboard */}
        <Route path="/dashboard" element={<ProtectedRoute><DashboardRedirect /></ProtectedRoute>} />

        {/* Existing student interview flow — student-only in this phase */}
        <Route
          path="/interview/type"
          element={<RoleRoute allowedRoles={['student']}><InterviewTypeSelection /></RoleRoute>}
        />
        <Route
          path="/interview/track"
          element={<RoleRoute allowedRoles={['student']}><TechnicalTrackSelection /></RoleRoute>}
        />
        <Route
          path="/interview/room"
          element={<RoleRoute allowedRoles={['student']}><InterviewRoom /></RoleRoute>}
        />
        <Route
          path="/interview/processing"
          element={<RoleRoute allowedRoles={['student']}><Processing /></RoleRoute>}
        />
        <Route
          path="/report/:id"
          element={<RoleRoute allowedRoles={['student']}><Report /></RoleRoute>}
        />
        <Route
          path="/history"
          element={<RoleRoute allowedRoles={['student']}><History /></RoleRoute>}
        />

        {/* Existing admin question route — system_admin only */}
        <Route
          path="/admin/questions"
          element={<RoleRoute allowedRoles={['system_admin']}><AdminQuestions /></RoleRoute>}
        />
        <Route
          path="/admin/organizations"
          element={<RoleRoute allowedRoles={['system_admin']}><AdminOrganizations /></RoleRoute>}
        />
        <Route
          path="/admin/users"
          element={<RoleRoute allowedRoles={['system_admin']}><AdminUsers /></RoleRoute>}
        />

        {/* Public invitation acceptance — deliberately unguarded: works for
            both an unauthenticated visitor (registration path) and an
            already-authenticated user (existing-account acceptance path).
            Backend authorization on each call is authoritative regardless. */}
        <Route path="/invitations/accept" element={<InvitationAccept />} />

        <Route path="/unauthorized" element={<Unauthorized />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
      </Router>
    </AuthProvider>
  )
}
