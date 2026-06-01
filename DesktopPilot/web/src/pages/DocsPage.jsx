import React from 'react'
import './DocsPage.css'

const sections = [
  {
    title: '1. Download & Install',
    content: [
      'Go to the home page and click "Download for Windows".',
      'Run the DesktopPilot-Setup.exe installer.',
      'The agent starts automatically and runs in the system tray.',
      'You will see a DesktopPilot icon in your taskbar notification area.',
    ]
  },
  {
    title: '2. Connect the Dashboard',
    content: [
      'Open the web dashboard at desktoppilot.vercel.app/dashboard.',
      'The dashboard connects to your local agent via WebSocket on port 8000.',
      'A green "Agent Connected" indicator confirms the connection.',
      'If disconnected, ensure the desktop agent is running.',
    ]
  },
  {
    title: '3. Voice Commands',
    content: [
      'Click the microphone button and speak your command.',
      'Release or click again to stop recording.',
      'The system transcribes your speech using Amazon Transcribe.',
      'Amazon Bedrock generates a step-by-step execution plan.',
    ]
  },
  {
    title: '4. Approval Gate',
    content: [
      'Commands that run terminal scripts, send emails, or change settings require approval.',
      'Review the plan shown on screen before approving.',
      'Click Approve to execute or Reject to cancel.',
      'Safe commands like opening apps or browsers run automatically.',
    ]
  },
  {
    title: '5. Example Commands',
    content: [
      '"Open Chrome"',
      '"Open VS Code"',
      '"Open my EduPulse project"',
      '"Prepare my development environment"',
      '"Open my latest resume"',
      '"Search AWS Bedrock documentation"',
      '"Open Gmail and draft an email to the team"',
      '"Open Bluetooth settings"',
      '"Open my project" — recalls your last used project automatically',
    ]
  },
  {
    title: '6. Project Registry',
    content: [
      'The agent scans common directories for projects on first run.',
      'Projects are stored in a local SQLite database.',
      'You can add projects manually via the agent settings.',
      'Supported frameworks: Django, Node.js, React, FastAPI, and more.',
    ]
  },
  {
    title: '7. AWS Services Used',
    content: [
      'Amazon Transcribe — converts your voice to text',
      'Amazon Bedrock (Claude 3 Sonnet) — understands intent and plans actions',
      'AWS Lambda — serverless functions for voice, planning, and memory',
      'AWS Step Functions — orchestrates the full pipeline',
      'Amazon DynamoDB — stores command history and user preferences',
      'Amazon S3 — stores audio files and the installer download',
      'Amazon CloudWatch — logs and monitors all executions',
    ]
  },
]

export default function DocsPage() {
  return (
    <main className="docs container">
      <div className="docs-header">
        <h1>Documentation</h1>
        <p className="text-muted">Everything you need to set up and use DesktopPilot AI.</p>
      </div>

      <div className="docs-body">
        <nav className="docs-nav card">
          <p className="card-title text-muted text-sm">On this page</p>
          <ul>
            {sections.map((s, i) => (
              <li key={i}>
                <a href={`#section-${i}`}>{s.title}</a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="docs-content">
          {sections.map((s, i) => (
            <section key={i} id={`section-${i}`} className="docs-section card">
              <h2>{s.title}</h2>
              <ul className="docs-list">
                {s.content.map((line, j) => (
                  <li key={j}>{line}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </main>
  )
}
