import { useState, useEffect } from 'react';

const STAGES = [
  { label: 'Planning sub-questions…', icon: '🧠' },
  { label: 'Retrieving relevant papers…', icon: '🔍' },
  { label: 'Extracting evidence…', icon: '📄' },
  { label: 'Generating grouped answer…', icon: '✍️' },
  { label: 'Verifying claims…', icon: '🛡️' },
];

export default function LoadingSpinner() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setStage((s) => (s + 1) % STAGES.length);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  const current = STAGES[stage];

  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      {/* Spinner ring */}
      <div className="relative w-20 h-20 mb-6">
        <div className="absolute inset-0 rounded-full border-4 border-blue-100" />
        <div className="absolute inset-0 rounded-full border-4 border-transparent border-t-blue-600 border-r-blue-400 animate-spin" />
        <span className="absolute inset-0 flex items-center justify-center text-3xl">
          {current.icon}
        </span>
      </div>
      <p className="text-base font-semibold text-slate-900 mb-2">{current.label}</p>
      <p className="text-sm text-slate-500">Analyzing papers with AI…</p>

      {/* Stage indicators */}
      <div className="flex gap-2 mt-8">
        {STAGES.map((_, i) => (
          <div
            key={i}
            className={`h-2 rounded-full transition-all duration-300 ${
              i === stage ? 'w-8 bg-blue-600' : i < stage ? 'w-2 bg-blue-400' : 'w-2 bg-slate-300'
            }`}
          />
        ))}
      </div>
    </div>
  );
}
