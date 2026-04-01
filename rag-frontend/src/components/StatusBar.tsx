import { useEffect, useState } from 'react';
import { Database, Cpu, HardDrive, Activity } from 'lucide-react';
import { getStatus } from '../services/api';
import type { StatusResponse } from '../types';

export default function StatusBar() {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    getStatus().then(setStatus).catch(() => setStatus(null));
  }, []);

  if (!status) {
    return (
      <p style={{ fontSize: 10, color: 'var(--text-muted)', margin: 0, padding: '0 4px' }}>Connecting…</p>
    );
  }

  const items = [
    { icon: Database, label: 'DB', value: status.mongodb === 'connected' ? 'OK' : 'Off', ok: status.mongodb === 'connected' },
    { icon: HardDrive, label: 'Papers', value: String(status.papers_count) },
    { icon: Activity, label: 'Vecs', value: String(status.faiss_vectors) },
    { icon: Cpu, label: 'LLM', value: status.llm_model.split('-').slice(0, 2).join('-') },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4, padding: '0 4px' }}>
      {items.map(it => {
        const Icon = it.icon;
        const hasOk = 'ok' in it;
        return (
          <span key={it.label} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            <Icon size={10} style={{ color: 'var(--text-muted)' }} />
            <span style={{ color: 'var(--text-muted)' }}>{it.label}</span>
            <span style={{ fontWeight: 600, color: hasOk ? (it.ok ? '#34d399' : '#f87171') : 'var(--text-secondary)' }}>
              {it.value}
            </span>
          </span>
        );
      })}
    </div>
  );
}
