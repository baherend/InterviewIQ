import React, { useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  FileVideo,
  Mic,
  Square,
  Upload,
  Video,
} from 'lucide-react'
import api from '../api/axios'

const NO_VALID_SCORE =
  'No valid technical score was produced because the spoken answer did not match the selected question.'

const percent = (value, scale = 1) =>
  value == null || value < 0 ? 'Not available' : `${(value * scale).toFixed(1)}%`

const Value = ({ label, value, note }) => (
  <div className="rounded-xl border border-white/10 bg-white/[0.025] p-4">
    <p className="text-xs uppercase tracking-wider text-gray-500">{label}</p>
    <p className="mt-1 text-lg font-bold text-white">{value ?? 'Not available'}</p>
    {note && <p className="mt-1 text-xs leading-relaxed text-gray-500">{note}</p>}
  </div>
)

export default function FusionTest() {
  const [questions, setQuestions] = useState([])
  const [questionId, setQuestionId] = useState('SE-028')
  const [videoFile, setVideoFile] = useState(null)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [recording, setRecording] = useState(false)
  const previewRef = useRef(null)
  const recorderRef = useRef(null)
  const streamRef = useRef(null)
  const chunksRef = useRef([])

  useEffect(() => {
    api.get('/interviews/analysis-questions')
      .then(({ data }) => setQuestions(data.questions || []))
      .catch((requestError) => {
        setError(requestError.response?.data?.detail || 'Could not load Fusion questions.')
      })
    return () => streamRef.current?.getTracks().forEach((track) => track.stop())
  }, [])

  const startRecording = async () => {
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: true })
      streamRef.current = stream
      if (previewRef.current) previewRef.current.srcObject = stream
      const mimeType = ['video/webm;codecs=vp8,opus', 'video/webm']
        .find((type) => MediaRecorder.isTypeSupported(type))
      const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'video/webm' })
        setVideoFile(new File([blob], 'browser-answer.webm', { type: blob.type }))
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        if (previewRef.current) previewRef.current.srcObject = null
      }
      recorder.start(1000)
      recorderRef.current = recorder
      setRecording(true)
    } catch {
      setError('Camera or microphone access was unavailable. You can upload a video instead.')
    }
  }

  const stopRecording = () => {
    if (recorderRef.current?.state !== 'inactive') recorderRef.current.stop()
    setRecording(false)
  }

  const analyze = async () => {
    if (!videoFile) {
      setError('Choose or record a video answer first.')
      return
    }
    setLoading(true)
    setError('')
    setResult(null)
    const form = new FormData()
    form.append('video', videoFile)
    form.append('question_id', questionId)
    try {
      const { data } = await api.post('/interviews/analyze', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 4_000_000,
      })
      setResult(data)
    } catch (requestError) {
      setError(
        requestError.response?.data?.detail ||
        'Fusion analysis failed. Check the backend terminal and preserved result artifact.'
      )
    } finally {
      setLoading(false)
    }
  }

  const selectedQuestion = questions.find((item) => item.question_id === questionId)
  const invalidAnswer = result?.question_answer_validity?.valid === false

  return (
    <main className="gradient-bg min-h-screen px-4 pb-16 pt-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-8">
          <div className="mb-3 flex items-center gap-3">
            <div className="rounded-xl border border-cyan-400/20 bg-cyan-400/10 p-3">
              <Brain className="text-cyan-400" size={25} />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-400">
                Local real-model test
              </p>
              <h1 className="text-3xl font-black">Fusion Analysis</h1>
            </div>
          </div>
          <p className="max-w-3xl text-sm leading-relaxed text-gray-400">
            Submit one video answer to the existing Vision, Audio, and NLP subprocess
            pipeline. Local model processing can take several minutes.
          </p>
        </div>

        <section className="glass-card mb-6 p-6">
          <div className="grid gap-5 lg:grid-cols-2">
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">Technical question</span>
              <select
                aria-label="Technical question"
                className="input-field"
                value={questionId}
                onChange={(event) => setQuestionId(event.target.value)}
              >
                {!questions.length && <option value="SE-028">SE-028</option>}
                {questions.map((item) => (
                  <option key={item.question_id} value={item.question_id}>
                    {item.question_id} · {item.track}
                  </option>
                ))}
              </select>
              <p className="mt-2 min-h-10 text-sm leading-relaxed text-gray-400">
                {selectedQuestion?.question || 'Loading question text…'}
              </p>
            </label>

            <div>
              <span className="mb-2 block text-sm font-semibold">Video answer</span>
              <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-cyan-400/30 bg-cyan-400/5 p-4 hover:bg-cyan-400/10">
                <Upload size={20} className="text-cyan-400" />
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">Choose a video file</span>
                  <span className="block truncate text-xs text-gray-500">
                    {videoFile?.name || 'MP4, WebM, MOV, MKV, or AVI'}
                  </span>
                </span>
                <input
                  data-testid="video-input"
                  className="sr-only"
                  type="file"
                  accept=".mp4,.webm,.mov,.mkv,.avi,video/*"
                  onChange={(event) => setVideoFile(event.target.files?.[0] || null)}
                />
              </label>

              <div className="mt-3 flex items-center gap-3">
                {!recording ? (
                  <button type="button" className="btn-secondary flex items-center gap-2 px-4 py-2 text-sm" onClick={startRecording}>
                    <Video size={16} /> Record in browser
                  </button>
                ) : (
                  <button type="button" className="btn-danger flex items-center gap-2 px-4 py-2 text-sm" onClick={stopRecording}>
                    <Square size={14} /> Stop recording
                  </button>
                )}
                {videoFile && (
                  <span className="flex items-center gap-1 text-xs text-green-400">
                    <CheckCircle2 size={14} /> Ready
                  </span>
                )}
              </div>
              {recording && (
                <video ref={previewRef} autoPlay muted playsInline className="mt-3 max-h-44 w-full rounded-xl bg-black object-contain" />
              )}
            </div>
          </div>

          {error && (
            <div role="alert" className="mt-5 flex items-start gap-3 rounded-xl border border-red-400/30 bg-red-400/10 p-4 text-sm text-red-200">
              <AlertTriangle size={18} className="mt-0.5 shrink-0 text-red-400" />
              {error}
            </div>
          )}

          <button
            data-testid="analyze-button"
            disabled={loading || recording || !videoFile}
            onClick={analyze}
            className="btn-primary mt-6 flex w-full items-center justify-center gap-2 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? (
              <>
                <span className="h-5 w-5 animate-spin rounded-full border-2 border-black border-t-transparent" />
                Running all three local models…
              </>
            ) : (
              <><Mic size={18} /> Analyze answer</>
            )}
          </button>
        </section>

        {result && (
          <section data-testid="fusion-results" className="space-y-6">
            {result.warnings?.length > 0 && (
              <div className="rounded-2xl border border-yellow-400/30 bg-yellow-400/10 p-5">
                <h2 className="mb-3 flex items-center gap-2 font-bold text-yellow-300">
                  <AlertTriangle size={19} /> Warnings and limitations
                </h2>
                <ul className="space-y-2 text-sm leading-relaxed text-yellow-100/75">
                  {result.warnings.map((warning) => <li key={warning}>• {warning}</li>)}
                </ul>
              </div>
            )}

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <Value label="Engineering status" value={result.status} note="Pipeline execution state, not candidate performance." />
              <Value
                label="Question-answer validity"
                value={result.question_answer_validity.valid === true ? 'Valid' : result.question_answer_validity.valid === false ? 'Mismatch' : 'Inconclusive'}
                note={result.question_answer_validity.reason}
              />
              <Value
                label="Final technical score"
                value={result.fusion_summary.final_technical_score == null ? 'Not produced' : percent(result.fusion_summary.final_technical_score)}
                note={result.fusion_summary.final_technical_score == null ? NO_VALID_SCORE : 'Candidate technical performance score.'}
              />
            </div>

            {invalidAnswer && (
              <div data-testid="mismatch-message" className="rounded-2xl border border-red-400/30 bg-red-400/10 p-5 font-semibold text-red-100">
                {NO_VALID_SCORE}
              </div>
            )}

            <div className="grid gap-6 lg:grid-cols-3">
              <article className="glass-card p-5">
                <h2 className="mb-4 flex items-center gap-2 font-bold"><Brain size={18} className="text-blue-400" /> NLP technical evaluation</h2>
                <div className="space-y-3">
                  <Value label="Technical score" value={percent(result.nlp.technical_score)} note="Candidate performance; negative raw contradiction values are withheld." />
                  <Value label="Precision" value={percent(result.nlp.precision, 100)} note="Candidate answer metric, when valid and non-negative." />
                  <Value label="Coverage" value={percent(result.nlp.coverage, 100)} note="Candidate answer metric, when valid and non-negative." />
                </div>
              </article>

              <article className="glass-card p-5">
                <h2 className="mb-4 flex items-center gap-2 font-bold"><FileVideo size={18} className="text-cyan-400" /> Vision model output</h2>
                <div className="space-y-3">
                  <Value label="Predicted class" value={result.vision.predicted_class} />
                  <Value label="Model confidence" value={percent(result.vision.model_confidence, 100)} note="Model certainty, not candidate performance." />
                  <Value label="Sufficient evidence" value={result.vision.sufficient_evidence === true ? 'Yes' : result.vision.sufficient_evidence === false ? 'No' : 'Unknown'} />
                </div>
              </article>

              <article className="glass-card p-5">
                <h2 className="mb-4 flex items-center gap-2 font-bold"><Mic size={18} className="text-purple-400" /> Audio model output</h2>
                <div className="space-y-3">
                  <Value label="Dominant emotion" value={result.audio.dominant_emotion} />
                  <Value label="Model confidence" value={percent(result.audio.model_confidence, 100)} note="Model certainty, not candidate performance or personality." />
                </div>
              </article>
            </div>

            <article className="glass-card p-6">
              <h2 className="mb-3 font-bold">Transcript</h2>
              <p className="whitespace-pre-wrap text-sm leading-7 text-gray-300">
                {result.transcript || 'No usable transcript was produced.'}
              </p>
            </article>
          </section>
        )}
      </div>
    </main>
  )
}
