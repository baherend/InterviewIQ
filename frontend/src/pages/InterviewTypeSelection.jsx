import React from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Users, TrendingUp, Code, ChevronRight, Brain } from 'lucide-react'

const types = [
  {
    id: 'HR',
    title: 'HR Interview',
    icon: <Users size={36} className="text-cyan-400" />,
    desc: 'Behavioural and situational questions covering your background, motivations, and cultural fit.',
    questions: 5,
    duration: '10–15 min',
    color: 'hover:border-cyan-400/40',
    iconBg: 'bg-cyan-400/10 border-cyan-400/20',
    tags: ['Tell me about yourself', 'Strengths & Weaknesses', 'Career Goals'],
  },
  {
    id: 'Leadership',
    title: 'Leadership Interview',
    icon: <TrendingUp size={36} className="text-purple-400" />,
    desc: 'Scenario-based questions assessing your leadership style, conflict resolution, and team motivation.',
    questions: 5,
    duration: '15–20 min',
    color: 'hover:border-purple-400/40',
    iconBg: 'bg-purple-400/10 border-purple-400/20',
    tags: ['Team Management', 'Conflict Resolution', 'Decision Making'],
  },
  {
    id: 'Technical',
    title: 'Technical Interview',
    icon: <Code size={36} className="text-blue-400" />,
    desc: 'Role-specific technical questions across Data Analysis, Data Science, Cybersecurity, and Software Engineering.',
    questions: 5,
    duration: '20–30 min',
    color: 'hover:border-blue-400/40',
    iconBg: 'bg-blue-400/10 border-blue-400/20',
    tags: ['Choose Your Track', 'Domain-Specific', 'In-Depth Q&A'],
  },
]

export default function InterviewTypeSelection() {
  const navigate = useNavigate()

  const handleSelect = (type) => {
    if (type.id === 'Technical') {
      navigate('/interview/track', { state: { interview_type: type.id } })
    } else {
      navigate('/interview/room', { state: { interview_type: type.id, track: null } })
    }
  }

  return (
    <div className="gradient-bg min-h-screen pt-24 pb-12 px-4">
      <div className="max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="text-center mb-12"
        >
          <div className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-6 border border-cyan-400/20">
            <Brain size={14} className="text-cyan-400" />
            <span className="text-sm text-cyan-400 font-medium">Step 1 of 2 — Choose Interview Type</span>
          </div>
          <h1 className="text-4xl font-black mb-3">What type of interview?</h1>
          <p className="text-gray-400 max-w-lg mx-auto">Select the interview category that best matches your upcoming interview or the skill you want to practice.</p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-6">
          {types.map((type, i) => (
            <motion.button
              key={type.id}
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.12 }}
              onClick={() => handleSelect(type)}
              className={`glass-card p-7 text-left w-full transition-all duration-300 group border border-white/7 ${type.color} hover:scale-[1.02] hover:shadow-neon`}
            >
              <div className={`w-16 h-16 ${type.iconBg} border rounded-2xl flex items-center justify-center mb-5 group-hover:scale-110 transition-transform`}>
                {type.icon}
              </div>

              <h2 className="text-xl font-black mb-2">{type.title}</h2>
              <p className="text-gray-400 text-sm leading-relaxed mb-5">{type.desc}</p>

              <div className="flex items-center gap-3 mb-5 text-xs text-gray-500">
                <span className="glass px-2.5 py-1 rounded-full">{type.questions} Questions</span>
                <span className="glass px-2.5 py-1 rounded-full">{type.duration}</span>
              </div>

              <div className="flex flex-wrap gap-1.5 mb-6">
                {type.tags.map((tag) => (
                  <span key={tag} className="text-xs bg-white/5 border border-white/8 px-2.5 py-1 rounded-full text-gray-400">
                    {tag}
                  </span>
                ))}
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-gray-300">Select this type</span>
                <ChevronRight size={18} className="text-gray-500 group-hover:text-cyan-400 group-hover:translate-x-1 transition-all" />
              </div>
            </motion.button>
          ))}
        </div>
      </div>
    </div>
  )
}
