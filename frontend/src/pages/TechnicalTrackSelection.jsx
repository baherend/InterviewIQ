import React from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Database, BrainCircuit, Shield, Terminal, ChevronRight, Brain, ArrowLeft } from 'lucide-react'

const tracks = [
  {
    id: 'Data Analysis',
    title: 'Data Analysis',
    icon: <Database size={34} className="text-cyan-400" />,
    desc: 'SQL queries, data normalisation, aggregation functions, handling missing data, and statistical methods.',
    topics: ['SQL Joins & Queries', 'GROUP BY & HAVING', 'Missing Value Handling', 'Descriptive Statistics'],
    color: 'hover:border-cyan-400/40',
    iconBg: 'bg-cyan-400/10 border-cyan-400/20',
  },
  {
    id: 'Data Science',
    title: 'Data Science',
    icon: <BrainCircuit size={34} className="text-purple-400" />,
    desc: 'Machine learning fundamentals covering supervised/unsupervised learning, model evaluation, and common pitfalls.',
    topics: ['Overfitting & Regularisation', 'Cross-Validation', 'Bias-Variance Tradeoff', 'Classification vs Regression'],
    color: 'hover:border-purple-400/40',
    iconBg: 'bg-purple-400/10 border-purple-400/20',
  },
  {
    id: 'Cybersecurity',
    title: 'Cybersecurity',
    icon: <Shield size={34} className="text-green-400" />,
    desc: 'Core security principles including the CIA Triad, common attack vectors, authentication, and network defences.',
    topics: ['CIA Triad', 'SQL Injection', 'Auth vs Authorisation', 'Phishing & Social Engineering'],
    color: 'hover:border-green-400/40',
    iconBg: 'bg-green-400/10 border-green-400/20',
  },
  {
    id: 'Software Engineering',
    title: 'Software Engineering',
    icon: <Terminal size={34} className="text-blue-400" />,
    desc: 'OOP principles, data structures, REST APIs, database paradigms, and version control best practices.',
    topics: ['OOP Pillars', 'Stack vs Queue', 'REST API Principles', 'SQL vs NoSQL & Git'],
    color: 'hover:border-blue-400/40',
    iconBg: 'bg-blue-400/10 border-blue-400/20',
  },
]

export default function TechnicalTrackSelection() {
  const navigate = useNavigate()
  const location = useLocation()
  const interviewType = location.state?.interview_type || 'Technical'

  const handleSelect = (track) => {
    navigate('/interview/room', { state: { interview_type: interviewType, track: track.id } })
  }

  return (
    <div className="gradient-bg min-h-screen pt-24 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <button
            onClick={() => navigate('/interview/type')}
            className="inline-flex items-center gap-2 text-gray-400 hover:text-cyan-400 transition-colors text-sm mb-6"
          >
            <ArrowLeft size={16} />
            Back to Interview Type
          </button>

          <div className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-6 border border-cyan-400/20 block">
            <Brain size={14} className="text-cyan-400" />
            <span className="text-sm text-cyan-400 font-medium">Step 2 of 2 — Choose Technical Track</span>
          </div>
          <h1 className="text-4xl font-black mb-3">Choose your specialisation</h1>
          <p className="text-gray-400 max-w-xl mx-auto">Select the technical domain that matches your role or the area you want to strengthen.</p>
        </motion.div>

        <div className="grid md:grid-cols-2 gap-6">
          {tracks.map((track, i) => (
            <motion.button
              key={track.id}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.1 }}
              onClick={() => handleSelect(track)}
              className={`glass-card p-7 text-left w-full transition-all duration-300 group border border-white/7 ${track.color} hover:scale-[1.02] hover:shadow-neon`}
            >
              <div className="flex items-start gap-5">
                <div className={`w-16 h-16 ${track.iconBg} border rounded-2xl flex items-center justify-center flex-shrink-0 group-hover:scale-110 transition-transform`}>
                  {track.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-black">{track.title}</h2>
                    <ChevronRight size={18} className="text-gray-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
                  </div>
                  <p className="text-gray-400 text-sm leading-relaxed mt-2 mb-4">{track.desc}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {track.topics.map((topic) => (
                      <span key={topic} className="text-xs bg-white/5 border border-white/8 px-2.5 py-1 rounded-full text-gray-400">
                        {topic}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  )
}
