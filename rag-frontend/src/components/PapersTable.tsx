import { BookOpen, ExternalLink } from 'lucide-react';
import type { PaperInfo } from '../types';

interface Props {
  papers: PaperInfo[];
}

export default function PapersTable({ papers }: Props) {
  if (!papers.length) return null;

  return (
    <div className="bg-white rounded-2xl border border-slate-200/80 shadow-sm overflow-hidden animate-fade-in">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center gap-2">
        <BookOpen size={16} className="text-blue-500" />
        <h3 className="text-sm font-semibold text-slate-800">
          Source Papers
        </h3>
        <span className="ml-1 text-xs text-slate-400 font-medium">({papers.length})</span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50/80 text-left text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              <th className="px-6 py-3 w-10">#</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Authors</th>
              <th className="px-4 py-3 w-16">Year</th>
              <th className="px-4 py-3 w-16">Link</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-50">
            {papers.map((p, i) => (
              <tr key={p.paper_id} className="hover:bg-blue-50/30 transition-colors">
                <td className="px-6 py-3.5">
                  <span className="w-6 h-6 rounded-full bg-slate-100 text-slate-500 text-xs font-bold inline-flex items-center justify-center">
                    {i + 1}
                  </span>
                </td>
                <td className="px-4 py-3.5 font-medium text-slate-800 max-w-md">
                  <span className="line-clamp-2 leading-snug">{p.title}</span>
                </td>
                <td className="px-4 py-3.5 text-slate-500 max-w-xs">
                  <span className="line-clamp-1">{p.authors}</span>
                </td>
                <td className="px-4 py-3.5 text-slate-400 tabular-nums">{p.year || '—'}</td>
                <td className="px-4 py-3.5">
                  {p.doi ? (
                    <a
                      href={p.doi.startsWith('http') ? p.doi : `https://doi.org/${p.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 text-xs font-medium"
                    >
                      DOI <ExternalLink size={10} />
                    </a>
                  ) : (
                    <span className="text-slate-300 text-xs">—</span>
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
