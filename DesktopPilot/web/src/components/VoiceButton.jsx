import React from 'react'
import { Mic, MicOff, Loader } from 'lucide-react'
import './VoiceButton.css'

const STEPS = {
  IDLE:       'idle',
  LISTENING:  'listening',
  PROCESSING: 'processing',
  PLANNING:   'planning',
  APPROVING:  'approving',
  EXECUTING:  'executing',
  DONE:       'done',
  ERROR:      'error',
}

export default function VoiceButton({ step, onStart, onStop }) {
  const isListening  = step === STEPS.LISTENING
  const isBusy       = [STEPS.PROCESSING, STEPS.PLANNING, STEPS.EXECUTING].includes(step)
  const isApproving  = step === STEPS.APPROVING
  const isDone       = step === STEPS.DONE
  const isError      = step === STEPS.ERROR

  const handleClick = () => {
    if (isListening)                    return onStop()
    if (isBusy || isApproving)          return
    onStart()
  }

  const btnClass = [
    'voice-btn',
    isListening ? 'voice-btn--listening' : '',
    isBusy      ? 'voice-btn--busy'      : '',
    isDone      ? 'voice-btn--done'      : '',
    isError     ? 'voice-btn--error'     : '',
  ].filter(Boolean).join(' ')

  return (
    <button className={btnClass} onClick={handleClick} disabled={isBusy || isApproving}>
      {isBusy
        ? <Loader size={32} className="spin" />
        : isListening
          ? <MicOff size={32} />
          : <Mic size={32} />
      }
      {isListening && <span className="pulse-ring" />}
    </button>
  )
}
