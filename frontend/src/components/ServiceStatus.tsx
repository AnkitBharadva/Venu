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
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }
      const data: HealthResponse = await res.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to connect to backend service');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  const getStatusBadge = (statusName?: string) => {
    if (statusName === 'healthy' || statusName === 'ok') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-950 text-emerald-400 border border-emerald-800/60">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1.5 animate-pulse"></span>
          Operational
        </span>
      );
    }
    if (statusName === 'degraded') {
      return (
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-950 text-amber-400 border border-amber-800/60">
          <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1.5"></span>
          Degraded
        </span>
      );
    }
    return (
      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-950 text-rose-400 border border-rose-800/60">
        <span className="w-1.5 h-1.5 rounded-full bg-rose-400 mr-1.5"></span>
        Unreachable
      </span>
    );
  };

  return (
    <div className="bg-gray-900/80 backdrop-blur border border-gray-800 rounded-xl p-5 shadow-lg">
      <div className="flex items-center justify-between pb-4 mb-4 border-b border-gray-800">
        <div className="flex items-center space-x-3">
          <div className="w-3 h-3 rounded-full bg-indigo-500 shadow-sm shadow-indigo-500/50"></div>
          <h2 className="text-base font-semibold text-white tracking-wide">
            Enclave Infrastructure Health
          </h2>
          <span className="text-xs px-2 py-0.5 rounded bg-gray-800 text-gray-400 font-mono">
            Zero Egress Guarded
          </span>
        </div>

        <div className="flex items-center space-x-3">
          {lastChecked && (
            <span className="text-xs text-gray-500 font-mono">Checked: {lastChecked}</span>
          )}
          <button
            onClick={fetchHealth}
            disabled={loading}
            className="text-xs px-3 py-1.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg border border-gray-700 transition font-medium flex items-center space-x-1.5 disabled:opacity-50"
          >
            <span>{loading ? 'Probing...' : 'Refresh Status'}</span>
          </button>
        </div>
      </div>

      {error ? (
        <div className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/50 text-rose-300 text-sm flex items-start space-x-3">
          <span className="text-rose-400 text-base">⚠️</span>
          <div>
            <p className="font-medium">Backend Connection Error</p>
            <p className="text-xs text-rose-400/80 mt-0.5">{error}</p>
            <p className="text-xs text-gray-400 mt-2">
              Ensure the backend service is running on port 8000 via Docker Compose or locally via{' '}
              <code className="bg-black/30 px-1 py-0.5 rounded text-amber-300">conda activate tri</code>.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Backend Service */}
          <div className="bg-gray-950/60 p-4 rounded-lg border border-gray-800/80">
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">FastAPI Backend</span>
              {getStatusBadge(health?.status)}
            </div>
            <div className="text-sm font-semibold text-gray-100 mt-1">Core Orchestrator</div>
            <div className="text-xs text-gray-500 font-mono mt-1">Port 8000 &bull; REST API</div>
          </div>

          {/* PostgreSQL */}
          <div className="bg-gray-950/60 p-4 rounded-lg border border-gray-800/80">
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">PostgreSQL</span>
              {getStatusBadge(health?.dependencies?.postgres?.status)}
            </div>
            <div className="text-sm font-semibold text-gray-100 mt-1">Metadata & Audit Log</div>
            <div className="text-xs text-gray-500 font-mono mt-1 flex justify-between">
              <span>Port 5432 &bull; AsyncPG</span>
              {health?.dependencies?.postgres?.latency_ms !== undefined && (
                <span className="text-emerald-400 font-medium">{health.dependencies.postgres.latency_ms}ms</span>
              )}
            </div>
          </div>

          {/* Qdrant */}
          <div className="bg-gray-950/60 p-4 rounded-lg border border-gray-800/80">
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Qdrant Store</span>
              {getStatusBadge(health?.dependencies?.qdrant?.status)}
            </div>
            <div className="text-sm font-semibold text-gray-100 mt-1">Vector Grounding</div>
            <div className="text-xs text-gray-500 font-mono mt-1 flex justify-between">
              <span>Port 6333 &bull; REST/gRPC</span>
              {health?.dependencies?.qdrant?.latency_ms !== undefined && (
                <span className="text-emerald-400 font-medium">{health.dependencies.qdrant.latency_ms}ms</span>
              )}
            </div>
          </div>

          {/* FalkorDB */}
          <div className="bg-gray-950/60 p-4 rounded-lg border border-gray-800/80">
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">FalkorDB</span>
              {getStatusBadge(health?.dependencies?.falkordb?.status)}
            </div>
            <div className="text-sm font-semibold text-gray-100 mt-1">Graph Entity Store</div>
            <div className="text-xs text-gray-500 font-mono mt-1 flex justify-between">
              <span>Port 6379 &bull; Cypher Graph</span>
              {health?.dependencies?.falkordb?.latency_ms !== undefined && (
                <span className="text-emerald-400 font-medium">{health.dependencies.falkordb.latency_ms}ms</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
