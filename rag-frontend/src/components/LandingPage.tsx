import { useState } from 'react';
import { ArrowRight, BookOpen, Zap, Shield } from 'lucide-react';
import type { QueryRequest } from '../types';

interface Props {
  onSearch: (req: QueryRequest) => void;
  loading: boolean;
}

export default function LandingPage({ onSearch, loading }: Props) {
  const [topic, setTopic] = useState('');
  const [numDocs, setNumDocs] = useState(10);
  const [mode, setMode] = useState<'dynamic' | 'cached'>('cached');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!topic.trim() || loading) return;
    onSearch({
      query: topic.trim(),
      num_documents: numDocs,
      mode,
      include_summary: true,
    });
  };

  return (
    <div className="min-h-screen bg-gradient-to-b from-white via-white to-slate-50">
      {/* Header */}
      <header className="border-b border-slate-200 bg-white sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-lg bg-gradient-to-br from-green-600 to-green-700 flex items-center justify-center shadow-lg">
              <BookOpen size={24} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-900">Blues</h1>
              <p className="text-xs text-slate-500 font-medium">Research Intelligence Platform</p>
            </div>
          </div>
          <a href="#" className="text-sm text-slate-600 hover:text-slate-900 font-medium">
            Documentation
          </a>
        </div>
      </header>

      {/* Hero Section */}
      <section className="max-w-7xl mx-auto px-6 lg:px-8 py-24">
        <div className="grid md:grid-cols-2 gap-16 items-center mb-24">
          {/* Left Column - Description */}
          <div>
            <h2 className="text-5xl font-bold text-slate-900 mb-6 leading-tight">
              Research Made Intelligent
            </h2>
            <p className="text-xl text-slate-600 mb-8 leading-relaxed">
              Blues leverages advanced AI to analyze research papers, extract key findings, and synthesize comprehensive answers to your research questions.
            </p>
            
            {/* Features */}
            <div className="space-y-4">
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center flex-shrink-0 mt-1">
                  <Zap size={20} className="text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">Instant Analysis</h3>
                  <p className="text-sm text-slate-600">AI-powered extraction and synthesis of research findings</p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center flex-shrink-0 mt-1">
                  <Shield size={20} className="text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">Verified Results</h3>
                  <p className="text-sm text-slate-600">Fact-checking and confidence scoring on all claims</p>
                </div>
              </div>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg bg-green-50 flex items-center justify-center flex-shrink-0 mt-1">
                  <BookOpen size={20} className="text-green-600" />
                </div>
                <div>
                  <h3 className="font-semibold text-slate-900">Source Tracking</h3>
                  <p className="text-sm text-slate-600">Every claim is traced back to its source documents</p>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column - Search Box */}
          <div>
            <form onSubmit={handleSubmit} className="space-y-6">
              {/* Topic Input */}
              <div>
                <label className="block text-sm font-semibold text-slate-900 mb-3">
                  What would you like to research?
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    placeholder="e.g., latest advances in quantum computing, climate change mitigation..."
                    disabled={loading}
                    className="w-full px-6 py-4 rounded-lg border-2 border-slate-200 
                               bg-white text-slate-900 placeholder:text-slate-400
                               focus:outline-none focus:ring-0 focus:border-green-500 focus:bg-green-50/30
                               disabled:opacity-60 disabled:cursor-not-allowed
                               transition-all text-lg"
                  />
                </div>
              </div>

              {/* Options */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-2">
                    Documents
                  </label>
                  <select
                    value={numDocs}
                    onChange={(e) => setNumDocs(Number(e.target.value))}
                    className="w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900
                               focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500"
                  >
                    <option value={5}>5 documents</option>
                    <option value={10}>10 documents</option>
                    <option value={20}>20 documents</option>
                    <option value={30}>30 documents</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 uppercase mb-2">
                    Mode
                  </label>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value as 'dynamic' | 'cached')}
                    className="w-full px-4 py-2.5 rounded-lg border border-slate-200 bg-white text-slate-900
                               focus:outline-none focus:ring-2 focus:ring-green-500/20 focus:border-green-500"
                  >
                    <option value="cached">Cached (Fast)</option>
                    <option value="dynamic">Dynamic (Comprehensive)</option>
                  </select>
                </div>
              </div>

              {/* Search Button */}
              <button
                type="submit"
                disabled={!topic.trim() || loading}
                className="w-full px-6 py-4 rounded-lg bg-gradient-to-r from-green-600 to-green-700 
                           text-white font-semibold text-lg
                           hover:from-green-700 hover:to-green-800 active:from-green-800 active:to-green-900
                           disabled:opacity-40 disabled:cursor-not-allowed
                           transition-all shadow-lg hover:shadow-xl
                           flex items-center justify-center gap-2"
              >
                {loading ? (
                  <>
                    <span className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Analyzing...
                  </>
                ) : (
                  <>
                    Start Research
                    <ArrowRight size={20} />
                  </>
                )}
              </button>
            </form>

            {/* Info Box */}
            <div className="mt-8 p-4 bg-green-50 border border-green-200 rounded-lg">
              <p className="text-sm text-green-900">
                <strong>Tip:</strong> Ask specific questions like "What are the latest methodologies in medical imaging?" for best results.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white mt-16">
        <div className="max-w-7xl mx-auto px-6 lg:px-8 py-12">
          <div className="text-center text-sm text-slate-600">
            <p>Powered by advanced AI | Built with ❤️ by <a href="https://github.com/Aparna0224" className="text-green-600 hover:text-green-700 font-medium">Aparna0224</a></p>
          </div>
        </div>
      </footer>
    </div>
  );
}
