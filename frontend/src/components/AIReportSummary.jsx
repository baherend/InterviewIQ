import React from 'react'
import {
  Award,
  CheckCircle2,
  MessageSquare,
  Target,
  TrendingUp,
  Video,
  Volume2,
} from 'lucide-react'

const isUsableNumber = (value) =>
  typeof value === 'number' && Number.isFinite(value) && value >= 0

const boundedScore = (value) =>
  isUsableNumber(value) ? Math.min(100, Math.max(0, value)) : null

const ratioAsScore = (value) => {
  if (!isUsableNumber(value)) return null
  return value <= 1 ? value * 100 : Math.min(100, value)
}

const unique = (items) => [...new Set(items.filter(Boolean))]

const assessmentColor = (level) => {
  if (level.includes('Strong') || level === 'Maintain Performance') return 'green'
  if (level.includes('Moderate') || level === 'Focused Development') return 'amber'
  if (level.includes('Developing')) return 'blue'
  return 'slate'
}

const getTechnicalAssessment = ({ score, answerIsInvalid, precision, coverage }) => {
  if (answerIsInvalid) {
    return {
      level: 'Developing',
      color: 'blue',
      summary: 'The response did not align closely enough with the selected question to demonstrate the expected technical understanding.',
      recommendation: 'Begin with a direct answer to the selected question, then support it with the relevant concept and an example.',
    }
  }

  if (score == null) {
    return {
      level: 'Limited Evidence',
      color: 'slate',
      summary: 'The available response did not provide enough technical evidence for a reliable interpretation.',
      recommendation: null,
    }
  }

  if (score >= 60) {
    const summary = coverage != null && coverage < 65
      ? 'The response demonstrated strong understanding of the main concept, with room to broaden the supporting detail.'
      : 'The response demonstrated strong understanding of the topic and connected the main concept with relevant supporting detail.'
    return {
      level: 'Strong',
      color: 'green',
      summary,
      recommendation: coverage != null && coverage < 65
        ? 'Add one more supporting detail or practical example to make the answer more complete.'
        : 'Maintain this level of technical focus and supporting explanation.',
    }
  }

  if (score >= 45) {
    const summary = coverage != null && coverage < 45
      ? 'The response addressed the main technical concept, but the supporting explanation covered only part of the expected detail.'
      : 'The response addressed the main technical concept and included relevant ideas, with an opportunity to explain them more fully.'
    return {
      level: 'Moderate',
      color: 'amber',
      summary,
      recommendation: precision != null && precision < 45
        ? 'Organize the answer around the core concept before adding secondary details.'
        : 'Deepen the answer with a concrete implementation detail or practical example.',
    }
  }

  return {
    level: 'Developing',
    color: 'blue',
    summary: score < 20
      ? 'The response showed limited alignment with the expected technical concept.'
      : 'The response included some relevant technical ideas but did not yet explain the main concept clearly or completely.',
    recommendation: coverage != null && coverage < 35
      ? 'Start with a concise definition, then explain how the concept works and where it is used.'
      : 'Connect each technical point to the question and support it with a practical example.',
  }
}

const getCommunicationAssessment = ({ score, vocal }) => {
  const speakingRate = isUsableNumber(vocal.speaking_rate_wpm)
    ? vocal.speaking_rate_wpm
    : null
  const pauseControl = ratioAsScore(vocal.pause_control_score)
  const volumeStability = ratioAsScore(vocal.volume_stability_score)
  const speechContinuity = ratioAsScore(vocal.speech_continuity_score)
  const hasDeliveryMetrics = [speakingRate, pauseControl, volumeStability, speechContinuity]
    .some((value) => value != null)

  if (vocal.sufficient_evidence === false || (score == null && !hasDeliveryMetrics)) {
    return {
      level: 'Limited Evidence',
      color: 'slate',
      summary: 'The available audio did not provide enough consistent speech evidence for a reliable communication assessment.',
      recommendation: null,
    }
  }

  const paceIsFast = speakingRate != null && speakingRate > 175
  const paceIsSlow = speakingRate != null && speakingRate < 90
  const paceIsBalanced = speakingRate != null && !paceIsFast && !paceIsSlow
  const pausesAreControlled = pauseControl != null && pauseControl >= 65
  const pausesNeedWork = pauseControl != null && pauseControl < 55
  const volumeNeedsWork = volumeStability != null && volumeStability < 60
  const continuityNeedsWork = speechContinuity != null && speechContinuity < 60
  const deliveryConcerns = [paceIsFast || paceIsSlow, pausesNeedWork, volumeNeedsWork, continuityNeedsWork]
    .filter(Boolean).length
  const deliveryStrengths = [
    paceIsBalanced,
    pausesAreControlled,
    volumeStability != null && volumeStability >= 70,
    speechContinuity != null && speechContinuity >= 70,
  ].filter(Boolean).length

  const level = score != null && score >= 75 && deliveryConcerns <= 1
    ? 'Strong'
    : ((score != null && score >= 50) || deliveryStrengths >= 2) && deliveryConcerns <= 2
      ? 'Moderate'
      : 'Developing'

  const positiveClauses = []
  if (paceIsBalanced) positiveClauses.push('maintained a balanced speaking pace')
  if (pausesAreControlled) positiveClauses.push('used pauses effectively')
  if (volumeStability != null && volumeStability >= 70) positiveClauses.push('kept vocal volume consistent')
  if (speechContinuity != null && speechContinuity >= 70) positiveClauses.push('moved smoothly between ideas')

  const concernClauses = []
  if (paceIsFast) concernClauses.push('The speaking pace was relatively fast and may reduce explanation clarity.')
  if (paceIsSlow) concernClauses.push('The speaking pace was slower than needed and may reduce momentum.')
  if (continuityNeedsWork) concernClauses.push('Flow between ideas was less consistent.')
  if (volumeNeedsWork) concernClauses.push('Vocal volume varied across the response.')
  if (pausesNeedWork) concernClauses.push('Pauses did not consistently support the answer structure.')

  const positiveSummary = positiveClauses.length
    ? `The candidate ${positiveClauses.slice(0, 2).join(' and ')}.`
    : level === 'Developing'
      ? 'Speech delivery showed inconsistent control across the response.'
      : 'The response remained understandable across the available audio.'
  const summary = `${positiveSummary}${concernClauses.length ? ` ${concernClauses.slice(0, 2).join(' ')}` : ''}`

  let recommendation = 'Maintain the current pace and controlled delivery.'
  if (paceIsFast) recommendation = 'Maintain clarity while reducing speaking speed slightly.'
  else if (paceIsSlow) recommendation = 'Use a slightly more active pace while keeping each point clear.'
  else if (continuityNeedsWork) recommendation = 'Practice smoother transitions between technical points.'
  else if (volumeNeedsWork) recommendation = 'Keep vocal volume more consistent from one point to the next.'
  else if (pausesNeedWork) recommendation = 'Use deliberate pauses to separate the answer into clear sections.'

  return { level, color: assessmentColor(level), summary, recommendation }
}

const getVisualEvidenceAssessment = ({ score, visual, vision }) => {
  const windowCount = isUsableNumber(visual.number_of_windows)
    ? visual.number_of_windows
    : null
  const faceVisibility = ratioAsScore(
    visual.metrics?.mean_face_detection_ratio ?? visual.mean_face_detection_ratio
  )
  const reliability = ratioAsScore(
    visual.metrics?.visual_reliability ?? visual.visual_reliability
  )
  const enoughFaces = visual.evidence_checks?.enough_faces
  const enoughWindows = visual.evidence_checks?.enough_windows
  const sourceSaysSufficient = visual.sufficient_evidence === true
    || vision?.sufficient_evidence === true
  const sourceSaysInsufficient = visual.sufficient_evidence === false
    || vision?.sufficient_evidence === false
  const shortSample = windowCount != null && windowCount <= 3
  const faceEvidenceIsLimited = enoughFaces === false
    || (faceVisibility != null && faceVisibility < 60)
  const frameEvidenceIsLimited = enoughWindows === false
    || (reliability != null && reliability < 55)

  if (sourceSaysInsufficient || !sourceSaysSufficient || shortSample
      || faceEvidenceIsLimited || frameEvidenceIsLimited || score == null) {
    let summary = 'Visual features were extracted, but the available behavioral signals were insufficient for a strong interpretation.'
    let recommendation = 'Use a longer response if a more representative visual evidence sample is required.'

    if (faceEvidenceIsLimited) {
      summary = 'Face-visible evidence was inconsistent, so the visual result is not strong enough for a candidate-level interpretation.'
      recommendation = 'Keep the face visible throughout the recording if visual feedback is required.'
    } else if (frameEvidenceIsLimited) {
      summary = 'Frame coverage was not consistent enough to support a reliable visual interpretation.'
      recommendation = 'Use a recording with clearer, more continuous visual coverage.'
    } else if (shortSample) {
      summary = 'Visual features were successfully extracted, but the short recording provided limited behavioral evidence.'
    }

    return { level: 'Limited Evidence', color: 'slate', summary, recommendation }
  }

  if (score >= 70) {
    return {
      level: 'Strong',
      color: 'green',
      summary: 'The available visual signals remained consistent across the recorded response.',
      recommendation: 'Maintain the same steady on-camera presentation.',
    }
  }

  if (score >= 45) {
    return {
      level: 'Moderate',
      color: 'amber',
      summary: 'The recording provided usable visual evidence, with some variation across the observed response.',
      recommendation: 'Maintain a steadier visible presence across the full answer.',
    }
  }

  return {
    level: 'Developing',
    color: 'blue',
    summary: 'The recording provided sufficient visual coverage, but the observed signals were not consistent across the response.',
    recommendation: 'Practice a more consistent on-camera presentation throughout the answer.',
  }
}

const getDevelopmentRecommendations = ({ technical, communication, visual }) => {
  const recommendation = unique([
    ['Moderate', 'Developing'].includes(technical.level) ? technical.recommendation : null,
    ['Moderate', 'Developing'].includes(communication.level) ? communication.recommendation : null,
    visual.level === 'Developing' ? visual.recommendation : null,
  ])
  return {
    level: recommendation.length ? 'Focused Development' : 'Maintain Performance',
    color: recommendation.length ? 'amber' : 'green',
    summary: recommendation.length
      ? 'Development priorities are drawn only from the evidence that showed a specific gap.'
      : 'The available evidence did not identify a priority development gap.',
    recommendation,
  }
}

const getOverallAssessment = ({
  technical,
  communication,
  visual,
  technicalScore,
  communicationScore,
  visualScore,
  answerIsInvalid,
}) => {
  const availableScores = []
  if (technicalScore != null) availableScores.push(technicalScore)
  if (communication.level !== 'Limited Evidence' && communicationScore != null) {
    availableScores.push(communicationScore)
  }
  if (visual.level !== 'Limited Evidence' && visualScore != null) availableScores.push(visualScore)

  const composite = availableScores.length
    ? availableScores.reduce((sum, value) => sum + value, 0) / availableScores.length
    : null
  const level = answerIsInvalid || composite == null || composite < 45
    ? 'Developing'
    : composite >= 75
      ? 'Strong Performance'
      : 'Moderate Performance'

  if (answerIsInvalid) {
    return {
      level,
      color: 'blue',
      summary: communication.level === 'Strong'
        ? 'The candidate demonstrated controlled delivery, but the response did not address the selected technical question closely enough.'
        : 'The available response did not address the selected technical question closely enough for a complete candidate evaluation.',
      recommendation: technical.recommendation,
    }
  }

  if (level === 'Strong Performance') {
    return {
      level,
      color: 'green',
      summary: 'The candidate demonstrated strong technical understanding with clear and controlled delivery across the available evidence.',
      recommendation: null,
    }
  }

  if (level === 'Moderate Performance') {
    const summary = technical.level === 'Strong'
      ? 'The candidate demonstrated strong technical understanding, with opportunities to make the delivery more consistent.'
      : communication.level === 'Strong'
        ? 'The candidate communicated clearly and demonstrated acceptable technical understanding, with opportunities to deepen the answer.'
        : 'The candidate demonstrated an acceptable foundation, with opportunities to improve answer depth and delivery consistency.'
    return {
      level,
      color: 'amber',
      summary,
      recommendation: technical.level === 'Strong'
        ? communication.recommendation
        : technical.recommendation,
    }
  }

  const summary = ['Strong', 'Moderate'].includes(communication.level)
    ? 'The candidate showed usable communication strengths, while the technical response needs clearer alignment, structure, and depth.'
    : technical.level === 'Strong'
      ? 'The candidate demonstrated technical understanding, while the spoken delivery would benefit from greater control and continuity.'
      : visual.level === 'Limited Evidence'
        ? 'The response shows an early foundation, while technical depth and communication consistency remain the clearest development priorities; visual evidence was limited.'
        : 'The response shows an early foundation, with development opportunities in technical depth and delivery consistency.'
  return {
    level,
    color: 'blue',
    summary,
    recommendation: technical.level === 'Developing'
      ? technical.recommendation
      : communication.recommendation,
  }
}

const semanticTones = {
  green: {
    badge: 'border-emerald-400/35 bg-emerald-400/10 text-emerald-300',
    icon: 'border-emerald-400/25 bg-emerald-400/10 text-emerald-300',
    level: 'text-emerald-300',
    dot: 'bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.55)]',
  },
  amber: {
    badge: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
    icon: 'border-amber-400/20 bg-amber-400/10 text-amber-200',
    level: 'text-amber-200',
    dot: 'bg-amber-200 shadow-[0_0_18px_rgba(253,230,138,0.5)]',
  },
  blue: {
    badge: 'border-blue-400/30 bg-blue-400/10 text-blue-200',
    icon: 'border-blue-400/20 bg-blue-400/10 text-blue-200',
    level: 'text-blue-200',
    dot: 'bg-blue-300 shadow-[0_0_18px_rgba(147,197,253,0.5)]',
  },
  slate: {
    badge: 'border-slate-400/30 bg-slate-400/10 text-slate-300',
    icon: 'border-slate-400/20 bg-slate-400/10 text-slate-300',
    level: 'text-slate-300',
    dot: 'bg-slate-300',
  },
}

const tone = (color) => semanticTones[color] || semanticTones.slate

const getEvaluationStatusTextColor = ({ dimension, level, fallbackColor }) => {
  if (dimension === 'content') {
    if (level === 'Strong') return semanticTones.green.level
    if (level === 'Moderate') return semanticTones.amber.level
    return 'text-rose-300'
  }

  if (dimension === 'communication' && level === 'Moderate') {
    return semanticTones.amber.level
  }

  if (dimension === 'visual-evidence' && level === 'Limited Evidence') {
    return semanticTones.blue.level
  }

  return tone(fallbackColor).level
}

const EvaluationCard = ({
  icon: Icon,
  title,
  narrative,
  dimension,
}) => {
  const colors = tone(narrative.color)
  const statusTextColor = getEvaluationStatusTextColor({
    dimension,
    level: narrative.level,
    fallbackColor: narrative.color,
  })
  return (
    <article className="rounded-2xl border border-white/10 bg-white/[0.035] p-6">
      <div className={`mb-5 inline-flex rounded-xl border p-3 ${colors.icon}`}>
        <Icon size={24} aria-hidden="true" />
      </div>
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-gray-400">{title}</p>
      <p className={`mt-3 text-2xl font-black ${statusTextColor}`}>{narrative.level}</p>
      <p className="mt-3 text-base leading-7 text-gray-300">{narrative.summary}</p>
      {narrative.recommendation && (
        <div className="mt-5 border-t border-white/10 pt-4">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-gray-500">
            DEVELOPMENT FOCUS
          </p>
          <p className="mt-2 text-sm leading-6 text-gray-400">{narrative.recommendation}</p>
        </div>
      )}
    </article>
  )
}

export default function AIReportSummary({ result }) {
  if (!result) return null

  const confidence = result.confidence || {}
  const vocal = confidence.vocal || {}
  const visual = confidence.visual || {}
  const technicalScore = boundedScore(
    result.fusion_summary?.final_technical_score
      ?? result.technical_score
      ?? result.nlp?.technical_score
  )
  const communicationScore = boundedScore(
    vocal.vocal_confidence_score
      ?? result.vocal_confidence_score
      ?? confidence.final_confidence_score
      ?? result.final_confidence_score
  )
  const visualScore = boundedScore(
    visual.visual_behavioral_confidence_score
      ?? visual.visual_confidence_score
      ?? result.visual_behavioral_confidence_score
  )
  const answerIsInvalid = result.question_answer_validity?.valid === false
  const technical = getTechnicalAssessment({
    score: technicalScore,
    answerIsInvalid,
    precision: ratioAsScore(result.nlp?.precision),
    coverage: ratioAsScore(result.nlp?.coverage),
  })
  const communication = getCommunicationAssessment({ score: communicationScore, vocal })
  const visualEvidence = getVisualEvidenceAssessment({
    score: visualScore,
    visual,
    vision: result.vision,
  })
  const overall = getOverallAssessment({
    technical,
    communication,
    visual: visualEvidence,
    technicalScore,
    communicationScore,
    visualScore,
    answerIsInvalid,
  })

  const strengths = []
  if (technical.level === 'Strong') {
    strengths.push('The candidate demonstrated strong understanding of the main technical concept.')
  } else if (technical.level === 'Moderate') {
    strengths.push('The answer addressed the main technical concept and included relevant supporting ideas.')
  } else if (ratioAsScore(result.nlp?.coverage) >= 20) {
    strengths.push('The response included some terminology relevant to the selected topic.')
  }

  const speakingRate = isUsableNumber(vocal.speaking_rate_wpm)
    ? vocal.speaking_rate_wpm
    : null
  const pauseControl = ratioAsScore(vocal.pause_control_score)
  const volumeStability = ratioAsScore(vocal.volume_stability_score)
  const speechContinuity = ratioAsScore(vocal.speech_continuity_score)
  if (speakingRate != null && speakingRate >= 90 && speakingRate <= 175) {
    strengths.push('The candidate maintained a balanced speaking pace.')
  }
  if (pauseControl != null && pauseControl >= 65) {
    strengths.push('The candidate used pauses effectively to support the spoken response.')
  }
  if (volumeStability != null && volumeStability >= 70
      && speechContinuity != null && speechContinuity >= 70) {
    strengths.push('The response maintained consistent vocal delivery between ideas.')
  }
  if (visualEvidence.level === 'Strong') {
    strengths.push('The candidate maintained consistent visible presentation across the recording.')
  }

  const candidateStrengths = unique(strengths).slice(0, 3)
  const recommendationNarrative = getDevelopmentRecommendations({
    technical,
    communication,
    visual: visualEvidence,
  })
  const recommendations = recommendationNarrative.recommendation.slice(0, 3)
  const overallTone = tone(overall.color)

  return (
    <section data-testid="ai-report-summary" aria-labelledby="assessment-title" className="space-y-6">
      <article className="glass-card overflow-hidden p-7 md:p-9">
        <div className="max-w-5xl">
          <h2 id="assessment-title" className="text-4xl font-black tracking-tight text-white md:text-5xl">
            AI Interview Evaluation Report
          </h2>
          <div className={`mt-7 inline-flex max-w-full items-center gap-4 rounded-2xl border px-6 py-5 md:px-7 ${overallTone.badge}`}>
            <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl border ${overallTone.icon}`}>
              <Award size={27} aria-hidden="true" />
            </div>
            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-[0.18em]">Overall performance</p>
              <div className="mt-2 flex items-center gap-3">
                <span className={`h-3 w-3 shrink-0 rounded-full ${overallTone.dot}`} aria-hidden="true" />
                <p data-testid="overall-performance" className="text-2xl font-black md:text-3xl">
                  {overall.level}
                </p>
              </div>
            </div>
          </div>
        </div>
      </article>

      <div className="grid gap-6 lg:grid-cols-2">
        <article className="glass-card p-7">
          <h2 className="flex items-center gap-3 text-2xl font-bold text-white">
            <CheckCircle2 className="text-emerald-300" size={26} aria-hidden="true" />
            Candidate Strengths
          </h2>
          {candidateStrengths.length ? (
            <ul className="mt-6 space-y-4 text-base leading-7 text-gray-300">
              {candidateStrengths.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-emerald-300" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-base leading-7 text-gray-400">
              The available evidence did not support a specific candidate strength.
            </p>
          )}
        </article>

        <article className="glass-card p-7">
          <h2 className="flex items-center gap-3 text-2xl font-bold text-white">
            <TrendingUp className="text-amber-200" size={26} aria-hidden="true" />
            Development Areas
          </h2>
          {recommendations.length ? (
            <ul className="mt-6 space-y-4 text-base leading-7 text-gray-300">
              {recommendations.map((item) => (
                <li key={item} className="flex gap-3">
                  <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-amber-200" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-6 text-base leading-7 text-gray-400">
              No priority development area was identified from the available evidence.
            </p>
          )}
        </article>
      </div>

      <article className="glass-card p-7 md:p-8">
        <div className="mb-6">
          <p className="text-sm font-bold uppercase tracking-[0.22em] text-cyan-300">Evaluation overview</p>
          <h2 className="mt-2 text-3xl font-black text-white">Detailed Evaluation</h2>
        </div>
        <div className="grid gap-5 lg:grid-cols-3">
          <EvaluationCard
            icon={Target}
            title="Content Answer"
            narrative={technical}
            dimension="content"
          />
          <EvaluationCard
            icon={Volume2}
            title="Communication"
            narrative={communication}
            dimension="communication"
          />
          <EvaluationCard
            icon={Video}
            title="Visual Evidence Analysis"
            narrative={visualEvidence}
            dimension="visual-evidence"
          />
        </div>
      </article>

      <div className="flex items-start gap-3 rounded-2xl border border-cyan-400/20 bg-cyan-400/5 p-5 text-sm leading-6 text-gray-400">
        <MessageSquare className="mt-0.5 shrink-0 text-cyan-300" size={20} aria-hidden="true" />
        <p>
          Use this report as interviewer support. It summarizes observable answer, speech, and video evidence and is not a personality judgment or an automated hiring decision.
        </p>
      </div>
    </section>
  )
}
