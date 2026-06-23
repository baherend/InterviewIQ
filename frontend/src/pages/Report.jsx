import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer,
} from 'recharts'
import {
  Eye, Mic, MessageSquare, Brain, PlayCircle, ArrowLeft, Award,
  AlertTriangle, Clock, TrendingUp, FileText, Volume2, Zap,
} from 'lucide-react'
import api from '../api/axios'
import ScoreCard from '../components/ScoreCard'

const verdictStyle = (verdict) => ({
  Excellent: 'bg-cyan-400/15 text-cyan-400 border-cyan-400/30',
  Pass: 'bg-blue-400/15 text-blue-400 border-blue-400/30',
  'Needs Improvement': 'bg-yellow-400/15 text-yellow-400 border-yellow-400/30',
  Fail: 'bg-red-400/15 text-red-400 border-red-400/30',
}[verdict] || 'bg-gray-400/15 text-gray-400 border-gray-400/30')

const scoreTextColor = (s) => {
  if (s >= 85) return 'text-cyan-400'
  if (s >= 70) return 'text-blue-400'
  if (s >= 50) return 'text-yellow-400'
  return 'text-red-400'
}

export default function Report() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    api.get(`/interviews/report/${id}`)
      .then(res => setData(res.data))
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg">
        <div className="w-14 h-14 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
        <div className="glass-card p-10 max-w-md text-center">
          <AlertTriangle size={44} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-3">Report Not Found</h2>
          <p className="text-gray-400 text-sm mb-6">This report may not exist or you may not have access.</p>
          <button onClick={() => navigate('/dashboard')} className="btn-primary">Go to Dashboard</button>
        </div>
      </div>
    )
  }

  const { interview, result } = data

  const radarData = [
    { subject: 'Vision', score: result.vision_score ?? 0 },
    { subject: 'Audio', score: result.audio_score ?? 0 },
    { subject: 'NLP', score: result.nlp_score ?? 0 },
  ]

  const metrics = [
    { label: 'Dominant Emotion', value: result.emotion || '—', icon: <Brain size={15} className="text-cyan-400" /> },
    { label: 'Eye Contact', value: result.eye_contact != null ? `${(result.eye_contact * 100).toFixed(0)}%` : '—', icon: <Eye size={15} className="text-purple-400" /> },
    { label: 'Speaking Pace', value: result.wpm != null ? `${result.wpm.toFixed(0)} WPM` : '—', icon: <Volume2 size={15} className="text-blue-400" /> },
    { label: 'Pause Count', value: result.pause_count != null ? `${result.pause_count} pauses` : '—', icon: <Clock size={15} className="text-yellow-400" /> },
    { label: 'Filler Words', value: result.filler_count != null ? `${result.filler_count} detected` : '—', icon: <MessageSquare size={15} className="text-orange-400" /> },
  ]

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-5xl mx-auto">
        <Link to="/history" className="inline-flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors text-sm mb-6">
          <ArrowLeft size={15} /> Back to History
        </Link>

        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-7 mb-6"
        >
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
            <div>
              <div className="flex items-center gap-3 mb-3">
                <div className="w-12 h-12 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
                  <Brain size={22} className="text-cyan-400" />
                </div>
                <div>
                  <h1 className="text-2xl font-black">Interview Report</h1>
                  <p className="text-gray-400 text-sm">
                    {interview.interview_type}{interview.track ? ` · ${interview.track}` : ''}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-500">
                <Clock size={14} />
                <span>
                  {new Date(interview.created_at).toLocaleDateString('en-US', {
                    weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
                  })}
                </span>
              </div>
            </div>
            <div className="text-right flex-shrink-0">
              <p className={`text-6xl font-black ${scoreTextColor(interview.final_score)}`}>
                {interview.final_score?.toFixed(1) ?? '—'}
              </p>
              <span className={`text-sm px-3 py-1.5 rounded-full border font-medium mt-2 inline-block ${verdictStyle(interview.verdict)}`}>
                {interview.verdict || '—'}
              </span>
            </div>
          </div>
        </motion.div>

        {/* Score cards */}
        <div className="grid md:grid-cols-3 gap-4 mb-6">
          <ScoreCard
            title="Vision Score"
            score={result.vision_score}
            icon={<Eye size={22} className="text-cyan-400" />}
            subtitle="Facial expression & eye contact"
            delay={0}
          />
          <ScoreCard
            title="Audio Score"
            score={result.audio_score}
            icon={<Mic size={22} className="text-purple-400" />}
            subtitle="Pace, clarity & confidence"
            delay={0.1}
          />
          <ScoreCard
            title="NLP Score"
            score={result.nlp_score}
            icon={<MessageSquare size={22} className="text-blue-400" />}
            subtitle="Content quality & relevance"
            delay={0.2}
          />
        </div>

        <div className="grid lg:grid-cols-2 gap-6 mb-6">
          {/* Radar */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.3 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
              <TrendingUp size={20} className="text-cyan-400" /> Performance Radar
            </h3>
            <ResponsiveContainer width="100%" height={220}>
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

          {/* Metrics */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.35 }}
            className="glass-card p-6"
          >
            <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
              <Zap size={20} className="text-cyan-400" /> Detailed Metrics
            </h3>
            <div className="space-y-3.5">
              {metrics.map(m => (
                <div key={m.label} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                  <div className="flex items-center gap-2.5">
                    {m.icon}
                    <span className="text-sm text-gray-400">{m.label}</span>
                  </div>
                  <span className="text-sm font-semibold text-white">{m.value}</span>
                </div>
              ))}
            </div>
          </motion.div>
        </div>

        {/* Transcript */}
        {result.transcript && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass-card p-6 mb-6"
          >
            <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
              <FileText size={20} className="text-cyan-400" /> Sample Transcript
            </h3>
            <p className="text-gray-300 text-sm leading-relaxed italic">"{result.transcript}"</p>
          </motion.div>
        )}

        {/* Recommendations */}
        {result.recommendations?.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.45 }}
            className="glass-card p-6 mb-8"
          >
            <h3 className="text-lg font-bold mb-5 flex items-center gap-2 flex-wrap">
              <Award size={20} className="text-cyan-400" />
              Recommendations
              {result.weakest_module && (
                <span className="text-xs bg-yellow-400/10 text-yellow-400 border border-yellow-400/20 px-2.5 py-1 rounded-full ml-1">
                  Focus area: {result.weakest_module}
                </span>
              )}
            </h3>
            <ul className="space-y-3.5">
              {result.recommendations.map((rec, i) => (
                <li key={i} className="flex gap-3 text-sm text-gray-300 leading-relaxed">
                  <span className="w-6 h-6 rounded-full bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center text-cyan-400 text-xs font-bold flex-shrink-0 mt-0.5">
                    {i + 1}
                  </span>
                  {rec}
                </li>
              ))}
            </ul>
          </motion.div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={() => navigate('/interview/type')}
            className="btn-primary flex items-center gap-2 justify-center"
          >
            <PlayCircle size={18} /> Start New Interview
          </button>
          <Link to="/history" className="btn-secondary flex items-center gap-2 justify-center">
            <Clock size={18} /> View All History
          </Link>
        </div>
      </div>
    </div>
  )
}
