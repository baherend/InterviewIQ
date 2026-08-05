import React, { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar, ResponsiveContainer,
} from 'recharts'
import {
  Eye, Mic, MessageSquare, Brain, PlayCircle, ArrowLeft, Award,
  AlertTriangle, Clock, TrendingUp, FileText, Volume2, Zap, Activity,
  HelpCircle, Waves, Timer, BarChart2,
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

// "Not available" — never a fabricated 0% — whenever the underlying real
// value is null (missing evidence, deferred phase, or analysis failure).
const pct = (value) => (value == null ? 'Not available' : `${Math.round(value * 100)}%`)
const num1 = (value, suffix = '') => (value == null ? 'Not available' : `${value.toFixed(1)}${suffix}`)

const SEGMENT_STATUS_META = {
  pending: { label: 'Queued for analysis', className: 'bg-gray-400/10 text-gray-400 border-gray-400/20' },
  processing: { label: 'Analyzing…', className: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20' },
  completed: { label: 'Analyzed', className: 'bg-cyan-400/10 text-cyan-400 border-cyan-400/20' },
  partial: { label: 'Partially analyzed', className: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20' },
  insufficient_evidence: { label: 'Insufficient evidence', className: 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20' },
  failed: { label: 'Analysis failed', className: 'bg-red-400/10 text-red-400 border-red-400/20' },
}

function QuestionAudioCard({ item, index }) {
  const segment = item.segment
  const audio = segment?.audio_analysis
  const statusMeta = segment
    ? (SEGMENT_STATUS_META[segment.processing_status] || SEGMENT_STATUS_META.pending)
    : { label: 'No recording', className: 'bg-gray-400/10 text-gray-400 border-gray-400/20' }

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.05 }}
      className="glass-card p-6"
    >
      <div className="flex items-start justify-between gap-3 mb-4 flex-wrap">
        <div>
          <span className="text-xs text-gray-500 uppercase tracking-widest font-semibold">
            Question {item.sequence_index + 1}
          </span>
          <h4 className="text-base font-bold mt-1 leading-relaxed">{item.question_text}</h4>
        </div>
        <span className={`text-xs px-2.5 py-1 rounded-full border font-medium flex-shrink-0 ${statusMeta.className}`}>
          {statusMeta.label}
        </span>
      </div>

      {!segment && (
        <p className="text-sm text-gray-500 italic">No answer was recorded for this question.</p>
      )}

      {segment && !audio && segment.failure_message && (
        <p className="text-sm text-gray-400">{segment.failure_message}</p>
      )}

      {audio && (
        <div className="grid sm:grid-cols-2 gap-x-6 gap-y-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Activity size={15} className="text-purple-400" />
              <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Audio Emotion Classification</span>
            </div>
            <p className="text-sm font-semibold text-white mb-1">{audio.emotion_label || 'Not available'}</p>
            {audio.emotion_probabilities && (
              <div className="space-y-1 mt-2">
                {Object.entries(audio.emotion_probabilities).map(([label, value]) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className="text-[11px] text-gray-500 w-24 flex-shrink-0 truncate">{label}</span>
                    <div className="flex-1 bg-white/5 rounded-full h-1">
                      <div className="h-1 rounded-full bg-purple-400" style={{ width: `${Math.round(value * 100)}%` }} />
                    </div>
                    <span className="text-[11px] text-gray-500 w-9 text-right">{Math.round(value * 100)}%</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <HelpCircle size={15} className="text-blue-400" />
              <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Audio Model Confidence</span>
            </div>
            <p className="text-sm font-semibold text-white">{pct(audio.model_confidence)}</p>
            <p className="text-[11px] text-gray-500 mt-1 leading-snug">
              Diagnostic model confidence; not candidate confidence.
            </p>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <Waves size={15} className="text-cyan-400" />
              <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Vocal Delivery Score</span>
            </div>
            <p className="text-sm font-semibold text-white">
              {audio.vocal_delivery_score == null ? 'Not available' : audio.vocal_delivery_score.toFixed(1)}
            </p>
            <p className="text-[11px] text-gray-500 mt-1 leading-snug">
              Experimental vocal-delivery indicator.
            </p>
          </div>

          <div>
            <div className="flex items-center gap-2 mb-1.5">
              <BarChart2 size={15} className="text-green-400" />
              <span className="text-xs text-gray-500 uppercase tracking-wide font-semibold">Evidence Status</span>
            </div>
            <p className="text-sm font-semibold text-white">
              {audio.sufficient_evidence == null ? 'Not available' : (audio.sufficient_evidence ? 'Sufficient' : 'Insufficient')}
            </p>
          </div>

          <div className="sm:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-3 pt-2 border-t border-white/5">
            <div>
              <p className="text-[11px] text-gray-500 mb-0.5 flex items-center gap-1"><Timer size={11} /> Speaking Rate</p>
              <p className="text-sm font-semibold text-white">
                {audio.speaking_rate_wpm == null ? 'Not available' : `${audio.speaking_rate_wpm.toFixed(0)} WPM`}
              </p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 mb-0.5">Pause Control</p>
              <p className="text-sm font-semibold text-white">{pct(audio.pause_control_score)}</p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 mb-0.5">Volume Stability</p>
              <p className="text-sm font-semibold text-white">{pct(audio.volume_stability_score)}</p>
            </div>
            <div>
              <p className="text-[11px] text-gray-500 mb-0.5">Speech Continuity</p>
              <p className="text-sm font-semibold text-white">{pct(audio.speech_continuity_score)}</p>
            </div>
          </div>

          {audio.failure_reason && (
            <div className="sm:col-span-2 text-[11px] text-gray-500 leading-relaxed pt-2 border-t border-white/5">
              {audio.failure_reason}
            </div>
          )}
        </div>
      )}
    </motion.div>
  )
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

  const { interview, result, questions = [], audio_summary: audioSummary } = data

  // Legacy (pre-Phase-3A) mocked scores — only shown when at least one
  // actually exists, so a Phase 3A interview (no Result row at all) never
  // renders a misleadingly-zeroed radar/score-card section.
  const hasLegacyResult = result && (
    result.vision_score != null || result.audio_score != null || result.nlp_score != null
  )
  const radarData = hasLegacyResult
    ? [
        { subject: 'Vision', score: result.vision_score ?? 0 },
        { subject: 'Audio', score: result.audio_score ?? 0 },
        { subject: 'NLP', score: result.nlp_score ?? 0 },
      ]
    : []

  const metrics = [
    { label: 'Dominant Emotion', value: result?.emotion || '—', icon: <Brain size={15} className="text-cyan-400" /> },
    { label: 'Eye Contact', value: result?.eye_contact != null ? `${(result.eye_contact * 100).toFixed(0)}%` : '—', icon: <Eye size={15} className="text-purple-400" /> },
    { label: 'Speaking Pace', value: result?.wpm != null ? `${result.wpm.toFixed(0)} WPM` : '—', icon: <Volume2 size={15} className="text-blue-400" /> },
    { label: 'Pause Count', value: result?.pause_count != null ? `${result.pause_count} pauses` : '—', icon: <Clock size={15} className="text-yellow-400" /> },
    { label: 'Filler Words', value: result?.filler_count != null ? `${result.filler_count} detected` : '—', icon: <MessageSquare size={15} className="text-orange-400" /> },
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
            {hasLegacyResult && (
              <div className="text-right flex-shrink-0">
                <p className={`text-6xl font-black ${scoreTextColor(interview.final_score)}`}>
                  {interview.final_score?.toFixed(1) ?? '—'}
                </p>
                <span className={`text-sm px-3 py-1.5 rounded-full border font-medium mt-2 inline-block ${verdictStyle(interview.verdict)}`}>
                  {interview.verdict || '—'}
                </span>
              </div>
            )}
          </div>
        </motion.div>

        {/* Legacy mock score section — only for interviews predating Phase 3A */}
        {hasLegacyResult && (
          <>
            <div className="grid md:grid-cols-3 gap-4 mb-6">
              <ScoreCard title="Vision Score" score={result.vision_score} icon={<Eye size={22} className="text-cyan-400" />} subtitle="Facial expression & eye contact" delay={0} />
              <ScoreCard title="Audio Score" score={result.audio_score} icon={<Mic size={22} className="text-purple-400" />} subtitle="Pace, clarity & confidence" delay={0.1} />
              <ScoreCard title="NLP Score" score={result.nlp_score} icon={<MessageSquare size={22} className="text-blue-400" />} subtitle="Content quality & relevance" delay={0.2} />
            </div>

            <div className="grid lg:grid-cols-2 gap-6 mb-6">
              <motion.div initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 }} className="glass-card p-6">
                <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
                  <TrendingUp size={20} className="text-cyan-400" /> Performance Radar
                </h3>
                <ResponsiveContainer width="100%" height={220}>
                  <RadarChart data={radarData} cx="50%" cy="50%" outerRadius="75%">
                    <PolarGrid stroke="rgba(255,255,255,0.08)" />
                    <PolarAngleAxis dataKey="subject" tick={{ fill: '#94a3b8', fontSize: 13, fontWeight: 600 }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} />
                    <Radar name="Score" dataKey="score" stroke="#00f5ff" fill="#00f5ff" fillOpacity={0.15} strokeWidth={2} />
                  </RadarChart>
                </ResponsiveContainer>
              </motion.div>

              <motion.div initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.35 }} className="glass-card p-6">
                <h3 className="text-lg font-bold mb-5 flex items-center gap-2">
                  <Zap size={20} className="text-cyan-400" /> Detailed Metrics
                </h3>
                <div className="space-y-3.5">
                  {metrics.map(m => (
                    <div key={m.label} className="flex items-center justify-between py-2 border-b border-white/5 last:border-0">
                      <div className="flex items-center gap-2.5">{m.icon}<span className="text-sm text-gray-400">{m.label}</span></div>
                      <span className="text-sm font-semibold text-white">{m.value}</span>
                    </div>
                  ))}
                </div>
              </motion.div>
            </div>

            {result.transcript && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.4 }} className="glass-card p-6 mb-6">
                <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                  <FileText size={20} className="text-cyan-400" /> Sample Transcript
                </h3>
                <p className="text-gray-300 text-sm leading-relaxed italic">"{result.transcript}"</p>
              </motion.div>
            )}

            {result.recommendations?.length > 0 && (
              <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.45 }} className="glass-card p-6 mb-8">
                <h3 className="text-lg font-bold mb-5 flex items-center gap-2 flex-wrap">
                  <Award size={20} className="text-cyan-400" /> Recommendations
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
          </>
        )}

        {/* Real per-question audio analysis (Phase 3A) */}
        {questions.length > 0 && (
          <div className="mb-8">
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} className="glass-card p-6 mb-4">
              <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
                <Mic size={20} className="text-cyan-400" /> Audio Analysis Summary
              </h3>
              {audioSummary?.available ? (
                <div className="flex flex-wrap items-center gap-6">
                  <div>
                    <p className="text-3xl font-black text-cyan-400">
                      {audioSummary.average_vocal_delivery_score.toFixed(1)}
                    </p>
                    <p className="text-xs text-gray-500 mt-1">Average Vocal Delivery Score</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-400">
                      {audioSummary.valid_segment_count} of {audioSummary.total_segment_count} answers scored
                    </p>
                  </div>
                  <p className="text-[11px] text-gray-500 leading-snug max-w-md">
                    Experimental vocal-delivery indicator, averaged only over answers with a valid score.
                  </p>
                </div>
              ) : (
                <p className="text-sm text-gray-500">
                  {audioSummary?.reason || 'Audio analysis not available for this historical interview.'}
                </p>
              )}
            </motion.div>

            <div className="space-y-4">
              {questions.map((item, i) => (
                <QuestionAudioCard key={item.sequence_index} item={item} index={i} />
              ))}
            </div>
          </div>
        )}

        {questions.length === 0 && !hasLegacyResult && (
          <div className="glass-card p-8 text-center mb-8">
            <AlertTriangle size={32} className="text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500">Audio analysis not available for this historical interview.</p>
          </div>
        )}

        {/* Actions */}
        <div className="flex flex-col sm:flex-row gap-3">
          <button onClick={() => navigate('/interview/type')} className="btn-primary flex items-center gap-2 justify-center">
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
