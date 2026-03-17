import { useState, useRef } from 'react';
import { Upload, X, FileText, CheckCircle, Loader2 } from 'lucide-react';
import { uploadPaper, extractErrorMessage } from '../services/api';
import type { UploadResponse } from '../types';

export default function FileUpload() {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      setError('Only PDF files are supported.');
      return;
    }
    setError('');
    setResult(null);
    setUploading(true);
    try {
      const res = await uploadPaper(file);
      setResult(res);
    } catch (err: unknown) {
      setError(extractErrorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) handleFile(file);
  };

  const onSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const dismiss = () => {
    setResult(null);
    setError('');
  };

  return (
    <div>
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-all
          ${dragging
            ? 'border-blue-400 bg-blue-50'
            : 'border-slate-300 hover:border-blue-400 hover:bg-slate-50'
          }
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={onSelect}
        />
        {uploading ? (
          <div className="flex flex-col items-center justify-center gap-3 py-2">
            <Loader2 size={28} className="text-blue-500 animate-spin" />
            <span className="text-sm font-medium text-slate-700">Processing PDF…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center">
            <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mb-3">
              <Upload size={24} className="text-blue-600" />
            </div>
            <p className="text-base font-semibold text-slate-800 mb-1">
              Drop your PDF here
            </p>
            <p className="text-sm text-slate-500">
              or click to select a file
            </p>
          </div>
        )}
      </div>

      {/* Success */}
      {result && (
        <div className="mt-4 flex items-start gap-3 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 animate-fade-in">
          <CheckCircle size={18} className="text-emerald-600 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="font-medium text-emerald-900">{result.title}</p>
            <p className="text-sm text-emerald-700 mt-1">
              ✓ {result.chunks_created} chunks • {result.vectors_added} vectors indexed
            </p>
          </div>
          <button onClick={dismiss} className="text-emerald-400 hover:text-emerald-600 p-0.5">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-4 flex items-start gap-3 bg-red-50 border border-red-200 rounded-lg px-4 py-3 animate-fade-in">
          <FileText size={16} className="text-red-500 shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm text-red-700">{error}</p>
          </div>
          <button onClick={dismiss} className="text-red-400 hover:text-red-600 p-0.5">
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
