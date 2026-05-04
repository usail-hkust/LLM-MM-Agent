"use client";

import React from "react";
import { AlertOctagon, RefreshCw, Home } from "lucide-react";

interface Props {
    children: React.ReactNode;
}

interface State {
    hasError: boolean;
    error?: Error;
}

export class TopErrorBoundary extends React.Component<Props, State> {
    constructor(props: Props) {
        super(props);
        this.state = { hasError: false };
    }

    static getDerivedStateFromError(error: Error) {
        return { hasError: true, error };
    }

    componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
        console.error("[TopErrorBoundary] Critical Application Crash:", error, errorInfo);
    }

    handleReset = () => {
        this.setState({ hasError: false, error: undefined });
        // Attempt to recover by clearing some state if needed, or just reload
        window.location.reload();
    };

    render() {
        if (this.state.hasError) {
            return (
                <div className="h-screen w-screen flex flex-col items-center justify-center bg-slate-50 text-slate-900 p-6">
                    <div className="bg-white p-8 rounded-2xl shadow-xl border border-slate-200 max-w-lg w-full text-center space-y-6">
                        <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto">
                            <AlertOctagon className="w-8 h-8 text-red-600" />
                        </div>

                        <div className="space-y-2">
                            <h1 className="text-2xl font-bold tracking-tight">System Error</h1>
                            <p className="text-slate-500 text-sm">
                                The application encountered a critical error and cannot continue.
                            </p>
                        </div>

                        <div className="bg-red-50 p-4 rounded-lg text-left overflow-auto max-h-40 border border-red-100">
                            <code className="text-xs font-mono text-red-700 break-all">
                                {this.state.error?.message || "Unknown error occurred"}
                            </code>
                        </div>

                        <div className="flex items-center justify-center gap-3 pt-2">
                            <button
                                onClick={() => window.location.href = "/"}
                                className="flex items-center gap-2 px-5 py-2.5 rounded-xl border border-slate-200 hover:bg-slate-50 font-medium text-slate-700 transition-colors"
                            >
                                <Home className="w-4 h-4" />
                                Return Home
                            </button>
                            <button
                                onClick={this.handleReset}
                                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-blue-600 hover:bg-blue-700 text-white font-bold shadow-sm transition-all hover:scale-105 active:scale-95"
                            >
                                <RefreshCw className="w-4 h-4" />
                                Reload Application
                            </button>
                        </div>
                    </div>

                    <div className="mt-8 text-xs text-slate-400 font-mono">
                        Error Code: CRITICAL_RENDER_FAILURE
                    </div>
                </div>
            );
        }

        return this.props.children;
    }
}
