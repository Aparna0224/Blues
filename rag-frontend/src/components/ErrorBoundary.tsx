import { Component, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: unknown) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div style={{
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '200px',
          gap: '12px',
        }}>
          <div style={{
            padding: '16px 24px',
            borderRadius: '12px',
            background: 'rgba(248,113,113,0.1)',
            border: '1px solid rgba(248,113,113,0.3)',
            color: '#dc2626',
            textAlign: 'center',
          }}>
            <p style={{ margin: '0 0 8px', fontSize: '14px', fontWeight: 600 }}>
              Something went wrong
            </p>
            <p style={{ margin: 0, fontSize: '12px', color: '#7f1d1d' }}>
              {this.state.error?.message || 'An unexpected error occurred'}
            </p>
          </div>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            style={{
              padding: '8px 16px',
              borderRadius: '8px',
              border: '1px solid rgba(15,38,92,0.2)',
              background: 'rgba(15,38,92,0.06)',
              color: '#0f265c',
              cursor: 'pointer',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            Try again
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
