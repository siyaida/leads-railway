const TONES = [
  {
    key: 'direct',
    label: 'Direct',
    description: 'Straight to the point, no fluff',
  },
  {
    key: 'friendly',
    label: 'Friendly',
    description: 'Warm, conversational, approachable',
  },
  {
    key: 'formal',
    label: 'Formal',
    description: 'Polished, C-suite appropriate',
  },
  {
    key: 'bold',
    label: 'Bold',
    description: 'Pattern-interrupt, provocative opener',
  },
]

export default function TonePicker({ value, onChange }) {
  return (
    <div className="picker-group">
      <label className="picker-label">Tone</label>
      <div className="tone-options">
        {TONES.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tone-option ${value === t.key ? 'active' : ''}`}
            onClick={() => onChange(t.key)}
          >
            <span className="tone-option-title">{t.label}</span>
            <span className="tone-option-desc">{t.description}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
