import { useState } from 'react';
import { Sparkles, ChevronDown } from 'lucide-react';

interface Props { summary: string | null; }

export default function SummaryPanel({ summary }: Props) {
  const [open, setOpen] = useState(false);
  if (!summary) return null;

  return (
    <div className="animate-fade-in" style={{ borderRadius: 13, border: '1px solid rgba(167,139,250,0.2)', background: 'rgba(167,139,250,0.05)', overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(!open)}
        style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%', padding: '14px 20px', background: 'transparent', border: 'none', cursor: 'pointer', textAlign: 'left', transition: 'background 0.15s' }}
      >
        <Sparkles size={15} style={{ color: 'var(--purple)' }} />
        <span style={{ flex: 1, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>AI Research Summary</span>
        <span style={{ fontSize: 9, color: 'var(--text-muted)', fontWeight: 500, textTransform: 'uppercase', letterSpacing: '0.08em', marginRight: 8 }}>Stage 5</span>
        <ChevronDown size={13} style={{ color: 'var(--text-muted)', transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }} />
      </button>

      {open && (
        <div className="prose animate-fade-in" style={{ padding: '0 20px 18px', fontSize: 13, lineHeight: 1.7 }}>
          {summary.split('\n').map((line, i) => line.trim() ? <p key={i}>{line}</p> : null)}
        </div>
      )}
    </div>
  );
}
