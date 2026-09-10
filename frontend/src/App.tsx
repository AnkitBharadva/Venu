import React from 'react';
import { ServiceStatus } from './components/ServiceStatus';
import { BlankDashboard } from './components/BlankDashboard';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#0b0f19] text-gray-100 flex flex-col justify-between">
      {/* Top Header */}
      <header className="border-b border-gray-800/80 bg-gray-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3.5 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-md shadow-indigo-600/30">
              AG
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-sm sm:text-base font-bold text-white tracking-tight">
                  SIH26155 &mdash; GenAI Content Transformation Platform
                </h1>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-700/60 font-semibold">
                  Air-Gapped &bull; 100% Offline
                </span>
              </div>
              <p className="text-[11px] text-gray-400 hidden sm:block">
                Autonomous multi-format content transformation with claim-to-source provenance
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2 text-xs font-mono text-gray-300 bg-gray-900/90 px-3 py-1.5 rounded-lg border border-gray-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>Enclave Isolated</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workspace Area */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-6">
        {/* Service Health Monitoring Section */}
        <ServiceStatus />

        {/* Blank Dashboard Canvas */}
        <BlankDashboard />
      </main>

      {/* Footer */}
      <footer className="border-t border-gray-900 bg-gray-950 py-4 text-center text-xs text-gray-500 font-mono">
        <div className="max-w-7xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>GenAI Automated Content Transformation &bull; Zero External Network Calls</div>
          <div className="text-gray-400">Cryptographic Provenance &bull; AES-256-GCM Secured</div>
        </div>
      </footer>
    </div>
  );
};

export default App;
