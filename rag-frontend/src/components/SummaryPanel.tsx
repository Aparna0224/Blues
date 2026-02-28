import { useState } from 'react';
import { Sparkles, ChevronDown } from 'lucide-react';

interface Props {
  summary: string | null;
}

export default function SummaryPanel({ summary }: Props) {
  const [open, setOpen] = useState(false);

  if (!summary) return null;

  return (
    <div className="rounded-2xl border border-purple-200/80 overflow-hidden shadow-sm animate-fade-in">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2.5 w-full text-left px-6 py-4
                   bg-gradient-to-r from-purple-50 via-indigo-50 to-blue-50
                   hover:from-purple-100 hover:via-indigo-100 hover:to-blue-100 transition-all"
      >
        <Sparkles size={16} className="text-purple-500" />
        <span className="text-sm font-semibold text-slate-800 flex-1">
          AI Research Summary
        </span>
        <span className="text-[10px] text-slate-400 font-medium uppercase tracking-wider mr-2">Stage 5</span>
        <ChevronDown
          size={14}
          className={`text-slate-400 transition-transform duration-200 ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open && (
        <div className="bg-white px-6 py-5 prose text-sm text-slate-700 leading-relaxed animate-fade-in">
          {summary.split('\n').map((line, i) =>
            line.trim() ? <p key={i}>{line}</p> : null
          )}
        </div>
      )}
    </div>
  );
}
