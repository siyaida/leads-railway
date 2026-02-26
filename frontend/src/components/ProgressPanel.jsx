import { useState, useEffect, useRef } from 'react'
import api from '../api/client'

export default function ProgressPanel({ sessionId, onComplete }) {
  const [status, setStatus] = useState('pending')
  const [progress, setProgress] = useState(1)
  const [logs, setLogs] = useState([])
  const [message, setMessage] = useState('Starting...')
  const afterRef = useRef(0)
  const logEndRef = useRef(null)
  const intervalRef = useRef(null)

  useEffect(() => {
    if (!sessionId) return

    const poll = async () => {
      try {
        const res = await api.get(`/pipeline/${sessionId}/status`, {
          params: { after: afterRef.current },
        })
        const data = res.data

        setStatus(data.status)
        setMessage(data.message)

        if (data.progress_pct > 0) {
          setProgress((prev) => Math.max(prev, data.progress_pct))
        }

        if (data.logs && data.logs.length > 0) {
          setLogs((prev) => [...prev, ...data.logs])
          afterRef.current += data.logs.length
        }

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(intervalRef.current)
          if (data.status === 'completed' && onComplete) {
            onComplete()
          }
        }
      } catch {
        // silently retry
      }
    }

    poll()
    intervalRef.current = setInterval(poll, 1500)

    return () => clearInterval(intervalRef.current)
  }, [sessionId])

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const isActive = status !== 'completed' && status !== 'failed'

  return (
    <div className="progress-panel">
      <div className="progress-header">
        <h3>
          {isActive && <span className="spinner" />}
          {status === 'completed' ? 'Pipeline Complete' : status === 'failed' ? 'Pipeline Failed' : 'Running Pipeline...'}
        </h3>
        <span className="progress-pct">{Math.round(progress)}%</span>
      </div>

      <div className="progress-bar-container">
        <div
          className={`progress-bar-fill ${status === 'failed' ? 'error' : ''} ${status === 'completed' ? 'complete' : ''}`}
          style={{ width: `${progress}%` }}
        />
      </div>

      <p className="progress-message">{message}</p>

      <div className="log-feed">
        {logs.map((entry, i) => (
          <div key={i} className="log-entry">
            <span className="log-emoji">{entry.emoji}</span>
            <span className="log-text">{entry.message}</span>
            <span className="log-time">
              {new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </span>
          </div>
        ))}
        <div ref={logEndRef} />
      </div>
    </div>
  )
}
