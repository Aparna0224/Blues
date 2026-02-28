import { useEffect, useState } from 'react';
import { Database, Cpu, HardDrive, Activity } from 'lucide-react';
import { getStatus } from '../services/api';
import type { StatusResponse } from '../types';

export default function StatusBar() {
  const [status, setStatus] = useState<StatusResponse | null>(null);

  useEffect(() => {
    getStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  if (!status) return null;

  const items = [
    {
      icon: Database,
      label: 'MongoDB',
      value: status.mongodb === 'connected' ? 'Connected' : 'Offline',
      ok: status.mongodb === 'connected',
    },
    { icon: HardDrive, label: 'Papers', value: String(status.papers_count) },
    { icon: Activity, label: 'FAISS vectors', value: String(status.faiss_vectors) },
    { icon: Cpu, label: 'LLM', value: `${status.llm_provider} / ${status.llm_model}` },
  ];

  return (
    <div className="flex items-center gap-4 flex-wrap text-xs text-slate-500">
      {items.map((it) => {
        const Icon = it.icon;
        return (
          <span key={it.label} className="flex items-center gap-1">
            <Icon size={12} />
            <span className="text-slate-400">{it.label}:</span>
            <span className={
              'ok' in it
                ? it.ok
                  ? 'text-green-600 font-medium'
                  : 'text-red-600 font-medium'
                : 'font-medium text-slate-600'
            }>
              {it.value}
            </span>
          </span>
        );
      })}
    </div>
  );
}
