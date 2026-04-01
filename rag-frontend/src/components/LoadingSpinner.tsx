export default function LoadingSpinner() {
  return (
    <div className="animate-fade-in" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 16, padding: '48px 24px' }}>
      {/* Rotating ring */}
      <div style={{ position: 'relative', width: 52, height: 52 }}>
        <div style={{
          width: '100%', height: '100%', borderRadius: '50%',
          border: '3px solid rgba(94,234,212,0.12)',
          borderTop: '3px solid var(--teal)',
          animation: 'spin 0.9s linear infinite',
        }} />
        <div style={{
          position: 'absolute', inset: 8, borderRadius: '50%',
          border: '2px solid rgba(129,140,248,0.12)',
          borderBottom: '2px solid var(--indigo)',
          animation: 'spin 1.4s linear infinite reverse',
        }} />
      </div>

      {/* Dots */}
      <div style={{ display: 'flex', gap: 6 }}>
        <span className="loading-dot" />
        <span className="loading-dot" />
        <span className="loading-dot" />
      </div>

      <div style={{ textAlign: 'center' }}>
        <p style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-primary)' }}>Running Pipeline</p>
        <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--text-muted)' }}>
          Planning → Retrieval → Verification → Synthesis
        </p>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
