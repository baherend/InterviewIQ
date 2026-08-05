import React, { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Brain, Mic, MicOff, Video, VideoOff, ChevronRight, Clock, AlertCircle, Check, Loader2, RefreshCw } from 'lucide-react'
import api from '../api/axios'

const getMimeType = () => {
  const types = ['video/webm;codecs=vp8,opus', 'video/webm;codecs=vp9,opus', 'video/webm', 'video/mp4']
  return types.find(t => MediaRecorder.isTypeSupported(t)) || 'video/webm'
}

export default function InterviewRoom() {
  const location = useLocation()
  const navigate = useNavigate()
  const { interview_type, track } = location.state || {}

  const videoRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])
  const streamRef = useRef(null)
  const timerRef = useRef(null)
  const questionStartRef = useRef(null)

  const [interviewId, setInterviewId] = useState(null)
  const [questions, setQuestions] = useState([])
  const [currentQ, setCurrentQ] = useState(0)
  const [phase, setPhase] = useState('loading')
  const [countdown, setCountdown] = useState(3)
  const [timeLeft, setTimeLeft] = useState(90)
  const [cameraError, setCameraError] = useState(null)
  const [micOn, setMicOn] = useState(true)
  const [videoOn, setVideoOn] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState(null)
  const [pendingBlob, setPendingBlob] = useState(null)

  // Persists the ordered question sequence on the server (Phase 3A) —
  // every question shown below is rendered from that persisted response,
  // never re-derived or re-requested independently.
  useEffect(() => {
    if (!interview_type) {
      navigate('/interview/type')
      return
    }
    api.post('/interviews/start-interview', { interview_type, track: track || null })
      .then(res => {
        setInterviewId(res.data.id)
        setQuestions(res.data.questions || [])
        setPhase('setup')
      })
      .catch(() => navigate('/interview/type'))
  }, [])

  useEffect(() => {
    const setup = async () => {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      } catch {
        setCameraError('Camera or microphone access was denied. Please allow permissions and refresh.')
      }
    }
    setup()
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [])

  const startCountdown = () => {
    setPhase('countdown')
    let count = 3
    setCountdown(count)
    const interval = setInterval(() => {
      count--
      if (count <= 0) {
        clearInterval(interval)
        setCountdown(0)
        beginRecording()
      } else {
        setCountdown(count)
      }
    }, 1000)
  }

  // Starts a fresh recorder scoped to exactly one question — this is the
  // structural fix for Phase 3A: every answer is its own MediaRecorder
  // session, not a slice of one interview-long recording.
  const startRecorderForQuestion = () => {
    const stream = streamRef.current
    if (!stream) return
    chunksRef.current = []
    const recorder = new MediaRecorder(stream, { mimeType: getMimeType() })
    recorder.ondataavailable = (e) => { if (e.data.size > 0) chunksRef.current.push(e.data) }
    recorder.start(1000)
    mediaRecorderRef.current = recorder
    questionStartRef.current = new Date().toISOString()
  }

  const beginRecording = () => {
    startRecorderForQuestion()
    setPhase('interview')
    resetQuestionTimer()
  }

  const resetQuestionTimer = () => {
    setTimeLeft(90)
    if (timerRef.current) clearInterval(timerRef.current)
    timerRef.current = setInterval(() => {
      setTimeLeft(prev => {
        if (prev <= 1) { clearInterval(timerRef.current); return 0 }
        return prev - 1
      })
    }, 1000)
  }

  const stopCurrentRecorder = () => new Promise((resolve) => {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state === 'inactive') {
      resolve(new Blob(chunksRef.current, { type: getMimeType() }))
      return
    }
    recorder.onstop = () => resolve(new Blob(chunksRef.current, { type: getMimeType() }))
    recorder.stop()
  })

  const uploadSegment = (blob, question, startedAtIso, endedAtIso) => {
    const formData = new FormData()
    formData.append('media', new File([blob], 'answer.webm', { type: blob.type || 'video/webm' }))
    formData.append('interview_question_id', String(question.id))
    if (question.question_id != null) formData.append('question_id', String(question.question_id))
    formData.append('sequence_index', String(question.sequence_index))
    if (startedAtIso) formData.append('started_at', startedAtIso)
    if (endedAtIso) formData.append('ended_at', endedAtIso)
    return api.post(`/interviews/${interviewId}/segments`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
  }

  // Shared by both the normal Next flow and Retry-after-failure: uploads
  // exactly one already-recorded Blob, waits for a confirmed acknowledgement,
  // and only then advances. On failure the Blob is kept in memory so the
  // candidate never has to re-record — just retry the upload.
  const finalizeAnswer = async (blob) => {
    setUploading(true)
    setUploadError(null)
    const question = questions[currentQ]
    const endedAtIso = new Date().toISOString()
    try {
      await uploadSegment(blob, question, questionStartRef.current, endedAtIso)
      setUploading(false)
      setPendingBlob(null)
      if (currentQ < questions.length - 1) {
        setCurrentQ(q => q + 1)
        resetQuestionTimer()
        startRecorderForQuestion()
      } else {
        if (timerRef.current) clearInterval(timerRef.current)
        if (streamRef.current) streamRef.current.getTracks().forEach(t => t.stop())
        navigate('/interview/processing', { state: { interviewId } })
      }
    } catch (err) {
      setUploading(false)
      setPendingBlob(blob)
      setUploadError(
        err.response?.data?.detail
        || 'Could not upload your answer. Please check your connection and retry.'
      )
    }
  }

  const goNext = async () => {
    if (uploading) return
    const blob = await stopCurrentRecorder()
    await finalizeAnswer(blob)
  }

  const retryUpload = () => {
    if (uploading || !pendingBlob) return
    finalizeAnswer(pendingBlob)
  }

  const toggleMic = () => {
    streamRef.current?.getAudioTracks().forEach(t => { t.enabled = !micOn })
    setMicOn(v => !v)
  }

  const toggleVideo = () => {
    streamRef.current?.getVideoTracks().forEach(t => { t.enabled = !videoOn })
    setVideoOn(v => !v)
  }

  const timePercent = (timeLeft / 90) * 100
  const timerColor = timeLeft > 30 ? 'text-cyan-400' : timeLeft > 10 ? 'text-yellow-400' : 'text-red-400'
  const timerBarColor = timeLeft > 30 ? 'bg-cyan-400' : timeLeft > 10 ? 'bg-yellow-400' : 'bg-red-400'

  if (phase === 'loading') {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg">
        <div className="text-center">
          <div className="w-14 h-14 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin mx-auto mb-4" />
          <p className="neon-text font-semibold">Preparing your interview...</p>
        </div>
      </div>
    )
  }

  if (cameraError) {
    return (
      <div className="flex items-center justify-center min-h-screen gradient-bg px-4">
        <div className="glass-card p-10 max-w-md text-center">
          <AlertCircle size={48} className="text-red-400 mx-auto mb-4" />
          <h2 className="text-xl font-bold mb-3">Camera Access Required</h2>
          <p className="text-gray-400 text-sm mb-6 leading-relaxed">{cameraError}</p>
          <button onClick={() => navigate('/interview/type')} className="btn-secondary">Go Back</button>
        </div>
      </div>
    )
  }

  return (
    <div className="gradient-bg min-h-screen pt-16">
      <div className="max-w-6xl mx-auto px-4 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <div className="glass px-3 py-1.5 rounded-full border border-cyan-400/20">
              <span className="text-sm text-cyan-400 font-medium">
                {interview_type}{track ? ` · ${track}` : ''}
              </span>
            </div>
            {phase === 'interview' && (
              <div className="flex items-center gap-1.5 glass px-3 py-1.5 rounded-full border border-red-400/30">
                <span className="w-2 h-2 bg-red-400 rounded-full recording-pulse" />
                <span className="text-xs text-red-400 font-semibold">REC</span>
              </div>
            )}
          </div>
          {phase === 'interview' && (
            <div className="glass px-4 py-2 rounded-full flex items-center gap-2">
              <span className="text-sm text-gray-400">Q</span>
              <span className="font-black text-white">{currentQ + 1}</span>
              <span className="text-gray-600">/</span>
              <span className="text-gray-400">{questions.length}</span>
            </div>
          )}
        </div>

        <div className="grid lg:grid-cols-5 gap-6 items-start">
          {/* Camera feed */}
          <div className="lg:col-span-2">
            <div className="glass-card overflow-hidden relative" style={{ aspectRatio: '4/3' }}>
              <video
                ref={videoRef}
                autoPlay
                muted
                playsInline
                className={`w-full h-full object-cover ${!videoOn ? 'opacity-0' : ''}`}
              />
              {!videoOn && (
                <div className="absolute inset-0 flex items-center justify-center bg-gray-900/90">
                  <VideoOff size={40} className="text-gray-600" />
                </div>
              )}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex items-center gap-3">
                <button
                  onClick={toggleMic}
                  className={`p-2.5 rounded-full border backdrop-blur-md transition-all ${
                    micOn ? 'bg-black/40 border-white/20 text-white hover:bg-black/60' : 'bg-red-400/20 border-red-400/40 text-red-400'
                  }`}
                >
                  {micOn ? <Mic size={17} /> : <MicOff size={17} />}
                </button>
                <button
                  onClick={toggleVideo}
                  className={`p-2.5 rounded-full border backdrop-blur-md transition-all ${
                    videoOn ? 'bg-black/40 border-white/20 text-white hover:bg-black/60' : 'bg-red-400/20 border-red-400/40 text-red-400'
                  }`}
                >
                  {videoOn ? <Video size={17} /> : <VideoOff size={17} />}
                </button>
              </div>
            </div>
          </div>

          {/* Right panel */}
          <div className="lg:col-span-3 flex flex-col gap-4">
            <AnimatePresence mode="wait">
              {phase === 'setup' && (
                <motion.div
                  key="setup"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="glass-card p-8"
                >
                  <Brain size={40} className="text-cyan-400 mb-5" />
                  <h2 className="text-2xl font-black mb-3">Ready to begin?</h2>
                  <p className="text-gray-400 text-sm leading-relaxed mb-6">
                    You have <strong className="text-white">{questions.length} questions</strong> to answer.
                    A 90-second timer will start with each question. Speak clearly and look at the camera.
                  </p>
                  <ul className="space-y-2.5 mb-8">
                    {[
                      'Ensure your face is well-lit and clearly visible',
                      'Speak clearly towards the microphone',
                      'You have 90 seconds to answer each question',
                      'Each answer is recorded and submitted separately',
                    ].map(tip => (
                      <li key={tip} className="flex items-start gap-2.5 text-sm text-gray-400">
                        <Check size={14} className="text-cyan-400 mt-0.5 flex-shrink-0" />
                        {tip}
                      </li>
                    ))}
                  </ul>
                  <button onClick={startCountdown} className="btn-primary w-full py-3.5 flex items-center justify-center gap-2">
                    <Brain size={18} /> Start Interview
                  </button>
                </motion.div>
              )}

              {phase === 'countdown' && (
                <motion.div
                  key="countdown"
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.9 }}
                  className="glass-card p-12 flex flex-col items-center justify-center text-center"
                >
                  <p className="text-gray-400 mb-6 text-lg font-medium">Starting in</p>
                  <AnimatePresence mode="wait">
                    <motion.div
                      key={countdown}
                      initial={{ scale: 0.4, opacity: 0 }}
                      animate={{ scale: 1, opacity: 1 }}
                      exit={{ scale: 1.4, opacity: 0 }}
                      transition={{ duration: 0.35 }}
                      className="text-9xl font-black neon-text"
                    >
                      {countdown === 0 ? 'GO!' : countdown}
                    </motion.div>
                  </AnimatePresence>
                </motion.div>
              )}

              {phase === 'interview' && questions[currentQ] && (
                <motion.div
                  key={currentQ}
                  initial={{ opacity: 0, x: 30 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -30 }}
                  className="glass-card p-8 flex flex-col"
                >
                  <div className="flex items-center justify-between mb-5">
                    <span className="text-xs text-gray-500 uppercase tracking-widest font-semibold">
                      Question {currentQ + 1} of {questions.length}
                    </span>
                    <div className={`flex items-center gap-2 ${timerColor} transition-colors`}>
                      <Clock size={16} />
                      <span className="font-mono font-bold text-lg">
                        {String(Math.floor(timeLeft / 60)).padStart(2, '0')}:{String(timeLeft % 60).padStart(2, '0')}
                      </span>
                    </div>
                  </div>

                  <div className="w-full bg-white/5 rounded-full h-1.5 mb-7">
                    <div
                      className={`h-1.5 rounded-full transition-all duration-1000 ${timerBarColor}`}
                      style={{ width: `${timePercent}%` }}
                    />
                  </div>

                  {questions[currentQ].difficulty && (
                    <span className={`text-xs px-2.5 py-1 rounded-full border font-medium mb-4 self-start ${
                      questions[currentQ].difficulty === 'Easy'
                        ? 'bg-green-400/10 text-green-400 border-green-400/20'
                        : questions[currentQ].difficulty === 'Hard'
                        ? 'bg-red-400/10 text-red-400 border-red-400/20'
                        : 'bg-yellow-400/10 text-yellow-400 border-yellow-400/20'
                    }`}>
                      {questions[currentQ].difficulty}
                    </span>
                  )}

                  <h2 className="text-xl font-bold leading-relaxed mb-8 flex-1">
                    {questions[currentQ].question_text}
                  </h2>

                  {uploadError && (
                    <div className="flex items-start gap-2.5 mb-4 p-3.5 rounded-xl bg-red-400/10 border border-red-400/20" role="alert">
                      <AlertCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
                      <p className="text-sm text-red-300 leading-relaxed">{uploadError}</p>
                    </div>
                  )}

                  {uploadError ? (
                    <button
                      onClick={retryUpload}
                      disabled={uploading}
                      className="btn-primary w-full py-3.5 flex items-center justify-center gap-2 disabled:opacity-60"
                    >
                      {uploading
                        ? <><Loader2 size={18} className="animate-spin" /> Retrying upload...</>
                        : <><RefreshCw size={18} /> Retry Upload</>}
                    </button>
                  ) : (
                    <button
                      onClick={goNext}
                      disabled={uploading}
                      className="btn-primary w-full py-3.5 flex items-center justify-center gap-2 disabled:opacity-60"
                    >
                      {uploading
                        ? <><Loader2 size={18} className="animate-spin" /> Submitting answer...</>
                        : currentQ < questions.length - 1
                          ? <><ChevronRight size={18} /> Next Question</>
                          : <><Check size={18} /> Finish Interview</>}
                    </button>
                  )}
                </motion.div>
              )}
            </AnimatePresence>

            {phase === 'interview' && (
              <div className="flex items-center justify-center gap-2">
                {questions.map((_, i) => (
                  <div
                    key={i}
                    className={`h-1.5 rounded-full transition-all duration-300 ${
                      i < currentQ ? 'bg-cyan-400 w-6' : i === currentQ ? 'bg-cyan-400 w-10' : 'bg-white/10 w-4'
                    }`}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
