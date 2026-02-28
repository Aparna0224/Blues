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
    <div className="flex flex-col items-center justify-center py-16 animate-fade-in">
      {/* Spinner ring */}
      <div className="relative w-16 h-16 mb-5">
        <div className="absolute inset-0 rounded-full border-[3px] border-slate-100" />
        <div className="absolute inset-0 rounded-full border-[3px] border-transparent border-t-blue-600 animate-spin" />
        <span className="absolute inset-0 flex items-center justify-center text-xl">
          {current.icon}
        </span>
      </div>
      <p className="text-sm font-semibold text-slate-700 mb-1">{current.label}</p>
      <p className="text-xs text-slate-400">Pipeline is running — this may take 1–2 minutes</p>

      {/* Stage indicators */}
      <div className="flex gap-1.5 mt-5">
        {STAGES.map((_, i) => (
          <div
            key={i}
            className={`w-1.5 h-1.5 rounded-full transition-all duration-300 ${
              i === stage ? 'bg-blue-600 scale-125' : i < stage ? 'bg-blue-300' : 'bg-slate-200'
            }`}
          />
        ))}
      </div>
    </div>
  );
}
