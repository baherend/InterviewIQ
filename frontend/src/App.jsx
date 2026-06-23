import React from 'react'
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Navbar from './components/Navbar'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import InterviewTypeSelection from './pages/InterviewTypeSelection'
import TechnicalTrackSelection from './pages/TechnicalTrackSelection'
import InterviewRoom from './pages/InterviewRoom'
import Processing from './pages/Processing'
import Report from './pages/Report'
import History from './pages/History'
import AdminQuestions from './pages/AdminQuestions'

const ProtectedRoute = ({ children }) => {
  const { token, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="neon-text text-lg font-semibold">Loading InterviewIQ...</p>
        </div>
      </div>
    )
  }
  return token ? children : <Navigate to="/login" replace />
}

const AppRoutes = () => {
  const { token } = useAuth()
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={token ? <Navigate to="/dashboard" /> : <Login />} />
        <Route path="/register" element={token ? <Navigate to="/dashboard" /> : <Register />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/interview/type" element={<ProtectedRoute><InterviewTypeSelection /></ProtectedRoute>} />
        <Route path="/interview/track" element={<ProtectedRoute><TechnicalTrackSelection /></ProtectedRoute>} />
        <Route path="/interview/room" element={<ProtectedRoute><InterviewRoom /></ProtectedRoute>} />
        <Route path="/interview/processing" element={<ProtectedRoute><Processing /></ProtectedRoute>} />
        <Route path="/report/:id" element={<ProtectedRoute><Report /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
        <Route path="/admin/questions" element={<ProtectedRoute><AdminQuestions /></ProtectedRoute>} />
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
