import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Clock, CheckCircle, XCircle, Loader, ArrowRight } from 'lucide-react'
import PipelineForm from '../components/PipelineForm'
import ProgressPanel from '../components/ProgressPanel'
import api from '../api/client'

function StatusBadge({ status }) {
  const map = {
    pending: { icon: Clock, className: 'badge-pending', label: 'Pending' },
    searching: { icon: Loader, className: 'badge-active', label: 'Searching' },
    enriching: { icon: Loader, className: 'badge-active', label: 'Enriching' },
    generating: { icon: Loader, className: 'badge-active', label: 'Generating' },
    completed: { icon: CheckCircle, className: 'badge-completed', label: 'Completed' },
    failed: { icon: XCircle, className: 'badge-failed', label: 'Failed' },
  }
  const info = map[status] || map.pending
  const Icon = info.icon
  return (
    <span className={`badge ${info.className}`}>
      <Icon size={14} />
      {info.label}
    </span>
  )
}

export default function DashboardPage() {
  const [sessions, setSessions] = useState([])
  const [activeSession, setActiveSession] = useState(null)
  const [loadingSessions, setLoadingSessions] = useState(true)
  const navigate = useNavigate()

  const fetchSessions = async () => {
    try {
      const res = await api.get('/pipeline/sessions')
      setSessions(res.data)
    } catch {
      // silently fail
    } finally {
      setLoadingSessions(false)
    }
  }

  useEffect(() => {
    fetchSessions()
  }, [])

  const handleStarted = (session) => {
    setActiveSession(session)
    setSessions((prev) => [session, ...prev])
  }

  const handleComplete = () => {
    fetchSessions()
  }

  return (
    <div className="dashboard">
      <div className="dashboard-main">
        <div className="card">
          <h2>New Lead Search</h2>
          <PipelineForm onStarted={handleStarted} />
        </div>

        {activeSession && (
          <div className="card">
            <ProgressPanel
              sessionId={activeSession.id}
              onComplete={handleComplete}
            />
            <div style={{ marginTop: 16, textAlign: 'center' }}>
              <button
                className="btn btn-secondary"
                onClick={() => navigate(`/session/${activeSession.id}`)}
              >
                View Leads <ArrowRight size={16} />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="dashboard-sidebar">
        <div className="card">
          <h3>Recent Sessions</h3>
          {loadingSessions ? (
            <p className="text-muted">Loading...</p>
          ) : sessions.length === 0 ? (
            <p className="text-muted">No sessions yet. Run your first search above.</p>
          ) : (
            <div className="session-list">
              {sessions.map((s) => (
                <button
                  key={s.id}
                  className="session-item"
                  onClick={() => navigate(`/session/${s.id}`)}
                >
                  <div className="session-item-top">
                    <span className="session-query">{s.raw_query}</span>
                    <StatusBadge status={s.status} />
                  </div>
                  <div className="session-item-bottom">
                    <span>{s.result_count} leads</span>
                    <span>{new Date(s.created_at).toLocaleDateString()}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
