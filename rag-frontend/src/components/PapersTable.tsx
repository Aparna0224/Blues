import { BookOpen, ExternalLink } from 'lucide-react';
import type { PaperInfo } from '../types';

interface Props { papers: PaperInfo[]; }

const th: React.CSSProperties = {
  padding: '10px 14px', fontSize: 10, fontWeight: 600, color: 'var(--text-muted)',
  textTransform: 'uppercase', letterSpacing: '0.07em', textAlign: 'left', background: 'rgba(255,255,255,0.03)',
};

export default function PapersTable({ papers }: Props) {
  if (!papers.length) return null;

  return (
    <div style={{ borderRadius: 13, border: '1px solid var(--border)', background: 'var(--bg-card)', overflow: 'hidden' }} className="animate-fade-in">
      <div style={{ padding: '14px 20px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <BookOpen size={15} style={{ color: 'var(--cyan)' }} />
        <h3 style={{ margin: 0, fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>Source Papers</h3>
        <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 2 }}>({papers.length})</span>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
          <thead>
            <tr>
              <th style={{ ...th, width: 36 }}>#</th>
              <th style={th}>Title</th>
              <th style={th}>Authors</th>
              <th style={{ ...th, width: 60 }}>Year</th>
              <th style={{ ...th, width: 60 }}>Link</th>
            </tr>
          </thead>
          <tbody>
            {papers.map((p, i) => (
              <tr
                key={p.paper_id || `paper-${i}`}
                style={{ borderTop: '1px solid rgba(255,255,255,0.05)', transition: 'background 0.1s' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.03)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
              >
                <td style={{ padding: '11px 14px' }}>
                  <span style={{ width: 22, height: 22, borderRadius: '50%', background: 'rgba(255,255,255,0.07)', color: 'var(--text-muted)', fontSize: 10, fontWeight: 700, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
                    {i + 1}
                  </span>
                </td>
                <td style={{ padding: '11px 14px', fontWeight: 500, color: 'var(--text-primary)', maxWidth: 340 }}>
                  <span style={{ display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical', overflow: 'hidden', lineHeight: 1.5 }}>{p.title}</span>
                </td>
                <td style={{ padding: '11px 14px', color: 'var(--text-muted)', maxWidth: 200 }}>
                  <span style={{ display: '-webkit-box', WebkitLineClamp: 1, WebkitBoxOrient: 'vertical', overflow: 'hidden' }}>{p.authors}</span>
                </td>
                <td style={{ padding: '11px 14px', color: 'var(--text-muted)', fontVariantNumeric: 'tabular-nums' }}>{p.year || '—'}</td>
                <td style={{ padding: '11px 14px' }}>
                  {p.doi ? (
                    <a
                      href={p.doi.startsWith('http') ? p.doi : `https://doi.org/${p.doi}`}
                      target="_blank" rel="noopener noreferrer"
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, color: 'var(--teal)', fontSize: 11, fontWeight: 500, textDecoration: 'none' }}
                    >
                      DOI <ExternalLink size={9} />
                    </a>
                  ) : (
                    <span style={{ color: 'rgba(255,255,255,0.15)', fontSize: 11 }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
