import { useState } from 'react'
import {
  ChevronDown,
  CheckCircle,
  AlertTriangle,
  Mic,
  Eye,
  Award,
  Activity
} from 'lucide-react'

export default function DetailedMetricsDashboard({ result }) {
  const [open, setOpen] = useState(true)

  const fusion = result?.fusion_summary || {}
  const vocal = result?.confidence?.vocal || {}
  const visual = result?.confidence?.visual || {}
  const validity = result?.question_answer_validity || {}

  const contentScore =
    fusion.final_technical_score ??
    result?.technical_score

  const vocalScore =
    vocal.vocal_confidence_score ??
    result?.vocal_confidence_score

  const visualScore =
    visual.visual_behavioral_confidence_score ??
    result?.visual_behavioral_confidence_score

  const deliveryScore =
    result?.delivery_confidence_score ??
    (
      (Number(vocalScore || 0) * 0.60) +
      (Number(visualScore || 0) * 0.40)
    )

  const formatPercent = (value) => {
    if (value == null) return 'N/A'
    if (value <= 1) return `${(value * 100).toFixed(1)}%`
    return `${value.toFixed(1)}%`
  }

  const cards = [
    {
      title: 'Engineering Status',
      value: 'Success',
      subtitle: 'Pipeline execution state, not candidate performance.',
      icon: <Activity size={20} />
    },
    {
      title: 'Question-Answer Validity',
      value: validity.valid ? 'Valid' : 'Invalid',
      subtitle: validity.reason || 'Transcript-question matching result.',
      icon: <CheckCircle size={20} />
    },
    {
      title: 'Answer Content Score',
      value: formatPercent(contentScore),
      subtitle: 'Candidate technical performance score.',
      icon: <Award size={20} />
    },
    {
      title: 'Delivery Confidence',
      value: formatPercent(deliveryScore),
      subtitle: 'Experimental behavioral score.',
      icon: <Mic size={20} />
    },
    {
      title: 'Vocal Confidence',
      value: formatPercent(vocalScore),
      subtitle: 'Speech delivery confidence indicator.',
      icon: <Mic size={20} />
    },
    {
      title: 'Visual Behavioral Confidence',
      value: formatPercent(visualScore),
      subtitle: 'Visual evidence based behavioral score.',
      icon: <Eye size={20} />
    }
  ]

  return (
    <div className="glass-card p-6">

      <button
        onClick={() => setOpen(!open)}
        className="w-full flex justify-between items-center"
      >
        <h3 className="text-lg font-bold">
          Detailed Metrics Dashboard
        </h3>

        <ChevronDown
          size={20}
          className={`transition-transform ${
            open ? 'rotate-180' : ''
          }`}
        />
      </button>


      {open && (
        <div className="mt-6 space-y-6">

          <div className="grid md:grid-cols-3 gap-4">

            {cards.map((card) => (
              <div
                key={card.title}
                className="border border-white/10 rounded-xl p-5"
              >

                <div className="flex gap-2 items-center text-gray-400 text-sm mb-3">
                  {card.icon}
                  {card.title}
                </div>

                <div className="text-2xl font-black text-white">
                  {card.value}
                </div>

                <p className="text-xs text-gray-500 mt-2">
                  {card.subtitle}
                </p>

              </div>
            ))}

          </div>


          <div className="border border-white/10 rounded-xl p-5">

            <h4 className="font-bold mb-4 flex gap-2 items-center">
              <Mic size={18}/>
              Audio Delivery Features
            </h4>


            <div className="grid md:grid-cols-4 gap-4 text-sm">

              <Metric
                label="Speaking Rate"
                value={`${vocal.speaking_rate_wpm ?? 'N/A'} WPM`}
              />

              <Metric
                label="Pause Control"
                value={formatPercent(vocal.pause_control_score)}
              />

              <Metric
                label="Volume Stability"
                value={formatPercent(vocal.volume_stability_score)}
              />

              <Metric
                label="Speech Continuity"
                value={formatPercent(vocal.speech_continuity_score)}
              />

            </div>

          </div>



          <div className="border border-white/10 rounded-xl p-5">

            <h4 className="font-bold mb-4 flex gap-2 items-center">
              <Eye size={18}/>
              Visual Behavioral Confidence
            </h4>


            <div className="grid md:grid-cols-4 gap-4">

              <Metric
                label="Visual Score"
                value={formatPercent(visualScore)}
              />

              <Metric
                label="Level"
                value={visualScore >= 70 ? 'HIGH' :
                  visualScore >= 45 ? 'MEDIUM' : 'LOW'}
              />

              <Metric
                label="Sufficient Evidence"
                value={
                  visual.sufficient_evidence === false
                    ? 'No'
                    : 'Yes'
                }
              />

              <Metric
                label="Number of Windows"
                value={
                  visual.analysis_window_count ??
                  visual.number_of_windows ??
                  'N/A'
                }
              />

            </div>

          </div>


          <div className="border border-white/10 rounded-xl p-5">

            <h4 className="font-bold mb-3">
              Question Answer Validity
            </h4>

            <div className="flex gap-2 items-center">

              {validity.valid ? (
                <>
                  <CheckCircle className="text-green-400" size={18}/>
                  Valid Answer
                </>
              ) : (
                <>
                  <AlertTriangle className="text-yellow-400" size={18}/>
                  {validity.reason || 'Invalid Answer'}
                </>
              )}

            </div>

          </div>


        </div>
      )}

    </div>
  )
}


function Metric({label, value}) {
  return (
    <div className="border border-white/10 rounded-lg p-3">
      <div className="text-xs text-gray-500">
        {label}
      </div>

      <div className="font-bold mt-1">
        {value}
      </div>
    </div>
  )
}