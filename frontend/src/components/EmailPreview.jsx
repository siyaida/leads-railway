import { useState } from 'react'
import { Mail, User, Building2, MapPin, Linkedin, Globe, Copy, Check, Edit3, Save } from 'lucide-react'
import api from '../api/client'

export default function EmailPreview({ lead, sessionId, onUpdate }) {
  const [editing, setEditing] = useState(false)
  const [editBody, setEditBody] = useState(lead.personalized_email || '')
  const [editSubject, setEditSubject] = useState(lead.email_subject || '')
  const [copied, setCopied] = useState(false)
  const [saving, setSaving] = useState(false)

  const name = [lead.first_name, lead.last_name].filter(Boolean).join(' ')
  const location = [lead.city, lead.state, lead.country].filter(Boolean).join(', ')

  const handleCopy = async () => {
    const text = lead.email_subject
      ? `Subject: ${lead.email_subject}\n\n${lead.personalized_email}`
      : lead.personalized_email
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await api.patch(`/leads/${lead.id}/email`, {
        personalized_email: editBody,
        email_subject: editSubject,
      })
      setEditing(false)
      if (onUpdate) onUpdate()
    } catch {
      alert('Save failed')
    } finally {
      setSaving(false)
    }
  }

  const handleEdit = () => {
    setEditBody(lead.personalized_email || '')
    setEditSubject(lead.email_subject || '')
    setEditing(true)
  }

  return (
    <div className="email-preview">
      <div className="lead-info-section">
        <h3>
          <User size={18} />
          {name || 'Unknown Contact'}
        </h3>
        {lead.job_title && <p className="lead-info-title">{lead.job_title}</p>}

        <div className="lead-info-grid">
          {lead.company_name && (
            <div className="lead-info-item">
              <Building2 size={14} />
              <span>{lead.company_name}</span>
            </div>
          )}
          {lead.company_domain && (
            <div className="lead-info-item">
              <Globe size={14} />
              <a href={`https://${lead.company_domain}`} target="_blank" rel="noopener noreferrer">
                {lead.company_domain}
              </a>
            </div>
          )}
          {location && (
            <div className="lead-info-item">
              <MapPin size={14} />
              <span>{location}</span>
            </div>
          )}
          {lead.email && (
            <div className="lead-info-item">
              <Mail size={14} />
              <a href={`mailto:${lead.email}`}>{lead.email}</a>
            </div>
          )}
          {lead.linkedin_url && (
            <div className="lead-info-item">
              <Linkedin size={14} />
              <a href={lead.linkedin_url} target="_blank" rel="noopener noreferrer">
                LinkedIn Profile
              </a>
            </div>
          )}
        </div>

        {lead.company_industry && (
          <div className="lead-info-tag">Industry: {lead.company_industry}</div>
        )}
        {lead.company_size && (
          <div className="lead-info-tag">Size: {lead.company_size} employees</div>
        )}
      </div>

      {(lead.personalized_email || editing) && (
        <div className="email-content-section">
          <div className="email-content-header">
            <h4>Generated Email</h4>
            <div className="email-content-actions">
              {!editing && (
                <>
                  <button className="btn-icon" onClick={handleCopy} title="Copy">
                    {copied ? <Check size={16} className="text-green" /> : <Copy size={16} />}
                  </button>
                  <button className="btn-icon" onClick={handleEdit} title="Edit">
                    <Edit3 size={16} />
                  </button>
                </>
              )}
              {editing && (
                <button className="btn btn-sm btn-primary" onClick={handleSave} disabled={saving}>
                  <Save size={14} />
                  {saving ? 'Saving...' : 'Save'}
                </button>
              )}
            </div>
          </div>

          {editing ? (
            <>
              <input
                className="email-subject-input"
                value={editSubject}
                onChange={(e) => setEditSubject(e.target.value)}
                placeholder="Subject line..."
              />
              <textarea
                className="email-body-input"
                value={editBody}
                onChange={(e) => setEditBody(e.target.value)}
                rows={8}
              />
            </>
          ) : (
            <>
              {lead.email_subject && (
                <div className="email-subject">
                  <strong>Subject:</strong> {lead.email_subject}
                </div>
              )}
              <div className="email-body">{lead.personalized_email}</div>
            </>
          )}

          {lead.suggested_approach && !editing && (
            <div className="email-approach">
              <strong>Strategy:</strong> {lead.suggested_approach}
            </div>
          )}
        </div>
      )}

      {!lead.personalized_email && !editing && (
        <div className="email-empty">
          <Mail size={24} />
          <p>No email generated yet for this lead.</p>
        </div>
      )}
    </div>
  )
}
