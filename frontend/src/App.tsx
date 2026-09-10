import React from 'react';
import { ServiceStatus } from './components/ServiceStatus';
import { BlankDashboard } from './components/BlankDashboard';

export const App: React.FC = () => {
  return (
    <div className="min-h-screen bg-[#F3F1EC] text-[#252525] flex flex-col justify-between">
      {/* Top Workstation Masthead */}
      <header className="border-b border-[#D8D5CE] bg-[#F8F7F3]/90 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          {/* Logo & Product Identity */}
          <div className="flex items-center space-x-3.5">
            <div className="w-8 h-8 rounded bg-[#30302E] flex items-center justify-center font-serif text-white text-base font-semibold tracking-wide shadow-soft">
              V
            </div>
            <div>
              <div className="flex items-center space-x-2.5">
                <h1 className="text-base font-bold text-[#252525] tracking-wider font-mono">
                  VENÜ
                </h1>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#EAE8E1] text-[#6F6D68] border border-[#D8D5CE]">
                  v1.0
                </span>
                <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-[#FCFBF8] text-[#7E9D82] border border-[#D8D5CE] flex items-center space-x-1 font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#7E9D82]"></span>
                  <span>Air-Gapped</span>
                </span>
              </div>
              <p className="text-xs text-[#6F6D68] mt-0.5">
                Autonomous multi-format content transformation with claim provenance
              </p>
            </div>
          </div>

          {/* Right Status Indicator */}
          <div className="flex items-center space-x-2.5 self-start sm:self-auto text-xs font-mono text-[#6F6D68]">
            <div className="px-3 py-1 rounded bg-[#FCFBF8] border border-[#D8D5CE] text-[#30302E] flex items-center space-x-1.5 shadow-soft">
              <span className="w-1.5 h-1.5 rounded-full bg-[#E8A36A]"></span>
              <span>Operator Console</span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Workstation Workspace */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 flex-1 w-full space-y-4">
        {/* Compact Enclave Telemetry Bar */}
        <ServiceStatus />

        {/* The VENU Workspace Component */}
        <BlankDashboard />
      </main>

      {/* Editorial Workstation Footer */}
      <footer className="border-t border-[#D8D5CE] bg-[#F8F7F3] py-3.5 text-xs text-[#6F6D68] font-mono">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-2">
          <div>VENÜ &bull; Calm Intelligence Workstation</div>
          <div className="text-[#99958D]">100% Claim-to-Chunk Provenance &bull; Encrypted at Rest (AES-256-GCM)</div>
        </div>
      </footer>
    </div>
  );
};

export default App;
