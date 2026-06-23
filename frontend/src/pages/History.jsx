import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, ChevronRight, PlayCircle, Filter, Eye, Mic, MessageSquare } from 'lucide-react'
import api from '../api/axios'

const verdictStyle = (verdict) => ({
  Excellent: 'bg-cyan-400/15 text-cyan-400 border-cyan-400/30',
  Pass: 'bg-blue-400/15 text-blue-400 border-blue-400/30',
  'Needs Improvement': 'bg-yellow-400/15 text-yellow-400 border-yellow-400/30',
  Fail: 'bg-red-400/15 text-red-400 border-red-400/30',
}[verdict] || 'bg-gray-400/15 text-gray-400 border-gray-400/30')

const MODULE_BARS = [
  { key: 'vision_score', label: 'V', color: 'bg-cyan-400', title: 'Vision' },
  { key: 'audio_score', label: 'A', color: 'bg-purple-400', title: 'Audio' },
  { key: 'nlp_score', label: 'N', color: 'bg-blue-400', title: 'NLP' },
]

const FILTERS = ['All', 'HR', 'Leadership', 'Technical']

export default function History() {
  const navigate = useNavigate()
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('All')

  useEffect(() => {
    api.get('/dashboard/history')
      .then(res => setHistory(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }, [])

  const filtered = filter === 'All' ? history : history.filter(h => h.interview_type === filter)

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg">
        <div className="w-14 h-14 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin" />
      </div>
    )
  }

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8"
        >
          <div>
            <h1 className="text-3xl font-black">Interview History</h1>
            <p className="text-gray-400 mt-1">
              {history.length} interview{history.length !== 1 ? 's' : ''} completed
            </p>
          </div>
          <button
            onClick={() => navigate('/interview/type')}
            className="btn-primary flex items-center gap-2 text-sm py-2.5 px-5 shrink-0"
          >
            <PlayCircle size={16} /> New Interview
          </button>
        </motion.div>

        {/* Filters */}
        <div className="flex items-center gap-2 mb-6 flex-wrap">
          <Filter size={14} className="text-gray-500 flex-shrink-0" />
          {FILTERS.map(type => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3.5 py-1.5 rounded-lg text-sm font-medium transition-all ${
                filter === type
                  ? 'bg-cyan-400/15 text-cyan-400 border border-cyan-400/30'
                  : 'text-gray-400 glass border border-white/5 hover:border-white/10 hover:text-white'
              }`}
            >
              {type}
            </button>
          ))}
        </div>

        {/* List */}
        {filtered.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="glass-card p-16 text-center"
          >
            <Brain size={48} className="text-gray-700 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-400 mb-2">No interviews found</h3>
            <p className="text-gray-600 text-sm">
              {filter !== 'All'
                ? `No ${filter} interviews yet. Try a different filter or start one.`
                : 'Complete your first interview to see your history here.'}
            </p>
          </motion.div>
        ) : (
          <div className="space-y-3">
            {filtered.map((item, i) => (
              <motion.div
                key={item.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Link
                  to={`/report/${item.id}`}
                  className="flex items-center gap-4 p-5 glass-card hover:border-cyan-400/25 transition-all group"
                >
                  <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center flex-shrink-0">
                    <Brain size={18} className="text-cyan-400" />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <p className="font-semibold text-sm">
                        {item.interview_type}{item.track ? ` · ${item.track}` : ''}
                      </p>
                      {item.verdict && (
                        <span className={`text-xs px-2 py-0.5 rounded-full border font-medium flex-shrink-0 ${verdictStyle(item.verdict)}`}>
                          {item.verdict}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mb-2">
                      {new Date(item.created_at).toLocaleDateString('en-US', {
                        weekday: 'short', year: 'numeric', month: 'short', day: 'numeric',
                      })}
                    </p>
                    <div className="flex items-center gap-3">
                      {MODULE_BARS.map(m => (
                        <div key={m.key} className="flex items-center gap-1.5 flex-1" title={`${m.title}: ${item[m.key]?.toFixed(1) ?? '—'}`}>
                          <span className="text-xs text-gray-600 w-3">{m.label}</span>
                          <div className="flex-1 bg-white/5 rounded-full h-1">
                            <div
                              className={`h-1 rounded-full ${m.color}`}
                              style={{ width: `${item[m.key] ?? 0}%` }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-2xl font-black text-white">
                      {item.final_score?.toFixed(1) ?? '—'}
                    </span>
                    <ChevronRight size={18} className="text-gray-600 group-hover:text-cyan-400 transition-colors" />
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
