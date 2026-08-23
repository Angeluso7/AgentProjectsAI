import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { EngineDefinitionItem, EnginesSummaryResponse } from '../types';
import {
  Cpu, Layers, Table, Eye, Scale, Network, Bot, CheckCircle2,
  AlertTriangle, XCircle, RefreshCw, Sliders, Key, Zap, Shield,
  Info, Sparkles, Check, ChevronRight, Globe, HardDrive, DollarSign
} from 'lucide-react';

export const AiEnginesPage: React.FC = () => {
  const [engines, setEngines] = useState<EngineDefinitionItem[]>([]);
  const [summary, setSummary] = useState<EnginesSummaryResponse | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [loading, setLoading] = useState(false);
  const [testingEngineId, setTestingEngineId] = useState<string | null>(null);
  const [activatingEngineId, setActivatingEngineId] = useState<string | null>(null);
  
  // Modals state
  const [configModalEngine, setConfigModalEngine] = useState<EngineDefinitionItem | null>(null);
  const [credentialsModalEngine, setCredentialsModalEngine] = useState<EngineDefinitionItem | null>(null);
  const [configForm, setConfigForm] = useState<Record<string, any>>({});
  const [credentialsForm, setCredentialsForm] = useState<Record<string, string>>({});
  const [savingConfig, setSavingConfig] = useState(false);

  useEffect(() => {
    loadData();
  }, [selectedCategory]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [enginesData, summaryData] = await Promise.all([
        apiService.getEngines(selectedCategory),
        apiService.getEnginesSummary()
      ]);
      setEngines(enginesData);
      setSummary(summaryData);
    } catch (e) {
      console.error("Error al cargar motores de IA:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleSetActive = async (category: string, engineId: string) => {
    try {
      setActivatingEngineId(engineId);
      await apiService.setActiveEngine(category, engineId);
      await loadData();
    } catch (e: any) {
      alert(`Error al activar motor: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setActivatingEngineId(null);
    }
  };

  const handleTestEngine = async (category: string, engineId: string) => {
    try {
      setTestingEngineId(engineId);
      const res = await apiService.testEngine(category, engineId);
      setEngines(prev => prev.map(eng => {
        if (eng.id === engineId && eng.category === category) {
          return {
            ...eng,
            latency_ms: res.latency_ms,
            last_tested: res.last_tested,
            last_error: res.error,
            status: res.status === 'OK' ? (eng.is_active ? 'active' : 'inactive') : (res.status === 'FALLBACK' ? 'fallback' : 'inactive')
          };
        }
        return eng;
      }));
    } catch (e: any) {
      alert(`Error en prueba de motor: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setTestingEngineId(null);
    }
  };

  const openConfigModal = (engine: EngineDefinitionItem) => {
    setConfigModalEngine(engine);
    setConfigForm({ ...engine.parameters });
  };

  const handleSaveConfig = async () => {
    if (!configModalEngine) return;
    try {
      setSavingConfig(true);
      const updated = await apiService.updateEngineConfig(
        configModalEngine.category,
        configModalEngine.id,
        configForm
      );
      setEngines(prev => prev.map(e => (e.id === updated.id && e.category === updated.category ? updated : e)));
      setConfigModalEngine(null);
    } catch (e: any) {
      alert(`Error guardando configuración: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const openCredentialsModal = (engine: EngineDefinitionItem) => {
    setCredentialsModalEngine(engine);
    const initial: Record<string, string> = {};
    engine.required_credentials.forEach(c => { initial[c] = ''; });
    setCredentialsForm(initial);
  };

  const handleSaveCredentials = async () => {
    if (!credentialsModalEngine) return;
    try {
      setSavingConfig(true);
      const updated = await apiService.updateEngineCredentials(
        credentialsModalEngine.category,
        credentialsModalEngine.id,
        credentialsForm
      );
      setEngines(prev => prev.map(e => (e.id === updated.id && e.category === updated.category ? updated : e)));
      setCredentialsModalEngine(null);
      alert('Credenciales actualizadas exitosamente en el entorno del servidor.');
    } catch (e: any) {
      alert(`Error guardando credenciales: ${e?.response?.data?.detail || e.message}`);
    } finally {
      setSavingConfig(false);
    }
  };

  const categories = [
    { id: 'all', label: 'Todos los Motores', icon: Cpu, count: summary?.total_engines || 0 },
    { id: 'ocr', label: 'OCR & Capas Vectoriales', icon: Cpu, activeName: summary?.categories?.ocr?.active_engine_name },
    { id: 'symbols', label: 'Detección Visual & Símbolos', icon: Eye, activeName: summary?.categories?.symbols?.active_engine_name },
    { id: 'layout', label: 'Layout & Viñetas', icon: Layers, activeName: summary?.categories?.layout?.active_engine_name },
    { id: 'tables', label: 'Tablas Técnicas', icon: Table, activeName: summary?.categories?.tables?.active_engine_name },
    { id: 'embeddings', label: 'Embeddings & Ontologías', icon: Network, activeName: summary?.categories?.embeddings?.active_engine_name },
    { id: 'llm', label: 'LLM & Razonador', icon: Bot, activeName: summary?.categories?.llm?.active_engine_name },
    { id: 'rules', label: 'Reglas QA/QC', icon: Scale, activeName: summary?.categories?.rules?.active_engine_name },
  ];

  const getCostBadge = (tier: string) => {
    switch (tier) {
      case 'gratis':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950/70 text-emerald-400 border border-emerald-800/60"><Check className="w-3 h-3" /> GRATIS (LOCAL)</span>;
      case 'pago':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950/70 text-amber-400 border border-amber-800/60"><DollarSign className="w-3 h-3" /> PAGO / API KEY</span>;
      case 'mixto':
        return <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-bold bg-blue-950/70 text-blue-400 border border-blue-800/60"><Sparkles className="w-3 h-3" /> MIXTO / TIER GRATUITO</span>;
      default:
        return <span className="text-[11px] text-slate-400">{tier}</span>;
    }
  };

  const getEngineTypeIcon = (type: string) => {
    switch (type) {
      case 'local':
      case 'open_source':
        return <span title="Ejecución local en servidor / contenedor"><HardDrive className="w-3.5 h-3.5 text-emerald-400" /></span>;
      case 'api_cloud':
      case 'paid_saas':
        return <span title="API Cloud Externa"><Globe className="w-3.5 h-3.5 text-sky-400" /></span>;
      default:
        return <Cpu className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-in fade-in duration-300">
      {/* Header & KPI Metrics */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/90 border border-slate-800 p-6 rounded-2xl shadow-xl">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-xl text-indigo-400">
              <Zap className="w-7 h-7" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-slate-100 flex items-center gap-2">
                Gestión de IAs & Motores del Pipeline
              </h1>
              <p className="text-sm text-slate-400">
                Selecciona, calibra y conmuta los modelos de visión, OCR, tablas, embeddings y reglas en caliente.
              </p>
            </div>
          </div>
        </div>

        {summary && (
          <div className="flex items-center gap-3 bg-slate-950/60 border border-slate-800/80 p-3 rounded-xl">
            <div className="text-center px-3 border-r border-slate-800">
              <div className="text-xl font-bold text-slate-100">{summary.total_engines}</div>
              <div className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold">Motores</div>
            </div>
            <div className="text-center px-3 border-r border-slate-800">
              <div className="text-xl font-bold text-emerald-400">{summary.free_engines}</div>
              <div className="text-[10px] uppercase tracking-wider text-emerald-500 font-semibold">Gratis / Local</div>
            </div>
            <div className="text-center px-3">
              <div className="text-xl font-bold text-amber-400">{summary.paid_engines}</div>
              <div className="text-[10px] uppercase tracking-wider text-amber-500 font-semibold">API / Pago</div>
            </div>
          </div>
        )}
      </div>

      {/* Category Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-thin">
        {categories.map(cat => {
          const isSelected = selectedCategory === cat.id;
          const Icon = cat.icon;
          return (
            <button
              key={cat.id}
              onClick={() => setSelectedCategory(cat.id)}
              className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold whitespace-nowrap transition-all border ${
                isSelected
                  ? 'bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/20'
                  : 'bg-slate-900/60 text-slate-400 border-slate-800 hover:bg-slate-800 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{cat.label}</span>
              {cat.count !== undefined && (
                <span className={`px-1.5 py-0.5 rounded-full text-[10px] ${
                  isSelected ? 'bg-indigo-700 text-white' : 'bg-slate-800 text-slate-400'
                }`}>
                  {cat.count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Engine Cards Grid */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
          <RefreshCw className="w-8 h-8 animate-spin text-indigo-400" />
          <p className="text-sm">Cargando catálogo de motores IA...</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {engines.map(engine => {
            const isTesting = testingEngineId === engine.id;
            const isActivating = activatingEngineId === engine.id;

            return (
              <div
                key={`${engine.category}-${engine.id}`}
                className={`relative flex flex-col justify-between p-5 rounded-2xl border transition-all ${
                  engine.is_active
                    ? 'bg-slate-900/90 border-indigo-500/70 ring-1 ring-indigo-500/40 shadow-xl shadow-indigo-950/30'
                    : 'bg-slate-900/50 border-slate-800 hover:border-slate-700/80 shadow-md'
                }`}
              >
                {/* Active Indicator Ribbon */}
                {engine.is_active && (
                  <div className="absolute top-4 right-4 flex items-center gap-1.5 px-2.5 py-1 bg-indigo-500/20 border border-indigo-500/40 rounded-full text-indigo-300 text-[11px] font-bold">
                    <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400" />
                    <span>ACTIVO EN PIPELINE</span>
                  </div>
                )}

                <div className="space-y-3">
                  {/* Top info */}
                  <div className="pr-28">
                    <span className="text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                      {engine.provider}
                    </span>
                    <h3 className="text-base font-bold text-slate-100 leading-snug">
                      {engine.model_name}
                    </h3>
                  </div>

                  {/* Badges & Meta */}
                  <div className="flex flex-wrap items-center gap-2 pt-1">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-slate-800 border border-slate-700 text-slate-300 text-[11px] rounded font-mono">
                      {getEngineTypeIcon(engine.engine_type)}
                      v{engine.version}
                    </span>
                    {getCostBadge(engine.cost_tier)}
                  </div>

                  {/* Description */}
                  <p className="text-xs text-slate-300 leading-relaxed pt-1">
                    {engine.description}
                  </p>

                  {/* Notes / Warnings */}
                  {engine.notes && (
                    <div className="p-2.5 bg-slate-950/60 border border-slate-800/80 rounded-xl text-[11px] text-slate-400 flex items-start gap-2">
                      <Info className="w-4 h-4 text-indigo-400 shrink-0 mt-0.5" />
                      <span>{engine.notes}</span>
                    </div>
                  )}

                  {/* Disciplines Scope */}
                  {engine.disciplines && engine.disciplines.length > 0 && (
                    <div className="flex items-center gap-1 flex-wrap text-[11px]">
                      <span className="text-slate-400">Alcance:</span>
                      {engine.disciplines.map(d => (
                        <span key={d} className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded text-[10px]">
                          {d}
                        </span>
                      ))}
                    </div>
                  )}

                  {/* Credentials warning if required but missing */}
                  {engine.required_credentials.length > 0 && !engine.has_credentials && (
                    <div className="p-2.5 bg-amber-950/40 border border-amber-800/50 rounded-xl text-[11px] text-amber-300 flex items-center justify-between">
                      <span className="flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
                        Faltan credenciales ({engine.required_credentials.join(', ')})
                      </span>
                      <button
                        onClick={() => openCredentialsModal(engine)}
                        className="text-amber-200 underline font-semibold hover:text-white"
                      >
                        Configurar
                      </button>
                    </div>
                  )}
                </div>

                {/* Footer Controls */}
                <div className="mt-5 pt-4 border-t border-slate-800/80 space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400">
                    <div>
                      <span>Latencia: </span>
                      <span className="font-mono font-bold text-emerald-400">
                        {engine.latency_ms ? `${engine.latency_ms} ms` : '--'}
                      </span>
                    </div>
                    {engine.last_tested && (
                      <span className="text-[10px] text-slate-400">
                        Probado: {new Date(engine.last_tested).toLocaleTimeString()}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {engine.is_active ? (
                      <div className="flex-1 py-2 px-3 bg-emerald-950/40 border border-emerald-800/50 text-emerald-400 rounded-xl text-xs font-semibold text-center flex items-center justify-center gap-1.5">
                        <Check className="w-3.5 h-3.5" /> Motor Seleccionado
                      </div>
                    ) : (
                      <button
                        onClick={() => handleSetActive(engine.category, engine.id)}
                        disabled={isActivating}
                        className="flex-1 py-2 px-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-all shadow disabled:opacity-50 flex items-center justify-center gap-1.5"
                      >
                        {isActivating ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Zap className="w-3.5 h-3.5" />
                        )}
                        <span>{isActivating ? 'Activando...' : 'Activar Motor'}</span>
                      </button>
                    )}

                    <button
                      onClick={() => handleTestEngine(engine.category, engine.id)}
                      disabled={isTesting}
                      title="Probar latencia y conectividad del motor"
                      className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 transition-colors disabled:opacity-50"
                    >
                      <RefreshCw className={`w-4 h-4 ${isTesting ? 'animate-spin text-indigo-400' : ''}`} />
                    </button>

                    <button
                      onClick={() => openConfigModal(engine)}
                      title="Configurar parámetros operacionales (thresholds, DPI, etc.)"
                      className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 transition-colors"
                    >
                      <Sliders className="w-4 h-4" />
                    </button>

                    {engine.required_credentials.length > 0 && (
                      <button
                        onClick={() => openCredentialsModal(engine)}
                        title="Configurar API Keys / Credenciales"
                        className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl border border-slate-700 transition-colors"
                      >
                        <Key className="w-4 h-4 text-amber-400" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Modal: Configuración de Parámetros */}
      {configModalEngine && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Sliders className="w-5 h-5 text-indigo-400" />
                <h3 className="text-base font-bold text-slate-100">
                  Calibrar Parámetros: {configModalEngine.model_name}
                </h3>
              </div>
              <button
                onClick={() => setConfigModalEngine(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <p className="text-xs text-slate-400">
                Ajusta los umbrales de sensibilidad y parámetros operacionales específicos de este motor.
              </p>

              {Object.keys(configForm).length === 0 ? (
                <p className="text-xs text-slate-400 italic">Este motor no requiere parámetros adicionales.</p>
              ) : (
                Object.entries(configForm).map(([key, value]) => (
                  <div key={key} className="space-y-1.5">
                    <label className="text-xs font-semibold text-slate-300 font-mono">
                      {key}
                    </label>
                    {typeof value === 'boolean' ? (
                      <select
                        value={value ? 'true' : 'false'}
                        onChange={e => setConfigForm({ ...configForm, [key]: e.target.value === 'true' })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none"
                      >
                        <option value="true">Activado (True)</option>
                        <option value="false">Desactivado (False)</option>
                      </select>
                    ) : typeof value === 'number' ? (
                      <input
                        type="number"
                        step={value <= 1 ? "0.05" : "1"}
                        value={value}
                        onChange={e => setConfigForm({ ...configForm, [key]: parseFloat(e.target.value) || 0 })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none font-mono"
                      />
                    ) : (
                      <input
                        type="text"
                        value={value}
                        onChange={e => setConfigForm({ ...configForm, [key]: e.target.value })}
                        className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-indigo-500 focus:outline-none font-mono"
                      />
                    )}
                  </div>
                ))
              )}
            </div>

            <div className="px-6 py-3 border-t border-slate-800 flex items-center justify-end gap-2 bg-slate-950/40">
              <button
                onClick={() => setConfigModalEngine(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveConfig}
                disabled={savingConfig}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-semibold transition-all shadow disabled:opacity-50"
              >
                {savingConfig ? 'Guardando...' : 'Guardar Parámetros'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Credenciales & API Keys */}
      {credentialsModalEngine && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
            <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Key className="w-5 h-5 text-amber-400" />
                <h3 className="text-base font-bold text-slate-100">
                  Credenciales: {credentialsModalEngine.provider}
                </h3>
              </div>
              <button
                onClick={() => setCredentialsModalEngine(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <div className="p-6 space-y-4">
              <p className="text-xs text-slate-400">
                Las claves se configuran de forma segura en las variables de entorno del servidor.
              </p>

              {credentialsModalEngine.required_credentials.map(credKey => (
                <div key={credKey} className="space-y-1.5">
                  <label className="text-xs font-semibold text-slate-300 font-mono">
                    {credKey}
                  </label>
                  <input
                    type="password"
                    placeholder={`Ingresa ${credKey}...`}
                    value={credentialsForm[credKey] || ''}
                    onChange={e => setCredentialsForm({ ...credentialsForm, [credKey]: e.target.value })}
                    className="w-full bg-slate-950 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:border-amber-500 focus:outline-none font-mono"
                  />
                </div>
              ))}
            </div>

            <div className="px-6 py-3 border-t border-slate-800 flex items-center justify-end gap-2 bg-slate-950/40">
              <button
                onClick={() => setCredentialsModalEngine(null)}
                className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold"
              >
                Cancelar
              </button>
              <button
                onClick={handleSaveCredentials}
                disabled={savingConfig}
                className="px-5 py-2 bg-amber-600 hover:bg-amber-500 text-white rounded-xl text-xs font-semibold transition-all shadow disabled:opacity-50"
              >
                {savingConfig ? 'Guardando...' : 'Guardar Credenciales'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
