interface LoadingSpinnerProps {
  stages?: string[];
  currentStage?: number;
}

export default function LoadingSpinner({
  stages = ['Stage 1 → Planning', 'Stage 2 → Retrieval', 'Stage 3 → Evidence', 'Stage 4 → Verification', 'Stage 5 → Summary'],
  currentStage = 0,
}: LoadingSpinnerProps) {
  const safeStage = Math.max(0, Math.min(currentStage, stages.length - 1));
  const progress = ((safeStage + 1) / stages.length) * 100;

  return (
    <div className="animate-fade-in glass-card" style={{ display: 'flex', flexDirection: 'column', gap: 16, padding: '24px 20px', minHeight: 420 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <div>
          <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Running Pipeline</p>
          <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>{stages[safeStage]}</p>
        </div>

        <div style={{ position: 'relative', width: 44, height: 44 }}>
          <div
            style={{
              width: '100%',
              height: '100%',
              borderRadius: '50%',
              border: '3px solid rgba(94,234,212,0.12)',
              borderTop: '3px solid var(--teal)',
              animation: 'spin 0.9s linear infinite',
            }}
          />
          <div
            style={{
              position: 'absolute',
              inset: 8,
              borderRadius: '50%',
              border: '2px solid rgba(129,140,248,0.12)',
              borderBottom: '2px solid var(--indigo)',
              animation: 'spin 1.4s linear infinite reverse',
            }}
          />
        </div>
      </div>

      <div style={{ height: 8, borderRadius: 999, background: 'rgba(15, 38, 92, 0.1)', overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${progress}%`, background: 'linear-gradient(90deg, #0f265c, #425d95)', transition: 'width 0.35s ease' }} />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,minmax(0,1fr))', gap: 8 }}>
        {stages.map((stage, idx) => (
          <div
            key={stage}
            style={{
              fontSize: 10,
              color: idx <= safeStage ? '#0f265c' : 'var(--text-muted)',
              fontWeight: idx === safeStage ? 700 : 500,
            }}
          >
            {stage.replace('Stage ', 'S')}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 6 }}>
        <span className="loading-dot" />
        <span className="loading-dot" />
        <span className="loading-dot" />
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 6 }}>
        <div style={{ height: 18, width: '40%', borderRadius: 6, background: 'rgba(15,38,92,0.08)' }} />
        <div style={{ height: 120, borderRadius: 10, background: 'rgba(15,38,92,0.06)' }} />
        <div style={{ height: 120, borderRadius: 10, background: 'rgba(15,38,92,0.06)' }} />
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
