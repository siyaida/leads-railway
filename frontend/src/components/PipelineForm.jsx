import { useState } from 'react'
import { Search } from 'lucide-react'
import ChannelPicker from './ChannelPicker'
import TonePicker from './TonePicker'
import api from '../api/client'

export default function PipelineForm({ onStarted }) {
  const [query, setQuery] = useState('')
  const [senderContext, setSenderContext] = useState('')
  const [channel, setChannel] = useState('email')
  const [tone, setTone] = useState('direct')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/pipeline/run', {
        query: query.trim(),
        sender_context: senderContext.trim(),
        tone,
        channel,
      })
      onStarted(res.data)
    } catch (err) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'object' && detail.message) {
        setError(detail.message)
      } else {
        setError(detail || 'Failed to start pipeline')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="pipeline-form">
      <div className="form-group">
        <label>What leads are you looking for?</label>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. Find AI startup founders in Riyadh, Saudi Arabia"
          rows={3}
          required
        />
      </div>

      <ChannelPicker value={channel} onChange={setChannel} />
      <TonePicker value={tone} onChange={setTone} />

      <button
        type="button"
        className="btn-link"
        onClick={() => setShowAdvanced(!showAdvanced)}
      >
        {showAdvanced ? 'Hide' : 'Show'} advanced options
      </button>

      {showAdvanced && (
        <div className="form-group">
          <label>Sender Context (who you are, what you offer)</label>
          <textarea
            value={senderContext}
            onChange={(e) => setSenderContext(e.target.value)}
            placeholder="e.g. I'm the CEO of a SaaS company that helps businesses automate their marketing..."
            rows={3}
          />
        </div>
      )}

      {error && <div className="alert alert-error">{error}</div>}

      <button type="submit" className="btn btn-primary btn-full" disabled={loading}>
        <Search size={18} />
        {loading ? 'Starting Pipeline...' : 'Generate Leads'}
      </button>
    </form>
  )
}
