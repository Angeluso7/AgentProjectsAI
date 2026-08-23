import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import {
  Activity, CheckCircle2, AlertTriangle, XCircle, RefreshCw,
  Cpu, Layers, Eye, Table, Scale, Network, Bot, X
} from 'lucide-react';

interface EngineHealthModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const EngineHealthModal: React.FC<EngineHealthModalProps> = ({ isOpen, onClose }) => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (isOpen) {
      loadHealth();
    }
  }, [isOpen]);

  const loadHealth = async () => {
    try {
      setLoading(true);
      const res = await apiService.getEngineHealth();
      setData(res);
    } catch (e) {
      console.error("Error loading engine health:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleRunLiveTest = async () => {
    try {
      setTesting(true);
      const res = await apiService.testEngineHealth();
      setData(res);
    } catch (e) {
      console.error("Error testing engines:", e);
    } finally {
      setTesting(false);
    }
  };

  if (!isOpen) return null;

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'ocr': return <Cpu className="w-5 h-5 text-indigo-400" />;
      case 'layout': return <Layers className="w-5 h-5 text-blue-400" />;
      case 'tables': return <Table className="w-5 h-5 text-teal-400" />;
      case 'symbols': return <Eye className="w-5 h-5 text-purple-400" />;
      case 'rules': return <Scale className="w-5 h-5 text-amber-400" />;
      case 'embeddings': return <Network className="w-5 h-5 text-emerald-400" />;
      case 'llm': return <Bot className="w-5 h-5 text-rose-400" />;
      default: return <Activity className="w-5 h-5 text-slate-400" />;
    }
  };

  const getStatusBadge = (status: string) => {
    if (status === 'OK') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60">
          <CheckCircle2 className="w-3.5 h-3.5" /> OK / OPERATIVO
        </span>
      );
    }
    if (status === 'FALLBACK') {
      return (
        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/60">
          <AlertTriangle className="w-3.5 h-3.5" /> FALLBACK ACTIVO
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/60">
        <XCircle className="w-3.5 h-3.5" /> ERROR
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-500/10 border border-indigo-500/30 rounded-xl text-indigo-400">
              <Activity className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                Estado Operativo de Motores IA & Pipeline
                {data && (
                  <span className="text-xs px-2 py-0.5 bg-slate-800 border border-slate-700 text-slate-300 rounded-full font-normal">
                    {data.engines_ok} OK / {data.engines_fallback} Fallback
                  </span>
                )}
              </h2>
              <p className="text-xs text-slate-400">Diagnóstico en tiempo real de cada componente de inferencia y extracción</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={handleRunLiveTest}
              disabled={testing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-semibold transition-all shadow disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${testing ? 'animate-spin' : ''}`} />
              {testing ? 'Ejecutando Test...' : 'Ejecutar Test en Vivo'}
            </button>
            <button
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-4">
          {loading && !data ? (
            <div className="py-12 flex flex-col items-center justify-center text-slate-400 gap-3">
              <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
              <p className="text-sm">Consultando estado de los motores...</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {data?.engines?.map((eng: any) => (
                <div
                  key={eng.category}
                  className="p-4 bg-slate-800/60 border border-slate-700/70 rounded-xl flex flex-col justify-between hover:border-slate-600 transition-colors shadow-sm"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2.5">
                        <div className="p-1.5 bg-slate-800 rounded-lg border border-slate-700">
                          {getCategoryIcon(eng.category)}
                        </div>
                        <div>
                          <h4 className="text-sm font-bold text-slate-100">{eng.name}</h4>
                          <span className="text-[11px] text-slate-400 font-mono">{eng.type} • {eng.cost}</span>
                        </div>
                      </div>
                      {getStatusBadge(eng.status)}
                    </div>

                    <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">
                      {eng.description}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-700/50 flex items-center justify-between text-xs">
                    <div>
                      <span className="text-slate-400 text-[11px]">Motor Activo: </span>
                      <span className="font-semibold text-indigo-300 font-mono text-[11px]">{eng.active_engine}</span>
                    </div>
                    <div className="flex items-center gap-1.5 text-slate-400 text-[11px]">
                      <span>Latencia:</span>
                      <span className="font-mono font-bold text-emerald-400">{eng.latency_ms} ms</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between text-xs text-slate-400">
          <span>Todos los motores operan de forma local o con fallback determinístico garantizado.</span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-xs font-semibold transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
