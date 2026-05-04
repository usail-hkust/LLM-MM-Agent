"use client";
import React from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

export class ErrorBoundary extends React.Component<{children: React.ReactNode}, {hasError: boolean, error?: Error}> {
  constructor(props: any) { super(props); this.state = { hasError: false }; }
  static getDerivedStateFromError(error: Error) { return { hasError: true, error }; }
  render() {
    if (this.state.hasError) {
      return (
        <div className="h-full flex flex-col items-center justify-center p-6 text-center bg-red-50/50 border border-red-100 rounded-xl">
          <AlertTriangle className="w-8 h-8 text-red-500 mb-2" />
          <h3 className="text-red-900 font-bold mb-1">Render Error</h3>
          <p className="text-red-600/80 text-xs font-mono mb-4">{this.state.error?.message}</p>
          <button onClick={() => this.setState({ hasError: false })} className="flex items-center gap-2 px-4 py-2 bg-white border border-red-200 text-red-700 rounded-lg text-sm shadow-sm hover:bg-red-50"><RefreshCw className="w-3 h-3"/> Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}
