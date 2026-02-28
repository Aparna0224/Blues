import { useState, useRef } from 'react';
import { Upload, X, FileText, CheckCircle } from 'lucide-react';
import { uploadPaper } from '../services/api';
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
      if (err && typeof err === 'object' && 'response' in err) {
        const axErr = err as { response?: { data?: { detail?: string } } };
        setError(axErr.response?.data?.detail ?? 'Upload failed');
      } else {
        setError('Upload failed');
      }
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
    <div className="mb-4">
      {/* Drop zone */}
      <div
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`
          border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all
          ${dragging
            ? 'border-blue-400 bg-blue-50'
            : 'border-slate-300 hover:border-blue-300 hover:bg-slate-50'
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
        <Upload className="mx-auto mb-2 text-slate-400" size={28} />
        <p className="text-sm font-medium text-slate-600">
          {uploading ? 'Uploading…' : 'Drop a PDF here or click to upload'}
        </p>
        <p className="text-xs text-slate-400 mt-1">
          The paper will be ingested, chunked, and indexed automatically
        </p>
      </div>

      {/* Success */}
      {result && (
        <div className="mt-3 flex items-start gap-3 bg-green-50 border border-green-200 rounded-lg p-3 animate-fade-in">
          <CheckCircle size={18} className="text-green-600 mt-0.5 shrink-0" />
          <div className="flex-1 text-sm">
            <p className="font-medium text-green-800">Paper uploaded successfully</p>
            <p className="text-green-700 mt-0.5">
              <FileText size={14} className="inline mr-1" />
              {result.title} — {result.chunks_created} chunks, {result.vectors_added} vectors
            </p>
          </div>
          <button onClick={dismiss} className="text-green-400 hover:text-green-600">
            <X size={16} />
          </button>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-center gap-2 bg-red-50 border border-red-200 rounded-lg p-3 animate-fade-in">
          <span className="text-sm text-red-700 flex-1">{error}</span>
          <button onClick={dismiss} className="text-red-400 hover:text-red-600">
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
