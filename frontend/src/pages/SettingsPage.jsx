import { useState, useEffect } from 'react'
import { Key, CheckCircle, XCircle, Loader, Cpu } from 'lucide-react'
import api from '../api/client'

export default function SettingsPage() {
  const [settings, setSettings] = useState(null)
  const [models, setModels] = useState([])
  const [keys, setKeys] = useState({ serper: '', apollo: '', openai: '' })
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState({})
  const [testResults, setTestResults] = useState({})
  const [message, setMessage] = useState('')

  useEffect(() => {
    Promise.all([
      api.get('/settings/'),
      api.get('/settings/models'),
    ]).then(([settingsRes, modelsRes]) => {
      setSettings(settingsRes.data)
      setModels(modelsRes.data)
    }).catch(() => {})
  }, [])

  const handleSaveKeys = async () => {
    setSaving(true)
    setMessage('')
    try {
      const payload = {}
      if (keys.serper) payload.serper = keys.serper
      if (keys.apollo) payload.apollo = keys.apollo
      if (keys.openai) payload.openai = keys.openai
      const res = await api.put('/settings/keys', payload)
      setSettings(res.data)
      setKeys({ serper: '', apollo: '', openai: '' })
      setMessage('API keys saved successfully.')
    } catch {
      setMessage('Failed to save API keys.')
    } finally {
      setSaving(false)
    }
  }

  const handleTest = async (service) => {
    setTesting((prev) => ({ ...prev, [service]: true }))
    setTestResults((prev) => ({ ...prev, [service]: null }))
    try {
      const res = await api.post(`/settings/test/${service}`)
      setTestResults((prev) => ({ ...prev, [service]: res.data }))
    } catch {
      setTestResults((prev) => ({
        ...prev,
        [service]: { status: 'invalid', message: 'Test request failed' },
      }))
    } finally {
      setTesting((prev) => ({ ...prev, [service]: false }))
    }
  }

  const handleModelChange = async (modelId) => {
    try {
      await api.put('/settings/model', { model: modelId })
      setSettings((prev) => prev ? { ...prev, current_model: modelId } : prev)
    } catch {
      alert('Failed to update model')
    }
  }

  if (!settings) return <div className="page-loader">Loading settings...</div>

  const services = [
    { key: 'serper', label: 'Serper.dev', description: 'Google search API for finding companies', required: true },
    { key: 'openai', label: 'OpenAI', description: 'AI for query parsing and email generation', required: true },
    { key: 'apollo', label: 'Apollo.io', description: 'Contact enrichment with email and phone data', required: false },
  ]

  return (
    <div className="settings-page">
      <h2>Settings</h2>

      <div className="card">
        <h3><Key size={20} /> API Keys</h3>
        <p className="text-muted">Configure your API keys to enable the lead generation pipeline.</p>

        {message && <div className="alert alert-success">{message}</div>}

        {services.map((svc) => (
          <div key={svc.key} className="settings-key-row">
            <div className="settings-key-info">
              <div className="settings-key-label">
                {svc.label}
                {svc.required ? <span className="required-badge">Required</span> : <span className="optional-badge">Optional</span>}
              </div>
              <div className="settings-key-desc">{svc.description}</div>
              <div className="settings-key-status">
                {settings[svc.key]?.configured ? (
                  <span className="text-green"><CheckCircle size={14} /> Configured: {settings[svc.key].masked_key}</span>
                ) : (
                  <span className="text-muted"><XCircle size={14} /> Not configured</span>
                )}
              </div>
            </div>
            <div className="settings-key-actions">
              <input
                type="password"
                value={keys[svc.key]}
                onChange={(e) => setKeys((prev) => ({ ...prev, [svc.key]: e.target.value }))}
                placeholder={settings[svc.key]?.configured ? 'Enter new key to update' : 'Enter API key'}
                className="settings-key-input"
              />
              <button
                className="btn btn-sm btn-secondary"
                onClick={() => handleTest(svc.key)}
                disabled={testing[svc.key] || !settings[svc.key]?.configured}
              >
                {testing[svc.key] ? <Loader size={14} className="spin" /> : 'Test'}
              </button>
            </div>
            {testResults[svc.key] && (
              <div className={`settings-test-result ${testResults[svc.key].status === 'valid' ? 'success' : 'error'}`}>
                {testResults[svc.key].status === 'valid' ? <CheckCircle size={14} /> : <XCircle size={14} />}
                {testResults[svc.key].message}
              </div>
            )}
          </div>
        ))}

        <button className="btn btn-primary" onClick={handleSaveKeys} disabled={saving} style={{ marginTop: 16 }}>
          {saving ? 'Saving...' : 'Save Keys'}
        </button>
      </div>

      <div className="card" style={{ marginTop: 24 }}>
        <h3><Cpu size={20} /> AI Model</h3>
        <p className="text-muted">Choose the OpenAI model for query parsing and email generation.</p>

        <div className="models-grid">
          {models.map((m) => (
            <button
              key={m.id}
              className={`model-card ${settings.current_model === m.id ? 'active' : ''}`}
              onClick={() => handleModelChange(m.id)}
            >
              <div className="model-card-header">
                <span className="model-name">{m.name}</span>
                <span className="model-cost">{m.cost}</span>
              </div>
              <p className="model-desc">{m.description}</p>
              {m.recommended_for === 'all' && (
                <span className="model-badge">Recommended</span>
              )}
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
