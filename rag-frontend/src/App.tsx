import { useState, useEffect } from 'react';
import { XCircle } from 'lucide-react';
import LandingPage from './components/LandingPage';
import ResultsPage from './components/ResultsPage';
import LoadingSpinner from './components/LoadingSpinner';
import { runQuery, getStatus, extractErrorMessage } from './services/api';
import type { QueryRequest, QueryResponse } from './types';

type AppPage = 'landing' | 'loading' | 'results';

function App() {
  const [page, setPage] = useState<AppPage>('landing');
  const [result, setResult] = useState<QueryResponse | null>(null);
  const [error, setError] = useState('');

  /* Check backend health on mount */
  useEffect(() => {
    getStatus()
      .then(() => {/* connected */})
      .catch(() => {/* offline */});
  }, []);

  const handleSearch = async (req: QueryRequest) => {
    setPage('loading');
    setError('');
    setResult(null);
    try {
      const data = await runQuery(req);
      setResult(data);
      setPage('results');
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
      setPage('landing');
    }
  };

  const handleBackToLanding = () => {
    setPage('landing');
    setResult(null);
    setError('');
  };

  // Landing Page
  if (page === 'landing') {
    return (
      <>
        <LandingPage onSearch={handleSearch} loading={false} />
        {error && (
          <div className="fixed top-4 right-4 max-w-md bg-red-50 border-l-4 border-red-500 rounded-lg p-4 shadow-lg animate-fade-in">
            <div className="flex items-start gap-3">
              <XCircle size={18} className="text-red-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-red-900">Error</p>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
              <button
                onClick={() => setError('')}
                className="text-red-400 hover:text-red-600 flex-shrink-0"
              >
                <XCircle size={16} />
              </button>
            </div>
          </div>
        )}
      </>
    );
  }

  // Loading Page
  if (page === 'loading') {
    return (
      <div className="min-h-screen bg-white flex flex-col items-center justify-center">
        <LoadingSpinner />
      </div>
    );
  }

  // Results Page
  if (page === 'results' && result) {
    return <ResultsPage result={result} onBack={handleBackToLanding} />;
  }

  return null;
}

export default App;
