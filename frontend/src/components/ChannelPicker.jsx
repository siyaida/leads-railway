import { Mail, Linkedin, MessageCircle } from 'lucide-react'

const CHANNELS = [
  {
    key: 'email',
    label: 'Cold Email',
    description: 'Professional email outreach with subject line',
    icon: Mail,
  },
  {
    key: 'linkedin',
    label: 'LinkedIn InMail',
    description: 'Short professional message for LinkedIn',
    icon: Linkedin,
  },
  {
    key: 'social_dm',
    label: 'Social DM',
    description: 'Quick Twitter/X or Instagram direct message',
    icon: MessageCircle,
  },
]

export default function ChannelPicker({ value, onChange }) {
  return (
    <div className="picker-group">
      <label className="picker-label">Outreach Channel</label>
      <div className="picker-options">
        {CHANNELS.map((ch) => (
          <button
            key={ch.key}
            type="button"
            className={`picker-option ${value === ch.key ? 'active' : ''}`}
            onClick={() => onChange(ch.key)}
          >
            <ch.icon size={20} />
            <div className="picker-option-text">
              <span className="picker-option-title">{ch.label}</span>
              <span className="picker-option-desc">{ch.description}</span>
            </div>
          </button>
        ))}
      </div>
    </div>
  )
}
