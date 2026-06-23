import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, Upload, Cpu, BarChart3, Sparkles, Check, AlertCircle } from 'lucide-react'
import api from '../api/axios'

const STEPS = [
  { icon: Upload, label: 'Uploading your recording' },
  { icon: Cpu, label: 'Analysing visual cues & expressions' },
  { icon: Brain, label: 'Processing speech & audio quality' },
  { icon: BarChart3, label: 'Evaluating answer content & relevance' },
  { icon: Sparkles, label: 'Generating your personalised report' },
]

const sleep = (ms) => new Promise(r => setTimeout(r, ms))

export default function Processing() {
  const location = useLocation()
  const navigate = useNavigate()
  const { interview_type, track, blob } = location.state || {}
  const [step, setStep] = useState(0)
  const [error, setError] = useState(null)
  const ran = useRef(false)

  useEffect(() => {
    if (!interview_type || !blob) {
      navigate('/interview/type')
      return
    }
    if (ran.current) return
    ran.current = true

    const run = async () => {
      try {
        const { data: interview } = await api.post('/interviews/start-interview', {
          interview_type,
          track: track || null,
        })
        const id = interview.id

        setStep(1)
        const formData = new FormData()
        formData.append('video', new File([blob], 'interview.webm', { type: blob.type || 'video/webm' }))
        await api.post(`/interviews/upload-video/${id}`, formData, {
          headers: { 'Content-Type': 'multipart/form-data' },
          timeout: 120000,
        })

        setStep(2)
        await sleep(600)

        setStep(3)
        await sleep(500)

        setStep(4)
        await api.post(`/interviews/analyze/${id}`)

        setStep(5)
        await sleep(700)

        navigate(`/report/${id}`)
      } catch (e) {
        console.error(e)
        setError('Something went wrong during analysis. Please try again.')
      }
    }

    run()
  }, [])

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
        <div className="glass-card p-10 max-w-md text-center">
          <AlertCircle size={48} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-3">Analysis Failed</h2>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">{error}</p>
          <button onClick={() => navigate('/interview/type')} className="btn-primary">Try Again</button>
        </div>
      </div>
    )
  }

  const progressPercent = Math.min((step / STEPS.length) * 100, 100)

  return (
    <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
      <div className="glass-card p-10 max-w-md w-full">
        <div className="text-center mb-10">
          <div className="w-20 h-20 rounded-2xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center mx-auto mb-5">
            <Brain size={36} className="text-cyan-400 animate-pulse" />
          </div>
          <h2 className="text-2xl font-black mb-2">Analysing your interview</h2>
          <p className="text-gray-400 text-sm">Our AI is processing your performance. This takes a few seconds.</p>
        </div>

        <div className="space-y-3 mb-8">
          {STEPS.map((s, i) => {
            const done = step > i
            const active = step === i
            const Icon = s.icon
            return (
              <motion.div
                key={i}
                initial={{ opacity: 0, x: -15 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.07 }}
                className={`flex items-center gap-4 p-3.5 rounded-xl transition-all duration-500 ${
                  done ? 'bg-cyan-400/8 border border-cyan-400/20' :
                  active ? 'bg-white/5 border border-white/10' :
                  'opacity-25'
                }`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 transition-all duration-300 ${
                  done ? 'bg-cyan-400 text-black' :
                  active ? 'bg-white/10 text-cyan-400 border border-cyan-400/40' :
                  'bg-white/5 text-gray-600'
                }`}>
                  {done ? <Check size={15} /> : <Icon size={15} />}
                </div>
                <span className={`text-sm font-medium transition-colors ${
                  done ? 'text-cyan-400' : active ? 'text-white' : 'text-gray-600'
                }`}>
                  {s.label}
                </span>
                {active && (
                  <div className="ml-auto w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
                )}
              </motion.div>
            )
          })}
        </div>

        <div className="w-full bg-white/5 rounded-full h-1.5 overflow-hidden">
          <motion.div
            className="h-1.5 rounded-full bg-gradient-to-r from-cyan-400 to-blue-500"
            animate={{ width: `${progressPercent}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
        <p className="text-center text-xs text-gray-600 mt-2">{Math.round(progressPercent)}% complete</p>
      </div>
    </div>
  )
}
