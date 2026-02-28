import { useState } from 'react';
import { Sparkles, ChevronDown, ChevronUp } from 'lucide-react';

interface Props {
  summary: string | null;
}

export default function SummaryPanel({ summary }: Props) {
  const [open, setOpen] = useState(false);

  if (!summary) return null;

  return (
    <div className="animate-fade-in">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full text-left px-4 py-3 bg-gradient-to-r
                   from-purple-50 to-blue-50 border border-purple-200 rounded-xl
                   hover:from-purple-100 hover:to-blue-100 transition-colors"
      >
        <Sparkles size={18} className="text-purple-600" />
        <span className="font-semibold text-slate-800 flex-1">
          AI Research Summary
        </span>
        <span className="text-xs text-slate-400 mr-2">Stage 5</span>
        {open ? (
          <ChevronUp size={16} className="text-slate-400" />
        ) : (
          <ChevronDown size={16} className="text-slate-400" />
        )}
      </button>

      {open && (
        <div className="mt-2 bg-white border border-slate-200 rounded-xl p-5 prose text-sm text-slate-700 leading-relaxed animate-fade-in">
          {summary.split('\n').map((line, i) =>
            line.trim() ? <p key={i}>{line}</p> : null
          )}
        </div>
      )}
    </div>
  );
}
