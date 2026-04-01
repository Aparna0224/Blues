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

  const dismiss = () => { setResult(null); setError(''); };

  return (
    <div>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          border: `1.5px dashed ${dragging ? 'var(--teal)' : 'rgba(255,255,255,0.12)'}`,
          borderRadius: 10, padding: '14px 20px', cursor: 'pointer', textAlign: 'center',
          background: dragging ? 'rgba(94,234,212,0.05)' : 'rgba(255,255,255,0.02)',
          transition: 'all 0.15s',
        }}
      >
        <input ref={inputRef} type="file" accept=".pdf" style={{ display: 'none' }} onChange={onSelect} />
        {uploading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8 }}>
            <Loader2 size={15} style={{ color: 'var(--teal)', animation: 'spin 1s linear infinite' }} />
            <span style={{ fontSize: 13, fontWeight: 500, color: 'var(--teal)' }}>Processing PDF…</span>
          </div>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Upload size={14} style={{ color: 'var(--text-muted)' }} />
            </div>
            <div style={{ textAlign: 'left' }}>
              <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: 'var(--text-secondary)' }}>
                Upload a paper <span style={{ color: 'var(--text-muted)', fontWeight: 400 }}>(optional)</span>
              </p>
              <p style={{ margin: 0, fontSize: 10, color: 'var(--text-muted)' }}>
                Drop a PDF or click — it will be chunked, embedded, and indexed
              </p>
            </div>
          </div>
        )}
      </div>

      {result && (
        <div className="animate-fade-in" style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: 9, border: '1px solid rgba(52,211,153,0.25)', background: 'rgba(52,211,153,0.08)' }}>
          <CheckCircle size={14} style={{ color: '#34d399', flexShrink: 0 }} />
          <div style={{ flex: 1, fontSize: 12 }}>
            <span style={{ fontWeight: 600, color: '#34d399' }}>{result.title}</span>
            <span style={{ color: '#6ee7b7', marginLeft: 6 }}>— {result.chunks_created} chunks, {result.vectors_added} vectors</span>
          </div>
          <button onClick={dismiss} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#34d399' }}><X size={13} /></button>
        </div>
      )}

      {error && (
        <div className="animate-fade-in" style={{ marginTop: 10, display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px', borderRadius: 9, border: '1px solid rgba(248,113,113,0.25)', background: 'rgba(248,113,113,0.08)' }}>
          <FileText size={13} style={{ color: '#f87171', flexShrink: 0 }} />
          <span style={{ flex: 1, fontSize: 12, color: '#fca5a5' }}>{error}</span>
          <button onClick={dismiss} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#f87171' }}><X size={13} /></button>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
