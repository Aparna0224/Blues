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
          relative border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all
          ${dragging
            ? 'border-blue-400 bg-blue-50/50 scale-[1.01]'
            : 'border-slate-200 hover:border-blue-300 hover:bg-blue-50/20'
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
          <div className="flex items-center justify-center gap-2 py-1">
            <Loader2 size={18} className="text-blue-500 animate-spin" />
            <span className="text-sm font-medium text-blue-600">Processing PDF…</span>
          </div>
        ) : (
          <div className="flex items-center justify-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
              <Upload size={16} className="text-slate-500" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-slate-700">
                Upload a paper <span className="text-slate-400 font-normal">(optional)</span>
              </p>
              <p className="text-[11px] text-slate-400">
                Drop a PDF or click — it will be chunked, embedded, and indexed
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Success */}
      {result && (
        <div className="mt-3 flex items-center gap-3 bg-emerald-50 border border-emerald-200 rounded-lg px-4 py-3 animate-fade-in">
          <CheckCircle size={16} className="text-emerald-600 shrink-0" />
          <div className="flex-1 text-sm">
            <span className="font-medium text-emerald-800">{result.title}</span>
            <span className="text-emerald-600 ml-1">
              — {result.chunks_created} chunks, {result.vectors_added} vectors indexed
            </span>
          </div>
          <button onClick={dismiss} className="text-emerald-400 hover:text-emerald-600 p-0.5">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg px-4 py-3 animate-fade-in">
          <FileText size={14} className="text-red-500 shrink-0" />
          <span className="text-sm text-red-700 flex-1">{error}</span>
          <button onClick={dismiss} className="text-red-400 hover:text-red-600 p-0.5">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}
