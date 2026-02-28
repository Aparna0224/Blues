import { BookOpen, ExternalLink } from 'lucide-react';
import type { PaperInfo } from '../types';

interface Props {
  papers: PaperInfo[];
}

export default function PapersTable({ papers }: Props) {
  if (!papers.length) return null;

  return (
    <div className="animate-fade-in">
      <div className="flex items-center gap-2 mb-3">
        <BookOpen size={18} className="text-blue-600" />
        <h3 className="font-semibold text-slate-800">
          Sources ({papers.length} papers)
        </h3>
      </div>

      <div className="overflow-x-auto rounded-xl border border-slate-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
              <th className="px-4 py-3">#</th>
              <th className="px-4 py-3">Title</th>
              <th className="px-4 py-3">Authors</th>
              <th className="px-4 py-3">Year</th>
              <th className="px-4 py-3">DOI</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {papers.map((p, i) => (
              <tr key={p.paper_id} className="hover:bg-slate-50 transition-colors">
                <td className="px-4 py-3 text-slate-400 font-mono text-xs">{i + 1}</td>
                <td className="px-4 py-3 font-medium text-slate-800 max-w-md">
                  <span className="line-clamp-2">{p.title}</span>
                </td>
                <td className="px-4 py-3 text-slate-600 max-w-xs">
                  <span className="line-clamp-1">{p.authors}</span>
                </td>
                <td className="px-4 py-3 text-slate-500">{p.year || '—'}</td>
                <td className="px-4 py-3">
                  {p.doi ? (
                    <a
                      href={p.doi.startsWith('http') ? p.doi : `https://doi.org/${p.doi}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-blue-600 hover:text-blue-800 hover:underline"
                    >
                      Link <ExternalLink size={12} />
                    </a>
                  ) : (
                    <span className="text-slate-300">—</span>
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
