import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Brain, CheckCircle2, AlertCircle, Clock, RefreshCw, MinusCircle } from 'lucide-react'
import api from '../api/axios'

const TERMINAL_STATUSES = new Set(['completed', 'partial', 'failed', 'insufficient_evidence'])
const POLL_INTERVAL_MS = 2000

const STATUS_META = {
  pending: { label: 'Waiting to analyze', icon: Clock, className: 'text-gray-500' },
  processing: { label: 'Analyzing…', icon: Brain, className: 'text-cyan-400' },
  completed: { label: 'Analyzed', icon: CheckCircle2, className: 'text-cyan-400' },
  partial: { label: 'Partially analyzed', icon: MinusCircle, className: 'text-yellow-400' },
  insufficient_evidence: { label: 'Insufficient evidence', icon: MinusCircle, className: 'text-yellow-400' },
  failed: { label: 'Analysis failed', icon: AlertCircle, className: 'text-red-400' },
}

export default function Processing() {
  const location = useLocation()
  const navigate = useNavigate()
  const { interviewId } = location.state || {}
  const [status, setStatus] = useState(null)
  const [error, setError] = useState(null)
  const [retrying, setRetrying] = useState(null)
  const startedRef = useRef(false)
  const pollRef = useRef(null)

  const pollOnce = async () => {
    try {
      const { data } = await api.get(`/interviews/${interviewId}/processing-status`)
      setStatus(data)
      if (data.all_terminal) {
        if (pollRef.current) clearInterval(pollRef.current)
        setTimeout(() => navigate(`/report/${interviewId}`), 800)
      }
    } catch (e) {
      console.error(e)
      setError('Could not check analysis status. Please try again.')
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }

  useEffect(() => {
    if (!interviewId) {
      navigate('/interview/type')
      return
    }
    if (startedRef.current) return
    startedRef.current = true

    const run = async () => {
      try {
        // Idempotent: safe even if a previous attempt already queued
        // processing (e.g. after a retry or a re-mount).
        await api.post(`/interviews/${interviewId}/process-audio`)
      } catch (e) {
        console.error(e)
        setError('Could not start audio analysis. Please try again.')
        return
      }
      await pollOnce()
      pollRef.current = setInterval(pollOnce, POLL_INTERVAL_MS)
    }
    run()

    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const retrySegment = async (segmentId) => {
    setRetrying(segmentId)
    try {
      await api.post(`/interviews/${interviewId}/segments/${segmentId}/retry-audio`)
      await pollOnce()
      if (!pollRef.current) pollRef.current = setInterval(pollOnce, POLL_INTERVAL_MS)
    } catch (e) {
      console.error(e)
    } finally {
      setRetrying(null)
    }
  }

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

  const segments = status?.segments || []
  const terminalCount = segments.filter(s => TERMINAL_STATUSES.has(s.processing_status)).length
  const progressPercent = segments.length ? Math.round((terminalCount / segments.length) * 100) : 0

  return (
    <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
      <div className="glass-card p-10 max-w-md w-full">
        <div className="text-center mb-10">
          <div className="w-20 h-20 rounded-2xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center mx-auto mb-5">
            <Brain size={36} className="text-cyan-400 animate-pulse" />
          </div>
          <h2 className="text-2xl font-black mb-2">Analysing your answers</h2>
          <p className="text-gray-400 text-sm">
            Running real local audio analysis on each recorded answer. This can take a minute per answer.
          </p>
        </div>

        <div className="space-y-3 mb-8">
          {segments.length === 0 && (
            <div className="flex items-center gap-3 p-3.5 rounded-xl bg-white/5 border border-white/10">
              <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              <span className="text-sm text-gray-400">Starting analysis…</span>
            </div>
          )}
          {segments.map((seg, i) => {
            const meta = STATUS_META[seg.processing_status] || STATUS_META.pending
            const Icon = meta.icon
            const isTerminal = TERMINAL_STATUSES.has(seg.processing_status)
            return (
              <motion.div
                key={seg.id}
                initial={{ opacity: 0, x: -15 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.05 }}
                className={`flex items-center gap-4 p-3.5 rounded-xl border transition-all duration-300 ${
                  isTerminal ? 'bg-white/5 border-white/10' : 'bg-cyan-400/5 border-cyan-400/20'
                }`}
              >
                <div className={`w-9 h-9 rounded-full flex items-center justify-center flex-shrink-0 bg-white/5 ${meta.className}`}>
                  {seg.processing_status === 'processing'
                    ? <div className="w-4 h-4 border-2 border-cyan-400 border-t-transparent rounded-full animate-spin" />
                    : <Icon size={16} />}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white">Question {seg.sequence_index + 1}</p>
                  <p className={`text-xs ${meta.className}`}>{meta.label}</p>
                </div>
                {seg.processing_status === 'failed' && (
                  <button
                    onClick={() => retrySegment(seg.id)}
                    disabled={retrying === seg.id}
                    className="text-xs px-2.5 py-1.5 rounded-lg bg-white/5 border border-white/10 text-gray-300 hover:text-cyan-400 hover:border-cyan-400/30 flex items-center gap-1.5 disabled:opacity-50 flex-shrink-0"
                  >
                    <RefreshCw size={12} className={retrying === seg.id ? 'animate-spin' : ''} /> Retry
                  </button>
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
        <p className="text-center text-xs text-gray-600 mt-2">
          {terminalCount}/{segments.length || '…'} answers analyzed
        </p>
      </div>
    </div>
  )
}
