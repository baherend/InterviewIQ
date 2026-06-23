import React, { useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Plus, Pencil, Trash2, Shield, X, Check, Search } from 'lucide-react'
import api from '../api/axios'

const TYPES = ['HR', 'Leadership', 'Technical']
const TRACKS = ['Data Analysis', 'Data Science', 'Cybersecurity', 'Software Engineering']
const DIFFICULTIES = ['Easy', 'Medium', 'Hard']

const diffStyle = (d) => ({
  Easy: 'text-green-400 bg-green-400/10 border-green-400/20',
  Medium: 'text-yellow-400 bg-yellow-400/10 border-yellow-400/20',
  Hard: 'text-red-400 bg-red-400/10 border-red-400/20',
}[d] || '')

const EMPTY_FORM = { question: '', interview_type: 'HR', track: '', difficulty: 'Medium' }

export default function AdminQuestions() {
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('All')
  const [modal, setModal] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [saving, setSaving] = useState(false)
  const [deleteTarget, setDeleteTarget] = useState(null)

  const fetchQuestions = () => {
    setLoading(true)
    api.get('/questions')
      .then(res => setQuestions(res.data))
      .catch(console.error)
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchQuestions() }, [])

  const openCreate = () => {
    setForm(EMPTY_FORM)
    setModal('create')
  }

  const openEdit = (q) => {
    setForm({ question: q.question, interview_type: q.interview_type, track: q.track || '', difficulty: q.difficulty })
    setModal(q)
  }

  const handleSave = async () => {
    if (!form.question.trim()) return
    setSaving(true)
    try {
      const payload = {
        ...form,
        track: form.interview_type === 'Technical' ? (form.track || null) : null,
      }
      if (modal === 'create') {
        await api.post('/questions', payload)
      } else {
        await api.put(`/questions/${modal.id}`, payload)
      }
      setModal(null)
      fetchQuestions()
    } catch (e) {
      console.error(e)
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!deleteTarget) return
    try {
      await api.delete(`/questions/${deleteTarget}`)
      setDeleteTarget(null)
      fetchQuestions()
    } catch (e) {
      console.error(e)
    }
  }

  const filtered = questions.filter(q => {
    const matchType = typeFilter === 'All' || q.interview_type === typeFilter
    const matchSearch = q.question.toLowerCase().includes(search.toLowerCase())
    return matchType && matchSearch
  })

  return (
    <div className="gradient-bg min-h-screen pt-20 pb-12 px-4">
      <div className="max-w-5xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8"
        >
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-cyan-400/10 border border-cyan-400/20 flex items-center justify-center">
              <Shield size={20} className="text-cyan-400" />
            </div>
            <div>
              <h1 className="text-3xl font-black">Question Bank</h1>
              <p className="text-gray-400 text-sm mt-0.5">
                {questions.length} question{questions.length !== 1 ? 's' : ''} total
              </p>
            </div>
          </div>
          <button onClick={openCreate} className="btn-primary flex items-center gap-2 text-sm py-2.5 px-5 shrink-0">
            <Plus size={16} /> Add Question
          </button>
        </motion.div>

        {/* Search & Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-6">
          <div className="relative flex-1">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500 pointer-events-none" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search questions..."
              className="input-field pl-10"
            />
          </div>
          <div className="flex gap-2 flex-wrap">
            {['All', ...TYPES].map(t => (
              <button
                key={t}
                onClick={() => setTypeFilter(t)}
                className={`px-3.5 py-2 rounded-lg text-sm font-medium transition-all ${
                  typeFilter === t
                    ? 'bg-cyan-400/15 text-cyan-400 border border-cyan-400/30'
                    : 'text-gray-400 glass border border-white/5 hover:border-white/10 hover:text-white'
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>

        {/* Questions list */}
        {loading ? (
          <div className="flex justify-center py-20">
            <div className="w-10 h-10 border-4 border-cyan-400 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="glass-card p-14 text-center text-gray-500">
            No questions found{search ? ` for "${search}"` : ''}.
          </div>
        ) : (
          <div className="space-y-2">
            {filtered.map((q, i) => (
              <motion.div
                key={q.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.02 }}
                className="glass-card p-5 flex items-start gap-4 group hover:border-cyan-400/20 transition-all"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white mb-2.5 leading-relaxed">{q.question}</p>
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400">
                      {q.interview_type}
                    </span>
                    {q.track && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-white/5 border border-white/10 text-gray-400">
                        {q.track}
                      </span>
                    )}
                    <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${diffStyle(q.difficulty)}`}>
                      {q.difficulty}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => openEdit(q)}
                    className="p-2 rounded-lg hover:bg-white/5 text-gray-400 hover:text-cyan-400 transition-colors"
                    title="Edit"
                  >
                    <Pencil size={15} />
                  </button>
                  <button
                    onClick={() => setDeleteTarget(q.id)}
                    className="p-2 rounded-lg hover:bg-red-400/5 text-gray-400 hover:text-red-400 transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={15} />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Create / Edit Modal */}
      <AnimatePresence>
        {modal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={e => { if (e.target === e.currentTarget) setModal(null) }}
          >
            <motion.div
              initial={{ scale: 0.92, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 20 }}
              className="glass-card p-7 w-full max-w-lg"
            >
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-xl font-bold">
                  {modal === 'create' ? 'Add Question' : 'Edit Question'}
                </h2>
                <button
                  onClick={() => setModal(null)}
                  className="p-1.5 rounded-lg hover:bg-white/5 text-gray-400 hover:text-white transition-colors"
                >
                  <X size={20} />
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1.5">Question</label>
                  <textarea
                    value={form.question}
                    onChange={e => setForm(f => ({ ...f, question: e.target.value }))}
                    rows={3}
                    className="input-field resize-none"
                    placeholder="Enter the interview question..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1.5">Type</label>
                    <select
                      value={form.interview_type}
                      onChange={e => setForm(f => ({ ...f, interview_type: e.target.value, track: '' }))}
                      className="input-field"
                    >
                      {TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1.5">Difficulty</label>
                    <select
                      value={form.difficulty}
                      onChange={e => setForm(f => ({ ...f, difficulty: e.target.value }))}
                      className="input-field"
                    >
                      {DIFFICULTIES.map(d => <option key={d} value={d}>{d}</option>)}
                    </select>
                  </div>
                </div>

                {form.interview_type === 'Technical' && (
                  <div>
                    <label className="block text-sm text-gray-400 mb-1.5">Track</label>
                    <select
                      value={form.track}
                      onChange={e => setForm(f => ({ ...f, track: e.target.value }))}
                      className="input-field"
                    >
                      <option value="">— Select track —</option>
                      {TRACKS.map(t => <option key={t} value={t}>{t}</option>)}
                    </select>
                  </div>
                )}
              </div>

              <div className="flex gap-3 mt-7">
                <button onClick={() => setModal(null)} className="btn-secondary flex-1 py-2.5 text-sm">
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving || !form.question.trim()}
                  className="btn-primary flex-1 py-2.5 text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {saving
                    ? <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                    : <Check size={16} />}
                  {modal === 'create' ? 'Add Question' : 'Save Changes'}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Delete Confirmation */}
      <AnimatePresence>
        {deleteTarget && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4"
            onClick={e => { if (e.target === e.currentTarget) setDeleteTarget(null) }}
          >
            <motion.div
              initial={{ scale: 0.92 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0.92 }}
              className="glass-card p-8 w-full max-w-sm text-center"
            >
              <div className="w-14 h-14 rounded-full bg-red-400/10 border border-red-400/20 flex items-center justify-center mx-auto mb-4">
                <Trash2 size={24} className="text-red-400" />
              </div>
              <h3 className="text-lg font-bold mb-2">Delete Question?</h3>
              <p className="text-gray-400 text-sm mb-7">This action cannot be undone.</p>
              <div className="flex gap-3">
                <button onClick={() => setDeleteTarget(null)} className="btn-secondary flex-1 py-2.5 text-sm">
                  Cancel
                </button>
                <button onClick={handleDelete} className="btn-danger flex-1 py-2.5 text-sm">
                  Delete
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
