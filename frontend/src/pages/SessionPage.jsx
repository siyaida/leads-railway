import { useState, useEffect, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { ArrowLeft, Download, RefreshCw, Mail, User, Building2, Globe, Linkedin, CheckSquare, Square } from 'lucide-react'
import api from '../api/client'
import ProgressPanel from '../components/ProgressPanel'
import EmailPreview from '../components/EmailPreview'

export default function SessionPage() {
  const { sessionId } = useParams()
  const navigate = useNavigate()
  const [session, setSession] = useState(null)
  const [leads, setLeads] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedLead, setSelectedLead] = useState(null)
  const [regenerating, setRegenerating] = useState(false)
  const [pipelineActive, setPipelineActive] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, leadsRes] = await Promise.all([
        api.get(`/pipeline/${sessionId}/status`),
        api.get(`/leads/${sessionId}`).catch(() => ({ data: [] })),
      ])
      setSession(statusRes.data)
      setLeads(leadsRes.data)

      const isActive = ['pending', 'searching', 'enriching', 'generating'].includes(statusRes.data.status)
      setPipelineActive(isActive)
    } catch {
      // ignore
    } finally {
      setLoading(false)
    }
  }, [sessionId])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Auto-refresh leads while pipeline is active
  useEffect(() => {
    if (!pipelineActive) return
    const interval = setInterval(() => {
      api.get(`/leads/${sessionId}`)
        .then((res) => setLeads(res.data))
        .catch(() => {})
    }, 5000)
    return () => clearInterval(interval)
  }, [pipelineActive, sessionId])

  const handlePipelineComplete = useCallback((finalStatus) => {
    setPipelineActive(false)
    // Refresh data to get final leads
    fetchData()
  }, [fetchData])

  const handleStatusChange = useCallback((newStatus) => {
    const isActive = ['pending', 'searching', 'enriching', 'generating'].includes(newStatus)
    setPipelineActive(isActive)
  }, [])

  const toggleLead = async (leadId, current) => {
    try {
      await api.patch(`/leads/${leadId}`, { is_selected: !current })
      setLeads((prev) =>
        prev.map((l) => (l.id === leadId ? { ...l, is_selected: !current } : l))
      )
    } catch {
      // ignore
    }
  }

  const handleExport = async (type = 'full') => {
    try {
      const res = await api.get(`/export/${sessionId}`, {
        params: { export_type: type },
        responseType: 'blob',
      })
      const url = URL.createObjectURL(res.data)
      const a = document.createElement('a')
      a.href = url
      a.download = `siyada_${type}_${sessionId.slice(0, 8)}.csv`
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      alert('Export failed. Make sure you have selected leads.')
    }
  }

  const handleRegenerate = async () => {
    setRegenerating(true)
    try {
      await api.post(`/generate/${sessionId}`, {
        sender_context: '',
        tone: 'direct',
        channel: 'email',
      })
      await fetchData()
    } catch {
      alert('Regeneration failed')
    } finally {
      setRegenerating(false)
    }
  }

  if (loading) return <div className="page-loader">Loading session...</div>

  return (
    <div className="session-page">
      <div className="session-header">
        <button className="btn btn-ghost" onClick={() => navigate('/')}>
          <ArrowLeft size={18} /> Back
        </button>
        <div className="session-header-info">
          <h2>Session Results</h2>
          <p className="text-muted">{session?.message}</p>
        </div>
        <div className="session-header-actions">
          {!pipelineActive && (
            <>
              <button className="btn btn-secondary" onClick={handleRegenerate} disabled={regenerating}>
                <RefreshCw size={16} className={regenerating ? 'spin' : ''} />
                {regenerating ? 'Regenerating...' : 'Regenerate Emails'}
              </button>
              <div className="dropdown">
                <button className="btn btn-primary" onClick={() => handleExport('full')}>
                  <Download size={16} /> Export CSV
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {pipelineActive && (
        <div className="card" style={{ marginBottom: 24 }}>
          <ProgressPanel
            sessionId={sessionId}
            onComplete={handlePipelineComplete}
            onStatusChange={handleStatusChange}
          />
        </div>
      )}

      <div className="session-content">
        <div className="leads-table-container">
          <div className="leads-table-header">
            <h3>
              {leads.length} Leads
              {pipelineActive && <span className="spinner" style={{ marginLeft: 8 }} />}
            </h3>
            <span className="text-muted">
              {leads.filter((l) => l.is_selected).length} selected
            </span>
          </div>

          {leads.length === 0 ? (
            <p className="text-muted" style={{ padding: 24 }}>
              No leads found yet. {pipelineActive ? 'Pipeline is still running...' : 'Try a different query.'}
            </p>
          ) : (
            <div className="leads-grid">
              {leads.map((lead) => (
                <div
                  key={lead.id}
                  className={`lead-card ${selectedLead?.id === lead.id ? 'active' : ''} ${!lead.is_selected ? 'deselected' : ''}`}
                  onClick={() => setSelectedLead(lead)}
                >
                  <div className="lead-card-check" onClick={(e) => { e.stopPropagation(); toggleLead(lead.id, lead.is_selected) }}>
                    {lead.is_selected ? <CheckSquare size={18} className="text-primary" /> : <Square size={18} />}
                  </div>
                  <div className="lead-card-body">
                    <div className="lead-name">
                      <User size={16} />
                      {[lead.first_name, lead.last_name].filter(Boolean).join(' ') || lead.company_name || 'Unknown'}
                    </div>
                    {lead.job_title && (
                      <div className="lead-detail">{lead.job_title}</div>
                    )}
                    {lead.company_name && (
                      <div className="lead-detail">
                        <Building2 size={14} /> {lead.company_name}
                      </div>
                    )}
                    <div className="lead-badges">
                      {lead.email && (
                        <span className="lead-badge email">
                          <Mail size={12} /> Email
                        </span>
                      )}
                      {lead.linkedin_url && (
                        <span className="lead-badge linkedin">
                          <Linkedin size={12} /> LinkedIn
                        </span>
                      )}
                      {lead.company_domain && (
                        <span className="lead-badge web">
                          <Globe size={12} /> {lead.company_domain}
                        </span>
                      )}
                    </div>
                  </div>
                  {lead.personalized_email && (
                    <div className="lead-card-email-indicator">
                      <Mail size={14} className="text-green" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="lead-detail-panel">
          {selectedLead ? (
            <EmailPreview lead={selectedLead} sessionId={sessionId} onUpdate={fetchData} />
          ) : (
            <div className="empty-detail">
              <Mail size={32} />
              <p>Select a lead to view details and email preview</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
