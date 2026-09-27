import React, { useEffect, useState, useCallback } from 'react';

interface DependencyStatus {
  status: string;
  latency_ms?: number;
  error?: string | null;
  database?: string;
  host?: string;
}

interface HealthResponse {
  status: string;
  timestamp: string;
  environment: string;
  airgap_strict_mode: boolean;
  dependencies: {
    postgres: DependencyStatus;
    qdrant: DependencyStatus;
    falkordb: DependencyStatus;
  };
}

export const ServiceStatus: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('');

  const fetchHealth = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch('/health');
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data: HealthResponse = await res.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Offline');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const isAllHealthy =
    health?.status === 'healthy' &&
    health?.dependencies?.postgres?.status === 'healthy' &&
    health?.dependencies?.qdrant?.status === 'healthy' &&
    health?.dependencies?.falkordb?.status === 'healthy';

  return (
    <div className="bg-[#F8F7F3] border border-[#D8D5CE] rounded-lg px-3.5 py-2 flex flex-wrap items-center justify-between gap-3 text-xs font-mono shadow-soft">
      <div className="flex items-center space-x-3 overflow-x-auto py-0.5">
        {/* Master Status */}
        <div className="flex items-center space-x-2 shrink-0">
          <span className={`w-1.5 h-1.5 rounded-full ${isAllHealthy ? 'bg-[#7E9D82]' : error ? 'bg-[#C87970]' : 'bg-[#EBCB72]'}`}></span>
          <span className="font-medium text-[#252525]">
            {error ? 'Service Alert' : isAllHealthy ? 'Workstation Core Active' : 'Connecting...'}
          </span>
        </div>

        <span className="text-[#D8D5CE]">|</span>

        {/* FastAPI Backend */}
        <div className="flex items-center space-x-1.5 text-[#6F6D68] shrink-0">
          <span className="text-[11px] text-[#99958D]">API:</span>
          <span className="text-[#30302E]">8001</span>
          <span className="text-[#7E9D82] text-[9px]">●</span>
        </div>

        <span className="text-[#D8D5CE]">·</span>

        {/* PostgreSQL */}
        <div className="flex items-center space-x-1.5 text-[#6F6D68] shrink-0">
          <span className="text-[11px] text-[#99958D]">SQL:</span>
          <span className="text-[#30302E]">5432</span>
          {health?.dependencies?.postgres?.latency_ms !== undefined && (
            <span className="text-[#99958D] text-[10px]">({Math.round(health.dependencies.postgres.latency_ms)}ms)</span>
          )}
          <span className={health?.dependencies?.postgres?.status === 'healthy' ? 'text-[#7E9D82] text-[9px]' : 'text-[#EBCB72] text-[9px]'}>●</span>
        </div>

        <span className="text-[#D8D5CE]">·</span>

        {/* Qdrant */}
        <div className="flex items-center space-x-1.5 text-[#6F6D68] shrink-0">
          <span className="text-[11px] text-[#99958D]">Vector:</span>
          <span className="text-[#30302E]">6335</span>
          {health?.dependencies?.qdrant?.latency_ms !== undefined && (
            <span className="text-[#99958D] text-[10px]">({Math.round(health.dependencies.qdrant.latency_ms)}ms)</span>
          )}
          <span className={health?.dependencies?.qdrant?.status === 'healthy' ? 'text-[#7E9D82] text-[9px]' : 'text-[#EBCB72] text-[9px]'}>●</span>
        </div>

        <span className="text-[#D8D5CE]">·</span>

        {/* FalkorDB */}
        <div className="flex items-center space-x-1.5 text-[#6F6D68] shrink-0">
          <span className="text-[11px] text-[#99958D]">Graph:</span>
          <span className="text-[#30302E]">6379</span>
          {health?.dependencies?.falkordb?.latency_ms !== undefined && (
            <span className="text-[#99958D] text-[10px]">({Math.round(health.dependencies.falkordb.latency_ms)}ms)</span>
          )}
          <span className={health?.dependencies?.falkordb?.status === 'healthy' ? 'text-[#7E9D82] text-[9px]' : 'text-[#EBCB72] text-[9px]'}>●</span>
        </div>
      </div>

      {/* Timestamp & Refresh */}
      <div className="flex items-center space-x-2 text-[11px] text-[#99958D] ml-auto shrink-0">
        {lastChecked && <span>Synced {lastChecked}</span>}
        <button
          onClick={fetchHealth}
          disabled={loading}
          className="p-1 hover:text-[#252525] text-[#6F6D68] transition disabled:opacity-50"
          title="Refresh telemetry"
        >
          <svg className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>
  );
};
