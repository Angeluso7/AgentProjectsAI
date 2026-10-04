import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { EvaluationDatasetItem, EvaluationSampleItem, AnnotationSetItem, EvaluationRunItem } from '../types';
import {
  Database, Play, CheckCircle2, AlertTriangle, XCircle, ShieldCheck,
  Lock, Plus, FileText, Layers, Table, Sparkles, RefreshCw, BarChart3, Award
} from 'lucide-react';

export const EvaluationPage: React.FC = () => {
  const [datasets, setDatasets] = useState<EvaluationDatasetItem[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<EvaluationDatasetItem | null>(null);
  const [samples, setSamples] = useState<EvaluationSampleItem[]>([]);
  const [selectedSample, setSelectedSample] = useState<EvaluationSampleItem | null>(null);
  const [annotations, setAnnotations] = useState<AnnotationSetItem[]>([]);
  const [runs, setRuns] = useState<EvaluationRunItem[]>([]);
  const [selectedRun, setSelectedRun] = useState<EvaluationRunItem | null>(null);
  
  const [loading, setLoading] = useState(false);
  const [evaluating, setEvaluating] = useState(false);
  const [activeTab, setActiveTab] = useState<'datasets' | 'samples' | 'runs'>('datasets');

  // Carga inicial
  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    try {
      setLoading(true);
      const data = await apiService.getEvaluationDatasets();
      setDatasets(data);
      if (data.length > 0 && !selectedDataset) {
        selectDataset(data[0]);
      }
    } catch (err) {
      console.error("Error al cargar datasets de evaluación:", err);
    } finally {
      setLoading(false);
    }
  };

  const selectDataset = async (dataset: EvaluationDatasetItem) => {
    setSelectedDataset(dataset);
    try {
      setLoading(true);
      const runsData = await apiService.getEvaluationRuns(dataset.id);
      setRuns(runsData);
      if (runsData.length > 0) {
        setSelectedRun(runsData[0]);
      } else {
        setSelectedRun(null);
      }
    } catch (err) {
      console.error("Error al cargar corridas del dataset:", err);
    } finally {
      setLoading(false);
    }
  };

  const handleFreezeDataset = async () => {
    if (!selectedDataset) return;
    if (!confirm(`¿Deseas congelar el dataset '${selectedDataset.name}'? Esto creará un snapshot SHA-256 inmutable de las anotaciones aprobadas.`)) return;
    try {
      setLoading(true);
      const updated = await apiService.freezeEvaluationDataset(selectedDataset.id);
      setSelectedDataset(updated);
      loadDatasets();
    } catch (err: any) {
      alert(`Error al congelar dataset: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async (split: string = 'test') => {
    if (!selectedDataset) return;
    try {
      setEvaluating(true);
      const newRun = await apiService.runDatasetEvaluation(selectedDataset.id, split);
      setRuns([newRun, ...runs]);
      setSelectedRun(newRun);
      setActiveTab('runs');
    } catch (err: any) {
      alert(`Error al ejecutar evaluación: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setEvaluating(false);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'pass':
      case 'approved':
      case 'completed':
      case 'active':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/60"><CheckCircle2 className="w-3 h-3" /> {status.toUpperCase()}</span>;
      case 'warning':
      case 'in_progress':
      case 'running':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-400 border border-amber-800/60"><AlertTriangle className="w-3 h-3" /> {status.toUpperCase()}</span>;
      case 'fail':
      case 'rejected':
      case 'failed':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/60 text-rose-400 border border-rose-800/60"><XCircle className="w-3 h-3" /> {status.toUpperCase()}</span>;
      case 'frozen':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-cyan-950/60 text-cyan-400 border border-cyan-800/60"><Lock className="w-3 h-3" /> FROZEN (SNAPSHOT)</span>;
      case 'insufficient_sample':
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-300 border border-zinc-700">INSUFFICIENT N</span>;
      default:
        return <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-zinc-800 text-zinc-400 border border-zinc-700">{status.toUpperCase()}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-zinc-900/80 p-6 rounded-2xl border border-zinc-800 backdrop-blur-md">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 rounded-xl">
              <Award className="w-6 h-6 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Golden Dataset & Evaluación de Calidad</h1>
              <p className="text-sm text-zinc-400">
                Benchmarking reproducible y calibración de confianza perceptual y decisional (Fase 3 - Línea 2)
              </p>
            </div>
          </div>
        </div>

        {selectedDataset && (
          <div className="flex items-center gap-3">
            {selectedDataset.status !== 'frozen' && (
              <button
                onClick={handleFreezeDataset}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-sm font-semibold rounded-xl border border-zinc-700 transition"
                title="Congelar snapshot inmutable SHA-256"
              >
                <Lock className="w-4 h-4 text-cyan-400" /> Congelar Dataset
              </button>
            )}
            <button
              onClick={() => handleRunEvaluation('test')}
              disabled={evaluating}
              className="flex items-center gap-2 px-5 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white text-sm font-semibold rounded-xl shadow-lg shadow-indigo-500/20 transition disabled:opacity-50"
            >
              {evaluating ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Ejecutar Evaluación Sandbox
            </button>
          </div>
        )}
      </div>

      {/* Tabs de Navegación */}
      <div className="flex gap-2 border-b border-zinc-800 pb-2">
        <button
          onClick={() => setActiveTab('datasets')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
            activeTab === 'datasets'
              ? 'bg-zinc-800 text-indigo-400 border border-zinc-700'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <Database className="w-4 h-4" /> Catálogo de Datasets ({datasets.length})
        </button>
        <button
          onClick={() => setActiveTab('runs')}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition ${
            activeTab === 'runs'
              ? 'bg-zinc-800 text-indigo-400 border border-zinc-700'
              : 'text-zinc-400 hover:text-zinc-200'
          }`}
        >
          <BarChart3 className="w-4 h-4" /> Scorecards & Corridas ({runs.length})
        </button>
      </div>

      {/* Vista 1: Catálogo de Datasets */}
      {activeTab === 'datasets' && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-1 space-y-3">
            <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Datasets Disponibles</h3>
            {datasets.map((ds) => (
              <div
                key={ds.id}
                onClick={() => selectDataset(ds)}
                className={`p-4 rounded-xl border cursor-pointer transition ${
                  selectedDataset?.id === ds.id
                    ? 'bg-indigo-950/20 border-indigo-500/50 shadow-md shadow-indigo-500/10'
                    : 'bg-zinc-900/60 border-zinc-800 hover:border-zinc-700'
                }`}
              >
                <div className="flex items-start justify-between">
                  <h4 className="font-semibold text-zinc-200 text-sm">{ds.name}</h4>
                  {getStatusBadge(ds.status)}
                </div>
                <p className="text-xs text-zinc-400 mt-1 line-clamp-2">{ds.description || 'Sin descripción.'}</p>
                <div className="flex items-center gap-4 mt-3 text-xs text-zinc-400">
                  <span className="capitalize">🏛 {ds.discipline}</span>
                  <span>📦 v{ds.version}</span>
                  <span className="capitalize">🛡 {ds.source_policy}</span>
                </div>
              </div>
            ))}
          </div>

          {/* Detalle del Dataset Seleccionado */}
          <div className="md:col-span-2">
            {selectedDataset ? (
              <div className="bg-zinc-900/60 border border-zinc-800 rounded-2xl p-6 space-y-6">
                <div>
                  <div className="flex items-center justify-between">
                    <h2 className="text-xl font-bold text-zinc-100">{selectedDataset.name}</h2>
                    {getStatusBadge(selectedDataset.status)}
                  </div>
                  <p className="text-sm text-zinc-400 mt-1">{selectedDataset.description}</p>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800">
                    <span className="text-xs text-zinc-400">Disciplina</span>
                    <p className="text-sm font-semibold text-zinc-200 capitalize">{selectedDataset.discipline}</p>
                  </div>
                  <div className="bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800">
                    <span className="text-xs text-zinc-400">Tipo de Dataset</span>
                    <p className="text-sm font-semibold text-zinc-200 capitalize">{selectedDataset.dataset_type}</p>
                  </div>
                  <div className="bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800">
                    <span className="text-xs text-zinc-400">Política de Origen</span>
                    <p className="text-sm font-semibold text-zinc-200 capitalize">{selectedDataset.source_policy}</p>
                  </div>
                  <div className="bg-zinc-950/50 p-3.5 rounded-xl border border-zinc-800">
                    <span className="text-xs text-zinc-400">Muestras Totales</span>
                    <p className="text-sm font-semibold text-indigo-400">{selectedDataset.samples_count || 0}</p>
                  </div>
                </div>

                {selectedDataset.snapshot_manifest_hash && (
                  <div className="p-4 bg-cyan-950/20 border border-cyan-800/40 rounded-xl space-y-1">
                    <div className="flex items-center gap-2 text-cyan-400 text-xs font-semibold uppercase tracking-wider">
                      <ShieldCheck className="w-4 h-4" /> Snapshot SHA-256 Inmutable
                    </div>
                    <code className="text-xs text-cyan-200 break-all font-mono">
                      {selectedDataset.snapshot_manifest_hash}
                    </code>
                  </div>
                )}

                <div className="border-t border-zinc-800 pt-4 flex items-center justify-between">
                  <span className="text-xs text-zinc-400">Creado por: {selectedDataset.created_by}</span>
                  <span className="text-xs text-zinc-400">Actualizado: {new Date(selectedDataset.updated_at).toLocaleString()}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-zinc-400">Selecciona un dataset para ver su detalle.</div>
            )}
          </div>
        </div>
      )}

      {/* Vista 2: Scorecards & Corridas */}
      {activeTab === 'runs' && (
        <div className="space-y-6">
          {runs.length === 0 ? (
            <div className="text-center py-12 bg-zinc-900/40 border border-zinc-800 rounded-2xl">
              <BarChart3 className="w-12 h-12 text-zinc-400 mx-auto mb-3" />
              <h3 className="text-base font-semibold text-zinc-200">No hay corridas de evaluación registradas</h3>
              <p className="text-sm text-zinc-400 mt-1">Ejecuta una evaluación en sandbox para generar scorecards reproducibles.</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Selector de Corrida */}
              <div className="flex items-center gap-3 overflow-x-auto pb-2">
                {runs.map((r) => (
                  <button
                    key={r.id}
                    onClick={() => setSelectedRun(r)}
                    className={`px-4 py-2.5 rounded-xl text-left border transition whitespace-nowrap ${
                      selectedRun?.id === r.id
                        ? 'bg-zinc-800 border-indigo-500/50 shadow-md'
                        : 'bg-zinc-900/60 border-zinc-800 hover:border-zinc-700'
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-semibold text-zinc-200">Run: {r.id.substring(0, 8)}</span>
                      {getStatusBadge(r.summary?.quality_gate_verdict || r.status)}
                    </div>
                    <span className="text-[10px] text-zinc-400 block mt-0.5">
                      {new Date(r.created_at).toLocaleString()} (Split: {r.split_evaluated})
                    </span>
                  </button>
                ))}
              </div>

              {/* Scorecard de la Corrida Seleccionada */}
              {selectedRun && selectedRun.summary && (
                <div className="space-y-6">
                  {/* Quality Gate Overview */}
                  <div className="p-6 bg-gradient-to-br from-zinc-900/90 to-zinc-950/90 border border-zinc-800 rounded-2xl backdrop-blur-md space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">Veredicto General de Calidad</span>
                        <div className="flex items-center gap-3 mt-1">
                          <h2 className="text-2xl font-bold text-zinc-100">
                            Quality Gate: {selectedRun.summary.quality_gate_verdict?.toUpperCase()}
                          </h2>
                          {getStatusBadge(selectedRun.summary.quality_gate_verdict)}
                        </div>
                      </div>
                      <div className="text-right">
                        <span className="text-xs text-zinc-400">Muestras Evaluadas</span>
                        <p className="text-xl font-bold text-indigo-400">{selectedRun.summary.samples_evaluated_count}</p>
                      </div>
                    </div>

                    {/* Quality Gate Rules Evaluated */}
                    {selectedRun.summary.quality_gates?.gate_results && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2">
                        {selectedRun.summary.quality_gates.gate_results.map((g: any, i: number) => (
                          <div key={i} className="p-3 bg-zinc-950/60 border border-zinc-800/80 rounded-xl flex items-center justify-between text-xs">
                            <div>
                              <span className="font-semibold text-zinc-200 uppercase">{g.component}: {g.metric_name}</span>
                              <p className="text-[11px] text-zinc-400">{g.description}</p>
                            </div>
                            <div className="text-right">
                              {getStatusBadge(g.status)}
                              <span className="text-[10px] text-zinc-400 block mt-1">Obs: {g.observed_value} / Obj: {g.threshold}</span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* SECCIÓN 1: EVALUACIÓN PERCEPTUAL */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-zinc-200 font-bold text-base">
                      <Layers className="w-5 h-5 text-cyan-400" />
                      <h3>Scorecard Perceptual (OCR, Layout, Viñetas, Tablas, Símbolos)</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      {/* OCR Scorecard */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">OCR Espacial</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.perceptual_metrics?.ocr?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">CER (Char Error):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.ocr?.cer}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">WER (Word Error):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.ocr?.wer}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">F1 Textos Críticos:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.perceptual_metrics?.ocr?.critical_f1}</span></div>
                        </div>
                      </div>

                      {/* Layout Scorecard */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Layout Macro-Regional</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.perceptual_metrics?.layout?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Mean IoU (mIoU):</span> <span className="font-mono text-emerald-400 font-semibold">{selectedRun.summary.perceptual_metrics?.layout?.mean_iou}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Drawing Area IoU:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.layout?.by_region_iou?.drawing_area || '1.0'}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Title Block IoU:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.layout?.by_region_iou?.title_block || '1.0'}</span></div>
                        </div>
                      </div>

                      {/* Title Block Scorecard */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Viñetas / Title Block</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.perceptual_metrics?.title_block?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Exact Match Ratio:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.title_block?.exact_match_ratio}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Normalized Accuracy:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.title_block?.normalized_accuracy}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Completitud Requerida:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.perceptual_metrics?.title_block?.required_completeness}</span></div>
                        </div>
                      </div>

                      {/* Tables Scorecard */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Extracción Tabular</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.perceptual_metrics?.tables?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Table Detection IoU:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.tables?.table_detection_iou}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Exactitud de Celdas:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.perceptual_metrics?.tables?.cell_accuracy}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Exactitud Encabezados:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.tables?.header_accuracy}</span></div>
                        </div>
                      </div>

                      {/* Symbols Scorecard */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Símbolos Técnicos</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.perceptual_metrics?.symbols?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Precisión / Recall:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.symbols?.precision} / {selectedRun.summary.perceptual_metrics?.symbols?.recall}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">F1 Score:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.perceptual_metrics?.symbols?.f1_score}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Count Error (MAE):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.perceptual_metrics?.symbols?.count_mae}</span></div>
                          {selectedRun.summary.perceptual_metrics?.symbols?.map_50 !== undefined && (
                            <div className="flex justify-between"><span className="text-zinc-400">mAP@0.50:</span> <span className="font-mono text-cyan-400">{selectedRun.summary.perceptual_metrics?.symbols?.map_50}</span></div>
                          )}
                        </div>

                        {/* Desglose por Clase */}
                        {selectedRun.summary.perceptual_metrics?.symbols?.by_class_metrics && Object.keys(selectedRun.summary.perceptual_metrics.symbols.by_class_metrics).length > 0 && (
                          <div className="pt-2 border-t border-zinc-800 space-y-1">
                            <span className="text-[10px] font-semibold text-zinc-400 uppercase tracking-wider block">Desglose por Clase</span>
                            <div className="space-y-1 max-h-32 overflow-y-auto">
                              {Object.entries(selectedRun.summary.perceptual_metrics.symbols.by_class_metrics).map(([cName, cM]: [string, any]) => (
                                <div key={cName} className="p-1.5 bg-zinc-950/60 rounded border border-zinc-800 flex items-center justify-between text-[10px]">
                                  <span className="font-semibold text-zinc-300 truncate max-w-[90px]">{cName}</span>
                                  <span className="text-zinc-400 font-mono">F1: <span className="text-emerald-400">{cM.f1_score}</span> | P:{cM.precision} | R:{cM.recall}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  </div>

                  {/* SECCIÓN 2: EVALUACIÓN DECISIONAL */}
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-zinc-200 font-bold text-base">
                      <Sparkles className="w-5 h-5 text-amber-400" />
                      <h3>Scorecard Decisional (Reglas QA/QC, Matriz de Confusión & HITL)</h3>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {/* Reglas QA/QC */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Motor de Reglas QA/QC</span>
                          <span className="text-xs text-zinc-400">N={selectedRun.summary.decisional_metrics?.rules?.sample_count}</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Precisión / Recall / F1:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.decisional_metrics?.rules?.precision} / {selectedRun.summary.decisional_metrics?.rules?.recall} / {selectedRun.summary.decisional_metrics?.rules?.f1_score}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">False Positive Rate (FPR):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.decisional_metrics?.rules?.fpr}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">False Negative Rate (FNR):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.decisional_metrics?.rules?.fnr}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Exactitud de Severidad:</span> <span className="font-mono text-zinc-200">{selectedRun.summary.decisional_metrics?.rules?.severity_accuracy}</span></div>
                        </div>

                        {/* Matriz de Confusión */}
                        {selectedRun.summary.decisional_metrics?.rules?.confusion_matrix && (
                          <div className="pt-2 border-t border-zinc-800">
                            <span className="text-[11px] font-semibold text-zinc-400 block mb-1.5">Matriz de Confusión (Hallazgos)</span>
                            <div className="grid grid-cols-2 gap-2 text-center text-xs">
                              <div className="p-2 bg-emerald-950/30 border border-emerald-800/40 rounded-lg">
                                <span className="text-[10px] text-zinc-400 block">True Positives</span>
                                <span className="font-bold text-emerald-400">{selectedRun.summary.decisional_metrics.rules.confusion_matrix.true_positive}</span>
                              </div>
                              <div className="p-2 bg-rose-950/30 border border-rose-800/40 rounded-lg">
                                <span className="text-[10px] text-zinc-400 block">False Positives</span>
                                <span className="font-bold text-rose-400">{selectedRun.summary.decisional_metrics.rules.confusion_matrix.false_positive}</span>
                              </div>
                              <div className="p-2 bg-rose-950/30 border border-rose-800/40 rounded-lg">
                                <span className="text-[10px] text-zinc-400 block">False Negatives</span>
                                <span className="font-bold text-rose-400">{selectedRun.summary.decisional_metrics.rules.confusion_matrix.false_negative}</span>
                              </div>
                              <div className="p-2 bg-emerald-950/30 border border-emerald-800/40 rounded-lg">
                                <span className="text-[10px] text-zinc-400 block">True Negatives</span>
                                <span className="font-bold text-emerald-400">{selectedRun.summary.decisional_metrics.rules.confusion_matrix.true_negative}</span>
                              </div>
                            </div>
                          </div>
                        )}
                      </div>

                      {/* HITL & Intervención Humana */}
                      <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 space-y-3">
                        <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
                          <span className="text-xs font-bold text-zinc-300">Calibración HITL / Humano</span>
                          <span className="text-xs text-zinc-400">Resoluciones</span>
                        </div>
                        <div className="space-y-1.5 text-xs">
                          <div className="flex justify-between"><span className="text-zinc-400">Tasa Confirmación:</span> <span className="font-mono text-emerald-400">{selectedRun.summary.decisional_metrics?.hitl?.confirmation_rate}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Tasa Descarte (Dismissed):</span> <span className="font-mono text-zinc-200">{selectedRun.summary.decisional_metrics?.hitl?.dismissed_rate}</span></div>
                          <div className="flex justify-between"><span className="text-zinc-400">Desacuerdo Regla / Auditor:</span> <span className="font-mono text-amber-400">{selectedRun.summary.decisional_metrics?.hitl?.disagreement_rate}</span></div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
