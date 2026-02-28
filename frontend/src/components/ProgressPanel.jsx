import { useState, useEffect, useRef, useCallback } from 'react'
import api from '../api/client'

export default function ProgressPanel({ sessionId, onComplete, onStatusChange }) {
  const [status, setStatus] = useState('pending')
  const [progress, setProgress] = useState(1)
  const [logs, setLogs] = useState([])
  const [message, setMessage] = useState('Starting...')
  const [pollError, setPollError] = useState(0)
  const afterRef = useRef(0)
  const logEndRef = useRef(null)
  const intervalRef = useRef(null)
  const mountedRef = useRef(true)

  const handleDone = useCallback((finalStatus) => {
    if (onComplete) onComplete(finalStatus)
  }, [onComplete])

  useEffect(() => {
    if (!sessionId) return
    mountedRef.current = true

    // Small delay before first poll to let backend initialize
    const initialDelay = setTimeout(() => {
      if (!mountedRef.current) return

      const poll = async () => {
        if (!mountedRef.current) return
        try {
          const res = await api.get(`/pipeline/${sessionId}/status`, {
            params: { after: afterRef.current },
          })
          if (!mountedRef.current) return
          const data = res.data

          setPollError(0)
          setStatus(data.status)
          setMessage(data.message)

          if (onStatusChange) onStatusChange(data.status)

          if (data.progress_pct > 0) {
            setProgress((prev) => Math.max(prev, data.progress_pct))
          }

          if (data.logs && data.logs.length > 0) {
            setLogs((prev) => [...prev, ...data.logs])
            afterRef.current += data.logs.length
          }

          if (data.status === 'completed' || data.status === 'failed') {
            clearInterval(intervalRef.current)
            handleDone(data.status)
          }
        } catch {
          setPollError((prev) => {
            const next = prev + 1
            // After 10 consecutive failures, stop polling
            if (next >= 10) {
              clearInterval(intervalRef.current)
              setMessage('Connection lost. Refresh the page to check status.')
            }
            return next
          })
        }
      }

      poll()
      intervalRef.current = setInterval(poll, 1500)
    }, 300)

    return () => {
      mountedRef.current = false
      clearTimeout(initialDelay)
      clearInterval(intervalRef.current)
    }
  }, [sessionId, handleDone, onStatusChange])

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

      {pollError >= 10 && (
        <p className="progress-error">Lost connection to server. Please refresh.</p>
      )}

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
