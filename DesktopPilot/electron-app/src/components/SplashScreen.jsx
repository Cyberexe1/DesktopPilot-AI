import React, { useEffect, useState } from 'react'
import './SplashScreen.css'

const BOOT_STEPS = [
  { id: 'core',    label: 'Initializing core systems'   },
  { id: 'ai',      label: 'Loading AI engine'           },
  { id: 'voice',   label: 'Calibrating voice interface' },
  { id: 'connect', label: 'Establishing connections'    },
  { id: 'ready',   label: 'ASTRA online'                },
]

export default function SplashScreen({ onComplete }) {
  const [phase, setPhase]         = useState('enter')
  const [stepIndex, setStepIndex] = useState(-1)
  const [progress, setProgress]   = useState(0)

  useEffect(() => {
    // Step timings
    const delays = [900, 1600, 2350, 3050, 3750]
    const timers = delays.map((ms, i) => setTimeout(() => setStepIndex(i), ms))

    // Smooth progress 0 → 100 over 5000 ms
    const start = Date.now()
    const raf = setInterval(() => {
      const pct = Math.min(100, ((Date.now() - start) / 5000) * 100)
      setProgress(pct)
      if (pct >= 100) clearInterval(raf)
    }, 16)

    const exitTimer = setTimeout(() => setPhase('exit'), 5300)
    const doneTimer = setTimeout(() => onComplete?.(), 5900)

    return () => {
      timers.forEach(clearTimeout)
      clearInterval(raf)
      clearTimeout(exitTimer)
      clearTimeout(doneTimer)
    }
  }, [onComplete])

  return (
    <div className={`splash splash--${phase}`} aria-label="ASTRA starting up">

      {/* ── Background ──────────────────────────────────────── */}
      <div className="splash__bg">
        <div className="splash__nebula splash__nebula--1" />
        <div className="splash__nebula splash__nebula--2" />
        <div className="splash__nebula splash__nebula--3" />
        <div className="splash__nebula splash__nebula--4" />
        <div className="splash__grid" />
      </div>

      {/* ── Rings (all absolutely centered) ─────────────────── */}
      <div className="splash__rings" aria-hidden="true">

        {/* Ring 1 — outermost slow CW */}
        <div className="splash__ring splash__ring--1">
          <svg viewBox="0 0 560 560" fill="none">
            <circle cx="280" cy="280" r="268"
              stroke="url(#r1)" strokeWidth="1"
              strokeDasharray="4 18" />
            <defs>
              <linearGradient id="r1" gradientTransform="rotate(90)">
                <stop offset="0%"   stopColor="#cc2200" stopOpacity="0.7" />
                <stop offset="40%"  stopColor="#ff3322" stopOpacity="0.15" />
                <stop offset="100%" stopColor="#cc2200" stopOpacity="0.7" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Ring 2 — second CCW */}
        <div className="splash__ring splash__ring--2">
          <svg viewBox="0 0 440 440" fill="none">
            <circle cx="220" cy="220" r="210"
              stroke="url(#r2)" strokeWidth="1.5"
              strokeDasharray="2 10" />
            <defs>
              <linearGradient id="r2" gradientTransform="rotate(130)">
                <stop offset="0%"   stopColor="#ff3322" stopOpacity="0.9" />
                <stop offset="50%"  stopColor="#cc2200" stopOpacity="0.1" />
                <stop offset="100%" stopColor="#ff3322" stopOpacity="0.9" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Ring 3 — third CW, solid arc */}
        <div className="splash__ring splash__ring--3">
          <svg viewBox="0 0 330 330" fill="none">
            <circle cx="165" cy="165" r="155"
              stroke="url(#r3)" strokeWidth="2"
              strokeDasharray="60 240" />
            <defs>
              <linearGradient id="r3" gradientTransform="rotate(60)">
                <stop offset="0%"   stopColor="#ff3322" stopOpacity="1" />
                <stop offset="100%" stopColor="#cc2200" stopOpacity="0" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* Ring 4 — inner pulsing circle */}
        <div className="splash__ring splash__ring--4" />

      </div>

      {/* ── Core logo block ───────────────────────────────────── */}
      <div className="splash__center">

        {/* Hex shape */}
        <div className="splash__hex">
          <svg viewBox="0 0 160 185" fill="none" className="splash__hex-svg">
            {/* outer hex */}
            <polygon
              points="80,6 154,45 154,140 80,179 6,140 6,45"
              stroke="#cc2200" strokeWidth="1.5"
              fill="rgba(204,34,0,0.05)"
            />
            {/* inner hex */}
            <polygon
              points="80,26 134,57 134,128 80,159 26,128 26,57"
              stroke="#ff3322" strokeWidth="1"
              fill="rgba(255,51,34,0.03)"
              opacity="0.5"
            />
          </svg>

          {/* AI symbol inside hex */}
          <div className="splash__hex-icon">
            <svg viewBox="0 0 64 64" fill="none" width="64" height="64">
              {/* outer ring */}
              <circle cx="32" cy="32" r="18" stroke="#ff3322" strokeWidth="1.5" fill="none" />
              {/* spokes */}
              <line x1="32" y1="6"  x2="32" y2="14" stroke="#cc2200" strokeWidth="2" strokeLinecap="round"/>
              <line x1="32" y1="50" x2="32" y2="58" stroke="#cc2200" strokeWidth="2" strokeLinecap="round"/>
              <line x1="6"  y1="32" x2="14" y2="32" stroke="#cc2200" strokeWidth="2" strokeLinecap="round"/>
              <line x1="50" y1="32" x2="58" y2="32" stroke="#cc2200" strokeWidth="2" strokeLinecap="round"/>
              {/* diagonal spokes */}
              <line x1="14" y1="14" x2="20" y2="20" stroke="#cc2200" strokeWidth="1.2" strokeLinecap="round" opacity="0.5"/>
              <line x1="44" y1="44" x2="50" y2="50" stroke="#cc2200" strokeWidth="1.2" strokeLinecap="round" opacity="0.5"/>
              <line x1="50" y1="14" x2="44" y2="20" stroke="#cc2200" strokeWidth="1.2" strokeLinecap="round" opacity="0.5"/>
              <line x1="14" y1="50" x2="20" y2="44" stroke="#cc2200" strokeWidth="1.2" strokeLinecap="round" opacity="0.5"/>
              {/* inner ring */}
              <circle cx="32" cy="32" r="8" stroke="#ff3322" strokeWidth="1" fill="none" opacity="0.6"/>
              {/* center dot */}
              <circle cx="32" cy="32" r="4" fill="#ff3322" />
              <circle cx="32" cy="32" r="2" fill="#fff" opacity="0.9" />
            </svg>
          </div>
        </div>

        {/* ASTRA name */}
        <h1 className="splash__name">
          {'ASTRA'.split('').map((ch, i) => (
            <span key={i} className="splash__letter" style={{ '--i': i }}>
              {ch}
            </span>
          ))}
        </h1>

        {/* Divider line */}
        <div className="splash__divider" />

        {/* Tagline */}
        <p className="splash__tagline">
          Autonomous System &amp; Task Response Agent
        </p>

      </div>

      {/* ── Corner HUD brackets ──────────────────────────────── */}
      <div className="splash__bracket splash__bracket--tl" />
      <div className="splash__bracket splash__bracket--tr" />
      <div className="splash__bracket splash__bracket--bl" />
      <div className="splash__bracket splash__bracket--br" />

      {/* ── Bottom section: log + progress ──────────────────── */}
      <div className="splash__bottom">

        {/* Boot log */}
        <div className="splash__log">
          {BOOT_STEPS.map((step, i) => (
            <div
              key={step.id}
              className={[
                'splash__log-line',
                i <= stepIndex ? 'splash__log-line--active'  : '',
                i === stepIndex ? 'splash__log-line--current' : '',
              ].join(' ')}
            >
              <span className="splash__log-indicator">
                {i < stepIndex
                  ? <span className="splash__log-check">✓</span>
                  : <span className="splash__log-dot" />
                }
              </span>
              <span className="splash__log-text">{step.label}</span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="splash__progress-wrap">
          <div className="splash__progress-track">
            <div className="splash__progress-fill" style={{ width: `${progress}%` }} />
            <div className="splash__progress-tip"  style={{ left:  `${progress}%` }} />
          </div>
          <span className="splash__progress-pct">{Math.round(progress)}%</span>
        </div>

      </div>

      {/* ── Version ──────────────────────────────────────────── */}
      <div className="splash__version">DesktopPilot AI · <v1 className="1 1"></v1></div>

    </div>
  )
}
