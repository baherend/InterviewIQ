import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer,
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import {
  Brain, Eye, Mic, MessageSquare, BarChart3, TrendingUp, Award, PlayCircle,
  ChevronRight, Clock, AlertTriangle,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import ScoreCard from '../components/ScoreCard'
import api from '../api/axios'

const verdictBadge = (verdict) => {
  const map = {
    Excellent: 'bg-cyan-400/15 text-cyan-400 border-cyan-400/30',
    Pass: 'bg-blue-400/15 text-blue-400 border-blue-400/30',
    'Needs Improvement': 'bg-yellow-400/15 text-yellow-400 border-yellow-400/30',
    Fail: 'bg-red-400/15 text-red-400 border-red-400/30',
  }
  return map[verdict] || 'bg-gray-400/15 text-gray-400 border-gray-400/30'
}

const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload?.length) {
    return (
      <div className="glass p-3 border border-white/10 rounded-xl text-sm">
        <p className="text-gray-300 font-medium mb-1">{label}</p>
        {payload.map((p) => (
          <p key={p.name} style={{ color: p.color }}>{p.name}: <strong>{p.value}</strong></p>
        ))}
      </div>
    )
  }
  return null
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const load = async () => {
      try {
        const [statsRes, historyRes] = await Promise.all([
          api.get('/dashboard/statistics'),
          api.get('/dashboard/history'),
        ])
        setStats(statsRes.data)
        setHistory(historyRes.data)
      } catch (e) {
        console.error(e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg">
        <div className="text-center">
          <div className="w-14 h-14 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="neon-text font-semibold">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  const latest = history[0]
  const radarData = latest
    ? [
        { subject: 'Vision', score: latest.vision_score ?? 0 },
        { subject: 'Audio', score: latest.audio_score ?? 0 },
        { subject: 'NLP', score: latest.nlp_score ?? 0 },
      ]
    : []

  const hasData = stats && stats.total_interviews > 0

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-8 gap-4"
        >
          <div>
            <h1 className="text-3xl font-black">
              Welcome back, <span className="neon-text">{user?.name?.split(' ')[0]}</span> 👋
            </h1>
            <p className="text-gray-400 mt-1">Track your interview performance and improve over time.</p>
          </div>
          <button
            onClick={() => navigate('/interview/type')}
            className="btn-primary flex items-center gap-2 shrink-0"
          >
            <PlayCircle size={18} />
            New Interview
          </button>
        </motion.div>

        {!hasData ? (
          /* Empty state */
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            className="glass-card p-16 text-center max-w-lg mx-auto mt-16"
          >
            <Brain size={56} className="text-cyan-400 mx-auto mb-5 animate-float" />
            <h2 className="text-2xl font-black mb-3">No Interviews Yet</h2>
            <p className="text-gray-400 mb-8 leading-relaxed">
              Complete your first AI mock interview to unlock your personalised dashboard with scores, charts, and recommendations.
            </p>
            <button onClick={() => navigate('/interview/type')} className="btn-primary px-10 py-3.5 flex items-center gap-2 mx-auto">
              <PlayCircle size={18} /> Start Your First Interview
            </button>
          </motion.div>
        ) : (
          <>
            {/* Top stats */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
              {[
                { label: 'Total Interviews', value: stats.total_interviews, icon: <Brain size={20} className="text-cyan-400" />, color: 'bg-cyan-400/10' },
                { label: 'Average Score', value: `${stats.average_score}`, icon: <BarChart3 size={20} className="text-blue-400" />, color: 'bg-blue-400/10' },
                { label: 'Best Score', value: `${stats.best_score}`, icon: <Award size={20} className="text-yellow-400" />, color: 'bg-yellow-400/10' },
                { label: 'Latest Verdict', value: latest?.verdict || '—', icon: <TrendingUp size={20} className="text-purple-400" />, color: 'bg-purple-400/10' },
              ].map((item, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.1 }}
                  className="glass-card p-5"
                >
                  <div className={`w-10 h-10 ${item.color} rounded-xl flex items-center justify-center mb-3`}>
                    {item.icon}
                  </div>
                  <p className="text-2xl font-black text-white">{item.value}</p>
                  <p className="text-gray-400 text-sm mt-0.5">{item.label}</p>
                </motion.div>
              ))}
            </div>

            {/* Score cards */}
            {latest && (
              <div className="grid md:grid-cols-3 gap-4 mb-6">
                <ScoreCard
                  title="Vision Score"
                  score={latest.vision_score}
                  icon={<Eye size={22} className="text-cyan-400" />}
                  subtitle="Facial expression & eye contact"
                  delay={0}
                />
                <ScoreCard
                  title="Audio Score"
                  score={latest.audio_score}
                  icon={<Mic size={22} className="text-purple-400" />}
                  subtitle="Pace, clarity & confidence"
                  delay={0.1}
                />
                <ScoreCard
                  title="NLP Score"
                  score={latest.nlp_score}
                  icon={<MessageSquare size={22} className="text-blue-400" />}
                  subtitle="Content quality & relevance"
                  delay={0.2}
                />
              </div>
            )}

            {/* Charts */}
            <div className="grid lg:grid-cols-2 gap-6 mb-6">
              {/* Radar chart */}
              <motion.div
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.3 }}
                className="glass-card p-6"
              >
                <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                  <BarChart3 size={20} className="text-cyan-400" />
                  Latest Performance Radar
                </h3>
                <ResponsiveContainer width="100%" height={260}>
                  <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                    <PolarGrid stroke="rgba(255,255,255,0.08)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 13, fontWeight: 600 }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
                    <Radar
                      name="Score"
                      dataKey="score"
                      stroke="#00f5ff"
                      fill="#00f5ff"
                      fillOpacity={0.15}
                      strokeWidth={2}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </motion.div>

              {/* Line chart */}
              <motion.div
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.35 }}
                className="glass-card p-6"
              >
                <h3 className="text-lg font-bold mb-6 flex items-center gap-2">
                  <TrendingUp size={20} className="text-cyan-400" />
                  Score Progress Over Time
                </h3>
                <ResponsiveContainer width="100%" height={260}>
                  <LineChart data={stats.score_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
                    <XAxis dataKey="date" tick={{ fill: '#64748b', fontSize: 11 }} />
                    <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 11 }} />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="score"
                      name="Final Score"
                      stroke="#00f5ff"
                      strokeWidth={2.5}
                      dot={{ fill: '#00f5ff', strokeWidth: 2, r: 4 }}
                      activeDot={{ r: 6, fill: '#00f5ff' }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </motion.div>
            </div>

            {/* Module averages */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="glass-card p-6 mb-6"
            >
              <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
                <Award size={20} className="text-cyan-400" />
                All-Time Module Averages
              </h3>
              <div className="grid md:grid-cols-3 gap-6">
                {[
                  { label: 'Vision', value: stats.module_averages.vision, color: 'from-cyan-400 to-cyan-600', icon: <Eye size={16} className="text-cyan-400" /> },
                  { label: 'Audio', value: stats.module_averages.audio, color: 'from-purple-400 to-purple-600', icon: <Mic size={16} className="text-purple-400" /> },
                  { label: 'NLP', value: stats.module_averages.nlp, color: 'from-blue-400 to-blue-600', icon: <MessageSquare size={16} className="text-blue-400" /> },
                ].map((m) => (
                  <div key={m.label}>
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-1.5">{m.icon}<span className="text-sm text-gray-300 font-medium">{m.label}</span></div>
                      <span className="text-sm font-bold text-white">{m.value}</span>
                    </div>
                    <div className="w-full bg-white/5 rounded-full h-2">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${m.value}%` }}
                        transition={{ duration: 0.8, ease: 'easeOut', delay: 0.5 }}
                        className={`h-2 rounded-full bg-gradient-to-r ${m.color}`}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>

            {/* Recent history */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="glass-card p-6"
            >
              <div className="flex items-center justify-between mb-5">
                <h3 className="text-lg font-bold flex items-center gap-2">
                  <Clock size={20} className="text-cyan-400" />
                  Recent Interviews
                </h3>
                <Link to="/history" className="text-sm text-cyan-400 hover:text-cyan-300 flex items-center gap-1 transition-colors">
                  View all <ChevronRight size={14} />
                </Link>
              </div>
              <div className="space-y-3">
                {history.slice(0, 5).map((item) => (
                  <Link
                    key={item.id}
                    to={`/report/${item.id}`}
                    className="flex items-center justify-between p-4 rounded-xl bg-white/3 border border-white/5 hover:border-cyan-400/20 hover:bg-white/5 transition-all group"
                  >
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-cyan-400/10 flex items-center justify-center">
                        <Brain size={16} className="text-cyan-400" />
                      </div>
                      <div>
                        <p className="font-semibold text-sm">{item.interview_type}{item.track ? ` · ${item.track}` : ''}</p>
                        <p className="text-xs text-gray-500">{new Date(item.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-lg font-black text-white">{item.final_score?.toFixed(1)}</span>
                      <span className={`text-xs px-2.5 py-1 rounded-full border font-medium ${verdictBadge(item.verdict)}`}>
                        {item.verdict}
                      </span>
                      <ChevronRight size={16} className="text-gray-600 group-hover:text-cyan-400 transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            </motion.div>
          </>
        )}
      </div>
    </div>
  )
}
