import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuth } from '../context/AuthContext'
import { Brain, LayoutDashboard, History, Shield, LogOut, Menu, X, ChevronRight } from 'lucide-react'

export default function Navbar() {
  const { user, logout, token } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
    setMenuOpen(false)
  }

  const navLinks = token
    ? [
        { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={16} /> },
        { to: '/history', label: 'History', icon: <History size={16} /> },
        { to: '/admin/questions', label: 'Admin', icon: <Shield size={16} /> },
      ]
    : []

  const isActive = (path) => location.pathname === path

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/5">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <Link to={token ? '/dashboard' : '/'} className="flex items-center gap-2 group">
            <div className="p-1.5 rounded-lg bg-cyan-400/10 border border-cyan-400/20 group-hover:border-cyan-400/50 transition-all">
              <Brain size={22} className="text-cyan-400" />
            </div>
            <span className="text-lg font-bold neon-text tracking-tight">InterviewIQ</span>
          </Link>

          {/* Desktop nav */}
          <div className="hidden md:flex items-center gap-1">
            {navLinks.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                className={`flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                  isActive(link.to)
                    ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/25'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                {link.icon}
                {link.label}
              </Link>
            ))}
          </div>

          {/* Right side */}
          <div className="hidden md:flex items-center gap-3">
            {token ? (
              <>
                <div className="glass px-3 py-1.5 rounded-lg">
                  <span className="text-sm text-gray-400">
                    Hey, <span className="text-cyan-400 font-semibold">{user?.name?.split(' ')[0]}</span>
                  </span>
                </div>
                <button
                  onClick={() => { navigate('/interview/type') }}
                  className="btn-primary text-sm py-2 px-4"
                >
                  New Interview
                </button>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-1.5 text-gray-400 hover:text-red-400 transition-colors text-sm"
                >
                  <LogOut size={16} />
                  Logout
                </button>
              </>
            ) : (
              <>
                <Link to="/login" className="btn-secondary text-sm py-2 px-5">Sign In</Link>
                <Link to="/register" className="btn-primary text-sm py-2 px-5">Get Started</Link>
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <button
            className="md:hidden p-2 rounded-lg text-gray-400 hover:text-white hover:bg-white/5 transition-colors"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            {menuOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {menuOpen && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="md:hidden border-t border-white/5 glass"
          >
            <div className="px-4 py-4 space-y-2">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMenuOpen(false)}
                  className={`flex items-center gap-2 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                    isActive(link.to)
                      ? 'bg-cyan-400/10 text-cyan-400'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  {link.icon} {link.label}
                </Link>
              ))}
              {token ? (
                <>
                  <button
                    onClick={() => { navigate('/interview/type'); setMenuOpen(false) }}
                    className="btn-primary w-full text-sm py-2.5"
                  >
                    New Interview
                  </button>
                  <button
                    onClick={handleLogout}
                    className="flex items-center gap-2 w-full px-4 py-3 text-red-400 hover:bg-red-400/5 rounded-lg text-sm"
                  >
                    <LogOut size={16} /> Logout
                  </button>
                </>
              ) : (
                <>
                  <Link to="/login" onClick={() => setMenuOpen(false)} className="btn-secondary w-full text-sm py-2.5 text-center block">Sign In</Link>
                  <Link to="/register" onClick={() => setMenuOpen(false)} className="btn-primary w-full text-sm py-2.5 text-center block">Get Started</Link>
                </>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  )
}
