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
                <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-400 border border-indigo-800/50">
                  Phase 0 Skeleton
                </span>
              </div>
              <p className="text-[11px] text-gray-400 hidden sm:block">
                Fully offline, air-gapped GenAI transformation enclave with claim provenance
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <div className="hidden md:flex items-center space-x-2 text-xs font-mono text-gray-400 bg-gray-900/90 px-3 py-1.5 rounded-lg border border-gray-800">
              <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
              <span>Enclave: Air-Gapped</span>
            </div>
            <div className="text-xs px-2.5 py-1 rounded bg-gray-800 border border-gray-700 font-mono text-gray-300">
              Role: Operator
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
          <div>SIH26155 GenAI Automated Content Transformation &bull; Zero External Network Calls</div>
          <div className="text-gray-400">Phase 0: Environment & Scaffolding Verified</div>
        </div>
      </footer>
    </div>
  );
};

export default App;
