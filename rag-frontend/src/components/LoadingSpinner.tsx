export default function LoadingSpinner({ message = 'Processing your query…' }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 animate-fade-in">
      <div className="flex gap-2 mb-4">
        <span className="loading-dot" />
        <span className="loading-dot" />
        <span className="loading-dot" />
      </div>
      <p className="text-sm text-slate-500 font-medium">{message}</p>
      <p className="text-xs text-slate-400 mt-1">This may take a minute for dynamic retrieval</p>
    </div>
  );
}
