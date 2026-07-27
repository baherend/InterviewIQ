import React from 'react'
import { motion } from 'framer-motion'
import { ClipboardCheck, Video, BarChart3, Building2 } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import OrganizationMembershipSummary from '../components/OrganizationMembershipSummary'

const ComingSoonCard = ({ icon, title, note }) => (
  <div className="glass-card p-6">
    <div className="flex items-center gap-2 mb-2">
      {icon}
      <h3 className="text-lg font-bold">{title}</h3>
      <span className="text-xs bg-white/5 border border-white/10 text-gray-400 px-2 py-0.5 rounded-full ml-auto">
        Coming soon
      </span>
    </div>
    <p className="text-gray-400 text-sm leading-relaxed">{note}</p>
  </div>
)

export default function InterviewerDashboard() {
  const { user } = useAuth()

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-3 mb-8"
        >
          <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
            <ClipboardCheck size={20} className="text-cyan-400" />
          </div>
          <div>
            <h1 className="text-3xl font-black">Interviewer</h1>
            <p className="text-gray-400 text-sm mt-0.5">Signed in as {user?.name}</p>
          </div>
        </motion.div>

        <div className="mb-6">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-3 flex items-center gap-2">
            <Building2 size={14} /> Organization Membership
          </h2>
          <OrganizationMembershipSummary />
        </div>

        <div className="grid md:grid-cols-3 gap-5">
          <ComingSoonCard
            icon={<ClipboardCheck size={20} className="text-cyan-400" />}
            title="Assigned Assessments"
            note="Assessments assigned to you by your organization."
          />
          <ComingSoonCard
            icon={<Video size={20} className="text-cyan-400" />}
            title="Interview Sessions"
            note="Interview sessions you're running or scheduled for."
          />
          <ComingSoonCard
            icon={<BarChart3 size={20} className="text-cyan-400" />}
            title="Candidate Results"
            note="Scores and reports for candidates you've interviewed."
          />
        </div>
      </div>
    </div>
  )
}
