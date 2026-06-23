import React from 'react'
import { motion } from 'framer-motion'

const getScoreColor = (score) => {
  if (score >= 85) return { bar: 'from-cyan-400 to-green-400', text: 'text-cyan-400', bg: 'bg-cyan-400/10' }
  if (score >= 70) return { bar: 'from-blue-400 to-purple-400', text: 'text-blue-400', bg: 'bg-blue-400/10' }
  if (score >= 50) return { bar: 'from-yellow-400 to-orange-400', text: 'text-yellow-400', bg: 'bg-yellow-400/10' }
  return { bar: 'from-red-500 to-red-700', text: 'text-red-400', bg: 'bg-red-400/10' }
}

export default function ScoreCard({ title, score, icon, subtitle, delay = 0 }) {
  const colors = getScoreColor(score ?? 0)
  const displayScore = score != null ? score.toFixed(1) : '—'

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      className="glass-card p-6 hover:border-cyan-400/25 transition-all duration-300"
    >
      <div className="flex items-start justify-between mb-5">
        <div>
          <p className="text-gray-400 text-sm font-medium mb-1">{title}</p>
          <p className={`text-4xl font-black ${colors.text}`}>{displayScore}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-3 rounded-xl ${colors.bg} border border-white/5`}>
          {icon}
        </div>
      </div>

      <div className="space-y-1.5">
        <div className="flex justify-between text-xs text-gray-500">
          <span>Score</span>
          <span>{displayScore} / 100</span>
        </div>
        <div className="w-full bg-white/5 rounded-full h-2 overflow-hidden">
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: `${score ?? 0}%` }}
            transition={{ delay: delay + 0.3, duration: 0.8, ease: 'easeOut' }}
            className={`h-2 rounded-full bg-gradient-to-r ${colors.bar}`}
          />
        </div>
      </div>
    </motion.div>
  )
}
