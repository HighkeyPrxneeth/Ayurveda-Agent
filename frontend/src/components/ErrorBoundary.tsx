'use client';

import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  errorInfo: ErrorInfo | null;
}

/**
 * Error Boundary Component
 * Catches JavaScript errors in child component tree and displays fallback UI.
 */
export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, errorInfo: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error, errorInfo: null };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo);
    this.setState({ error, errorInfo });
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null, errorInfo: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div 
          className="bg-white dark:bg-gray-900 rounded-2xl shadow-lg p-6 text-center"
          role="alert"
          aria-live="assertive"
        >
          <div className="text-4xl mb-4" aria-hidden="true">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-2">
            Something went wrong
          </h2>
          <p className="text-gray-600 dark:text-gray-400 mb-4 text-sm">
            We encountered an unexpected error. Please try again.
          </p>
          
          {this.state.error && (
            <details className="mb-4 text-left">
              <summary className="cursor-pointer text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200">
                Error Details
              </summary>
              <pre className="mt-2 p-3 bg-gray-100 dark:bg-gray-800 rounded-lg text-xs overflow-x-auto text-red-600 dark:text-red-400">
                {this.state.error.toString()}
                {this.state.errorInfo?.componentStack && (
                  <span className="text-gray-500 dark:text-gray-400">
                    {this.state.errorInfo.componentStack}
                  </span>
                )}
              </pre>
            </details>
          )}
          
          <div className="flex gap-3 justify-center">
            <button
              type="button"
              onClick={this.handleReset}
              className="px-4 py-2 bg-ayurveda-gold text-white rounded-lg hover:bg-amber-600 transition-all focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              Try Again
            </button>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-200 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700 transition-all focus:outline-none focus:ring-2 focus:ring-ayurveda-gold focus:ring-offset-2 dark:focus:ring-offset-gray-900"
            >
              Refresh Page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;

