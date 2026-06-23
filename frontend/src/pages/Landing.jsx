import React from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, Eye, Mic, MessageSquare, ChevronRight, Star, Zap, Shield, BarChart3 } from 'lucide-react'

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 30 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay },
})

const FloatingOrb = ({ className }) => (
  <div className={`absolute rounded-full blur-3xl pointer-events-none ${className}`} />
)

export default function Landing() {
  const features = [
    {
      icon: <Eye size={28} className="text-cyan-400" />,
      title: 'Vision AI',
      desc: 'Analyses your eye contact, facial expressions, and body posture in real time to score your non-verbal communication.',
      weight: '35%',
    },
    {
      icon: <Mic size={28} className="text-purple-400" />,
      title: 'Audio AI',
      desc: 'Evaluates speech clarity, speaking pace (WPM), pause patterns, and vocal confidence to measure your delivery.',
      weight: '30%',
    },
    {
      icon: <MessageSquare size={28} className="text-blue-400" />,
      title: 'NLP AI',
      desc: 'Transcribes your answers and rates content quality, keyword relevance, coherence, and filler word usage.',
      weight: '35%',
    },
  ]

  const steps = [
    { n: '01', title: 'Choose Your Track', desc: 'Select from HR, Leadership, or Technical interviews across 4 specialisations.' },
    { n: '02', title: 'Record Your Interview', desc: 'Answer AI-curated questions on camera with a live timer and question navigator.' },
    { n: '03', title: 'Get AI Feedback', desc: 'Three independent AI systems analyse your performance and fuse results into an actionable report.' },
  ]

  const stats = [
    { label: 'AI Modules', value: '3', suffix: '' },
    { label: 'Questions Bank', value: '30', suffix: '+' },
    { label: 'Interview Tracks', value: '6', suffix: '' },
    { label: 'Score Dimensions', value: '10', suffix: '+' },
  ]

  return (
    <div className="gradient-bg min-h-screen">
      {/* Hero */}
      <section className="relative pt-32 pb-24 px-4 overflow-hidden">
        <FloatingOrb className="w-[500px] h-[500px] bg-cyan-500/8 -top-40 -left-40" />
        <FloatingOrb className="w-[400px] h-[400px] bg-blue-600/10 top-20 -right-32" />
        <FloatingOrb className="w-[300px] h-[300px] bg-purple-600/8 bottom-0 left-1/3" />

        <div className="max-w-5xl mx-auto text-center relative z-10">
          <motion.div {...fadeUp(0)} className="inline-flex items-center gap-2 glass px-4 py-2 rounded-full mb-8 border border-cyan-400/20">
            <Zap size={14} className="text-cyan-400" />
            <span className="text-sm text-cyan-400 font-medium">AI-Powered • Real-Time • Multi-Modal Analysis</span>
          </motion.div>

          <motion.h1 {...fadeUp(0.1)} className="text-5xl md:text-7xl font-black mb-6 leading-tight tracking-tight">
            Master Your Interview.
            <br />
            <span className="neon-text">Get Hired.</span>
          </motion.h1>

          <motion.p {...fadeUp(0.2)} className="text-xl text-gray-400 max-w-2xl mx-auto mb-10 leading-relaxed">
            InterviewIQ deploys three independent AI systems — Vision, Audio, and NLP — to evaluate your performance and deliver a precise, actionable score with personalised recommendations.
          </motion.p>

          <motion.div {...fadeUp(0.3)} className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link to="/register" className="btn-primary text-base px-8 py-3.5 inline-flex items-center gap-2">
              Start Free Interview <ChevronRight size={18} />
            </Link>
            <Link to="/login" className="btn-secondary text-base px-8 py-3.5">
              Sign In
            </Link>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="py-12 px-4 border-y border-white/5">
        <div className="max-w-4xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6">
          {stats.map((s, i) => (
            <motion.div key={i} {...fadeUp(i * 0.1)} className="text-center">
              <p className="text-4xl font-black neon-text">{s.value}{s.suffix}</p>
              <p className="text-gray-400 text-sm mt-1">{s.label}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* AI Modules */}
      <section className="py-24 px-4">
        <div className="max-w-6xl mx-auto">
          <motion.div {...fadeUp()} className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-black mb-4">Three Independent AI Systems</h2>
            <p className="text-gray-400 max-w-xl mx-auto">Each module operates autonomously, ensuring modular, unbiased evaluation that can be upgraded independently.</p>
          </motion.div>

          <div className="grid md:grid-cols-3 gap-6">
            {features.map((f, i) => (
              <motion.div
                key={i}
                {...fadeUp(i * 0.15)}
                className="glass-card p-8 hover:border-cyan-400/30 transition-all duration-300 group"
              >
                <div className="mb-5 p-3 w-fit rounded-xl bg-white/5 border border-white/8 group-hover:scale-110 transition-transform">
                  {f.icon}
                </div>
                <div className="flex items-center gap-2 mb-3">
                  <h3 className="text-xl font-bold">{f.title}</h3>
                  <span className="text-xs bg-cyan-400/10 text-cyan-400 border border-cyan-400/20 px-2 py-0.5 rounded-full font-mono">
                    {f.weight}
                  </span>
                </div>
                <p className="text-gray-400 leading-relaxed text-sm">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="py-24 px-4 border-t border-white/5">
        <div className="max-w-4xl mx-auto">
          <motion.div {...fadeUp()} className="text-center mb-16">
            <h2 className="text-3xl md:text-4xl font-black mb-4">How It Works</h2>
            <p className="text-gray-400">Three steps from sign-up to a detailed performance report.</p>
          </motion.div>

          <div className="space-y-6">
            {steps.map((s, i) => (
              <motion.div
                key={i}
                {...fadeUp(i * 0.15)}
                className="glass-card p-6 flex items-start gap-6 hover:border-cyan-400/25 transition-all"
              >
                <div className="flex-shrink-0 w-12 h-12 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
                  <span className="text-cyan-400 font-black text-sm font-mono">{s.n}</span>
                </div>
                <div>
                  <h3 className="text-lg font-bold mb-1">{s.title}</h3>
                  <p className="text-gray-400 text-sm leading-relaxed">{s.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4">
        <motion.div
          {...fadeUp()}
          className="max-w-3xl mx-auto glass-card p-12 text-center neon-border"
        >
          <Brain size={48} className="text-cyan-400 mx-auto mb-6 animate-float" />
          <h2 className="text-3xl md:text-4xl font-black mb-4">Ready to Ace Your Next Interview?</h2>
          <p className="text-gray-400 mb-8 max-w-lg mx-auto">Join InterviewIQ and get AI-powered feedback that turns nervous candidates into confident professionals.</p>
          <Link to="/register" className="btn-primary text-base px-10 py-4 inline-flex items-center gap-2">
            Create Free Account <ChevronRight size={18} />
          </Link>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-8 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Brain size={18} className="text-cyan-400" />
            <span className="font-bold neon-text">InterviewIQ</span>
          </div>
          <p className="text-gray-500 text-sm">© 2024 InterviewIQ. AI-Powered Mock Interview Platform.</p>
        </div>
      </footer>
    </div>
  )
}
