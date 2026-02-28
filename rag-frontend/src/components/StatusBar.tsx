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

  if (!status) {
    return (
      <span className="text-[11px] text-slate-400">Connecting to backend…</span>
    );
  }

  const items = [
    {
      icon: Database,
      label: 'DB',
      value: status.mongodb === 'connected' ? 'OK' : 'Off',
      ok: status.mongodb === 'connected',
    },
    { icon: HardDrive, label: 'Papers', value: String(status.papers_count) },
    { icon: Activity, label: 'Vectors', value: String(status.faiss_vectors) },
    { icon: Cpu, label: 'LLM', value: status.llm_model.split('-').slice(0, 2).join('-') },
  ];

  return (
    <div className="flex items-center gap-3 flex-wrap">
      {items.map((it) => {
        const Icon = it.icon;
        return (
          <span
            key={it.label}
            className="inline-flex items-center gap-1 text-[11px] text-slate-500"
          >
            <Icon size={11} className="text-slate-400" />
            <span className="text-slate-400">{it.label}</span>
            <span className={
              'ok' in it
                ? it.ok
                  ? 'text-emerald-600 font-semibold'
                  : 'text-red-500 font-semibold'
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
