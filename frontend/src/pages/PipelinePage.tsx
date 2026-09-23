import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiService } from '../services/api';
import { useProject } from '../context/ProjectContext';
import {
  Project,
  ReviewDisciplineItem,
  ReviewTopicItem,
  ReviewPlanResponse,
  ReviewRunDetailResponse
} from '../types';
import {
  Play, RefreshCw, CheckCircle2, XCircle, AlertTriangle, HelpCircle,
  FileText, ShieldCheck, Download, ExternalLink, Clock, Folder,
  FileSpreadsheet, FileCode, CheckSquare, Square, Eye, Sparkles
} from 'lucide-react';

export const PipelinePage: React.FC = () => {
  const navigate = useNavigate();
  const { projects, activeProject, activeProjectId, setActiveProjectId } = useProject();

  // Taxonomía
  const [disciplines, setDisciplines] = useState<ReviewDisciplineItem[]>([]);
  const [selectedDiscipline, setSelectedDiscipline] = useState<string>('PIPING');
  const [topics, setTopics] = useState<ReviewTopicItem[]>([]);
  const [selectedTopic, setSelectedTopic] = useState<string>('PID_SYMBOLS');

  // Modo de Ejecución
  const [mode, setMode] = useState<'production' | 'sandbox'>('production');

  // Documentos
  const [documents, setDocuments] = useState<Array<{ id: string; filename: string }>>([]);
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Plan Pre-Flight
  const [plan, setPlan] = useState<ReviewPlanResponse | null>(null);
  const [loadingPlan, setLoadingPlan] = useState<boolean>(false);

  // Ejecución activa y detalles
  const [running, setRunning] = useState<boolean>(false);
  const [activeRun, setActiveRun] = useState<ReviewRunDetailResponse | null>(null);

  // Historial de Corridas
  const [historyRuns, setHistoryRuns] = useState<ReviewRunDetailResponse[]>([]);

  // Exportaciones
  const [exportingFormat, setExportingFormat] = useState<string | null>(null);
  const [lastExport, setLastExport] = useState<{ id: string; format: string; sha256: string; url: string } | null>(null);

  // Estado general de carga inicial
  const [initialLoading, setInitialLoading] = useState<boolean>(true);

  // 1. Cargar disciplinas al inicio
  useEffect(() => {
    initData();
  }, []);

  const initData = async () => {
    setInitialLoading(true);
    try {
      const discs = await apiService.getReviewDisciplines(true);
      setDisciplines(discs);

      // Priorizar PIPING si existe
      const pipingDisc = discs.find(d => d.code === 'PIPING');
      if (pipingDisc) {
        setSelectedDiscipline('PIPING');
      } else if (discs.length > 0) {
        setSelectedDiscipline(discs[0].code);
      }
    } catch (e) {
      console.error('Error inicializando PipelinePage:', e);
    } finally {
      setInitialLoading(false);
    }
  };


  // 2. Cargar documentos e historial cuando cambia el proyecto activo
  useEffect(() => {
    if (!activeProjectId) return;
    loadProjectDocuments(activeProjectId);
    loadHistoryRuns(activeProjectId);
  }, [activeProjectId]);

  const loadProjectDocuments = async (projId: string) => {
    try {
      const docs = await apiService.getProjectDocuments(projId);
      const mapped = docs.map((d: any) => ({ id: d.id, filename: d.filename }));
      setDocuments(mapped);
      // Por defecto seleccionar todos los documentos del proyecto
      setSelectedDocIds(mapped.map((d: any) => d.id));
    } catch (e) {
      console.error('Error cargando documentos del proyecto:', e);
      setDocuments([]);
      setSelectedDocIds([]);
    }
  };

  const loadHistoryRuns = async (projId: string) => {
    try {
      const runs = await apiService.listReviewRuns(projId);
      setHistoryRuns(runs);
      if (runs.length > 0 && !activeRun) {
        setActiveRun(runs[0]);
      }
    } catch (e) {
      console.error('Error cargando historial de revisiones:', e);
      setHistoryRuns([]);
    }
  };

  // 3. Cargar temas cuando cambia la disciplina
  useEffect(() => {
    if (!selectedDiscipline) return;
    loadTopics(selectedDiscipline);
  }, [selectedDiscipline]);

  const loadTopics = async (discCode: string) => {
    try {
      const tops = await apiService.getReviewTopics(discCode, true);
      setTopics(tops);
      // Priorizar PID_SYMBOLS si está en la lista
      const pidSym = tops.find(t => t.code === 'PID_SYMBOLS');
      if (pidSym) {
        setSelectedTopic('PID_SYMBOLS');
      } else if (tops.length > 0) {
        setSelectedTopic(tops[0].code);
      }
    } catch (e) {
      console.error('Error cargando temas:', e);
      setTopics([]);
    }
  };

  // 4. Calcular pre-flight plan cuando cambia proyecto, disciplina, tema, selección o modo
  useEffect(() => {
    if (!activeProjectId || !selectedDiscipline || !selectedTopic) return;
    fetchPlan();
  }, [activeProjectId, selectedDiscipline, selectedTopic, selectedDocIds, mode]);

  const fetchPlan = async () => {
    setLoadingPlan(true);
    try {
      const p = await apiService.getReviewPlan({
        project_id: activeProjectId,
        discipline_code: selectedDiscipline,
        topic_code: selectedTopic,
        document_ids: selectedDocIds,
        mode: mode
      });
      setPlan(p);
    } catch (e) {
      console.error('Error generando plan:', e);
      setPlan(null);
    } finally {
      setLoadingPlan(false);
    }
  };

  // Manejador de selección de documentos
  const toggleDoc = (docId: string) => {
    setSelectedDocIds(prev =>
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    );
  };

  const toggleAllDocs = () => {
    if (selectedDocIds.length === documents.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(documents.map(d => d.id));
    }
  };

  // Ejecución de la revisión
  const handleExecuteReview = async () => {
    if (!plan || !plan.can_execute || running) return;

    setRunning(true);
    setLastExport(null);
    try {
      const res = await apiService.executeReviewRun({
        project_id: activeProjectId,
        discipline_code: selectedDiscipline,
        topic_code: selectedTopic,
        document_ids: selectedDocIds,
        mode: mode,
        run_name: `Revisión ${selectedDiscipline} - ${plan.topic_name} (${mode.toUpperCase()})`
      });

      // Recargar detalles de la corrida ejecutada
      const details = await apiService.getReviewRunDetails(res.review_run_id);
      setActiveRun(details);

      // Recargar historial
      loadHistoryRuns(activeProjectId);
    } catch (err: any) {
      console.error('Error ejecutando revisión:', err);
      alert(err.response?.data?.detail || 'Error al ejecutar la revisión.');
    } finally {
      setRunning(false);
    }
  };

  // Generar exportación persistida
  const handleCreateExport = async (format: 'json' | 'xlsx' | 'pdf') => {
    if (!activeRun) return;
    setExportingFormat(format);
    try {
      const rep = await apiService.createReviewExport(activeRun.id, format);
      const downloadUrl = apiService.downloadReviewReportUrl(rep.id);
      setLastExport({
        id: rep.id,
        format: rep.format,
        sha256: rep.sha256,
        url: downloadUrl
      });
      // Abrir descarga automática
      window.open(downloadUrl, '_blank');
    } catch (err: any) {
      console.error('Error exportando reporte:', err);
      alert(err.response?.data?.detail || 'Error al generar exportación.');
    } finally {
      setExportingFormat(null);
    }
  };

  const currentProject = useMemo(() => {
    return projects.find(p => p.id === activeProjectId);
  }, [projects, activeProjectId]);

  if (initialLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-blue-600 animate-spin" />
          <p className="text-sm font-medium text-slate-600 dark:text-slate-400">
            Cargando taxonomía y configuración de auditoría...
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-[1600px] mx-auto space-y-6">
      {/* Header Principal */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800 pb-5">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-slate-900 dark:text-white tracking-tight">
              One-Click Review por Especialidad y Punto de Revisión
            </h1>
            <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 border border-blue-200 dark:border-blue-800">
              Orquestador QA/QC v2.0
            </span>
          </div>
          <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
            Evaluación determinística y trazable por especialidad técnica, punto de control y documentos del proyecto.
          </p>
        </div>

        {/* Selector de Proyecto Activo */}
        <div className="flex items-center gap-3 bg-white dark:bg-slate-900 p-2 rounded-lg border border-slate-200 dark:border-slate-800 shadow-sm">
          <Folder className="w-4 h-4 text-blue-600 dark:text-blue-400 shrink-0 ml-1" />
          <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">Proyecto:</span>
          <select
            className="bg-transparent text-sm font-semibold text-slate-800 dark:text-slate-200 focus:outline-none cursor-pointer pr-2"
            value={activeProjectId}
            onChange={(e) => {
              setActiveProjectId(e.target.value);
              localStorage.setItem('active_project_id', e.target.value);
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id} className="dark:bg-slate-900">
                {p.code} - {p.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid de Configuración del Alcance de Revisión */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Panel Izquierdo: Configuración del Scope (4 cols) */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 shadow-sm space-y-5">
            <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
              <ShieldCheck className="w-5 h-5 text-blue-600" />
              1. Alcance de Evaluación
            </h2>

            {/* Selector de Especialidad */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
                Especialidad Técnica
              </label>
              <select
                className="w-full bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-sm font-medium text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={selectedDiscipline}
                onChange={(e) => setSelectedDiscipline(e.target.value)}
              >
                {disciplines.map((d) => (
                  <option key={d.id} value={d.code}>
                    {d.code === 'PIPING' ? '★ ' : ''}{d.name} ({d.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Selector de Punto de Revisión */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
                Punto de Revisión
              </label>
              <select
                className="w-full bg-slate-50 dark:bg-slate-800/80 border border-slate-300 dark:border-slate-700 rounded-lg p-2.5 text-sm font-medium text-slate-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:outline-none"
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
              >
                {topics.map((t) => (
                  <option key={t.id} value={t.code}>
                    {t.code === 'PID_SYMBOLS' ? '● ' : '○ '}
                    {t.name} {!t.enabled_mvp && t.code !== 'PID_SYMBOLS' ? '(Sin reglas aprobadas)' : ''}
                  </option>
                ))}
              </select>
            </div>

            {/* Toggle Modo: Producción vs Sandbox */}
            <div>
              <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
                Modo de Ejecución
              </label>
              <div className="grid grid-cols-2 gap-2 bg-slate-100 dark:bg-slate-800 p-1 rounded-lg">
                <button
                  type="button"
                  onClick={() => setMode('production')}
                  className={`py-2 text-xs font-bold rounded-md transition-all ${
                    mode === 'production'
                      ? 'bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm border border-slate-200 dark:border-slate-700'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  Producción
                </button>
                <button
                  type="button"
                  onClick={() => setMode('sandbox')}
                  className={`py-2 text-xs font-bold rounded-md transition-all ${
                    mode === 'sandbox'
                      ? 'bg-amber-500 text-white shadow-sm font-black'
                      : 'text-slate-600 dark:text-slate-400 hover:text-slate-900'
                  }`}
                >
                  Sandbox Exploratorio
                </button>
              </div>
              {mode === 'sandbox' && (
                <div className="mt-2 p-2.5 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <span>
                    <strong>Resultado exploratorio:</strong> no constituye validación productiva oficial ni modifica indicadores oficiales.
                  </span>
                </div>
              )}
            </div>

            {/* Selección de Documentos del Proyecto */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Documentos ({selectedDocIds.length}/{documents.length})
                </label>
                {documents.length > 0 && (
                  <button
                    type="button"
                    onClick={toggleAllDocs}
                    className="text-xs text-blue-600 dark:text-blue-400 hover:underline font-semibold"
                  >
                    {selectedDocIds.length === documents.length ? 'Deseleccionar todos' : 'Seleccionar todos'}
                  </button>
                )}
              </div>

              <div className="max-h-48 overflow-y-auto space-y-1.5 border border-slate-200 dark:border-slate-800 rounded-lg p-2 bg-slate-50 dark:bg-slate-950/40">
                {documents.length === 0 ? (
                  <p className="text-xs text-slate-500 italic p-2 text-center">
                    El proyecto no tiene documentos cargados.
                  </p>
                ) : (
                  documents.map((d) => {
                    const isSelected = selectedDocIds.includes(d.id);
                    return (
                      <div
                        key={d.id}
                        onClick={() => toggleDoc(d.id)}
                        className={`flex items-center gap-2 p-2 rounded text-xs cursor-pointer transition-colors ${
                          isSelected
                            ? 'bg-blue-50 dark:bg-blue-900/30 text-blue-900 dark:text-blue-200 font-medium'
                            : 'hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-700 dark:text-slate-300'
                        }`}
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-blue-600 shrink-0" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-400 shrink-0" />
                        )}
                        <span className="truncate">{d.filename}</span>
                      </div>
                    );
                  })
                )}
              </div>
            </div>

            {/* Botón de Ejecutar */}
            <div>
              <button
                type="button"
                onClick={handleExecuteReview}
                disabled={!plan?.can_execute || running}
                className={`w-full py-3 px-4 rounded-xl font-bold text-sm shadow-md transition-all flex items-center justify-center gap-2 ${
                  plan?.can_execute && !running
                    ? 'bg-blue-600 hover:bg-blue-700 text-white cursor-pointer active:scale-[0.99]'
                    : 'bg-slate-200 dark:bg-slate-800 text-slate-400 cursor-not-allowed'
                }`}
              >
                {running ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    <span>Ejecutando Orquestador (Fases 1-9)...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Ejecutar One-Click Review</span>
                  </>
                )}
              </button>

              {!plan?.can_execute && (
                <p className="text-xs text-center text-slate-500 dark:text-slate-400 mt-2 italic">
                  {plan?.empty_reason || 'Seleccione al menos un documento y un alcance con reglas aprobadas.'}
                </p>
              )}
            </div>
          </div>

          {/* Historial de Corridas Recientes */}
          <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-4 shadow-sm">
            <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-500" />
              Historial de Revisiones ({historyRuns.length})
            </h3>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {historyRuns.length === 0 ? (
                <p className="text-xs text-slate-500 italic text-center py-3">
                  Sin corridas previas en este proyecto.
                </p>
              ) : (
                historyRuns.map((r) => {
                  const isSelected = activeRun?.id === r.id;
                  return (
                    <div
                      key={r.id}
                      onClick={() => setActiveRun(r)}
                      className={`p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
                        isSelected
                          ? 'border-blue-500 bg-blue-50/50 dark:bg-blue-900/20'
                          : 'border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:hover:bg-slate-800/60'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-slate-900 dark:text-white truncate">
                          {r.run_name}
                        </span>
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                          r.status === 'completed'
                            ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300'
                            : 'bg-amber-100 text-amber-800'
                        }`}>
                          {r.status.toUpperCase()}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-slate-500 text-[11px] mt-1">
                        <span>{r.requested_at ? new Date(r.requested_at).toLocaleTimeString() : 'N/A'}</span>
                        <span className="font-semibold text-slate-700 dark:text-slate-300">
                          {r.findings_count} hallazgo(s)
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {/* Panel Derecho: Pre-flight Plan o Resultados de Ejecución (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {/* Si no hay corrida seleccionada o se está visualizando pre-flight plan */}
          {(!activeRun || running) && (
            <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-6">
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <Sparkles className="w-5 h-5 text-blue-600" />
                    Resumen Previo (Pre-Flight Review Plan)
                  </h2>
                  <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                    Plan topológico de evaluación estructurado para {selectedDiscipline} • {selectedTopic}
                  </p>
                </div>
                {loadingPlan && <RefreshCw className="w-4 h-4 text-blue-600 animate-spin" />}
              </div>

              {/* Estado Vacío Explicativo si no hay reglas aprobadas */}
              {plan && !plan.can_execute && (
                <div className="p-6 rounded-xl bg-slate-50 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 text-center space-y-3">
                  <HelpCircle className="w-10 h-10 text-slate-400 mx-auto" />
                  <h3 className="text-base font-bold text-slate-800 dark:text-slate-200">
                    No hay reglas aprobadas para este alcance
                  </h3>
                  <p className="text-sm text-slate-600 dark:text-slate-400 max-w-lg mx-auto">
                    El punto de revisión <strong>{selectedTopic}</strong> en la especialidad <strong>{selectedDiscipline}</strong> no cuenta con reglas activas aprobadas en producción.
                    Para el primer MVP, seleccione la especialidad <strong>PIPING</strong> y el punto <strong>PID_SYMBOLS</strong>.
                  </p>
                </div>
              )}

              {/* Plan con reglas aprobadas */}
              {plan && plan.can_execute && (
                <div className="space-y-6">
                  {/* Fases Blueprint */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-3">
                      Plan Topológico de Fases (1 a 9)
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                      {plan.phases_blueprint.map((p) => (
                        <div
                          key={p.phase}
                          className="p-3 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 space-y-1 text-xs"
                        >
                          <div className="flex items-center justify-between">
                            <span className="font-bold text-slate-900 dark:text-white">
                              Fase {p.phase}
                            </span>
                            <span className={`px-1.5 py-0.2 rounded text-[10px] uppercase font-bold ${
                              p.step_type === 'preparation' ? 'bg-blue-100 text-blue-800 dark:bg-blue-900/40' :
                              p.step_type === 'evaluation' ? 'bg-purple-100 text-purple-800 dark:bg-purple-900/40' :
                              'bg-slate-200 text-slate-700 dark:bg-slate-800'
                            }`}>
                              {p.step_type}
                            </span>
                          </div>
                          <p className="text-slate-600 dark:text-slate-400 font-medium truncate">
                            {p.phase_name}
                          </p>
                          <p className="text-slate-500 text-[11px]">
                            {p.rule_count > 0 ? `${p.rule_count} regla(s) QA/QC` : 'Preparación técnica'}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Reglas Aplicables */}
                  <div>
                    <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-3">
                      Reglas Aprobadas Aplicables ({plan.applicable_rules.length})
                    </h3>
                    <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
                      {plan.applicable_rules.map((r) => (
                        <div key={r.rule_id} className="p-3 bg-white dark:bg-slate-900 flex items-start justify-between gap-4 text-xs">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-900 dark:text-white">
                                {r.code}
                              </span>
                              <span className="text-slate-500">•</span>
                              <span className="text-slate-700 dark:text-slate-300 font-medium">
                                {r.name}
                              </span>
                            </div>
                            <p className="text-slate-500 text-[11px] leading-relaxed">
                              {r.description}
                            </p>
                            {r.rationale && (
                              <p className="text-blue-600 dark:text-blue-400 text-[11px] italic">
                                Justificación: {r.rationale}
                              </p>
                            )}
                          </div>
                          <div className="shrink-0 flex flex-col items-end gap-1">
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                              FASE {r.execution_phase}
                            </span>
                            <span className="text-[10px] text-slate-400">
                              Prioridad: {r.priority}
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Documentos Requeridos Faltantes si aplica */}
                  {plan.missing_required_document_types.length > 0 && (
                    <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-800 space-y-2">
                      <h4 className="text-xs font-bold text-amber-900 dark:text-amber-200 uppercase tracking-wider flex items-center gap-1.5">
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                        Documentos Requeridos Faltantes
                      </h4>
                      {plan.missing_required_document_types.map((m, idx) => (
                        <div key={idx} className="text-xs text-amber-800 dark:text-amber-300 space-y-0.5">
                          <p className="font-semibold">• Tipo {m.document_type}: {m.reason}</p>
                          <p className="text-amber-700 dark:text-amber-400 text-[11px]">Acción recomendada: {m.recommended_action}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Resultados de la Corrida Activa */}
          {activeRun && !running && (
            <div className="space-y-6">
              {/* Tarjeta de Resumen y KPIs de la Corrida */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200 dark:border-slate-800 pb-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold text-slate-900 dark:text-white">
                        {activeRun.run_name}
                      </h2>
                      <span className="px-2.5 py-0.5 text-xs font-bold rounded-full bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300">
                        {activeRun.status.toUpperCase()}
                      </span>
                    </div>
                    <p className="text-xs text-slate-500 mt-1">
                      Ejecutado por {activeRun.requested_by} • Duración: {activeRun.execution_time_sec}s • {activeRun.rule_count} reglas evaluadas
                    </p>
                  </div>

                  {/* Botones de Exportación Persistida */}
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => handleCreateExport('json')}
                      disabled={exportingFormat !== null}
                      className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-1.5 transition-colors"
                    >
                      <FileCode className="w-3.5 h-3.5 text-blue-600" />
                      JSON
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreateExport('xlsx')}
                      disabled={exportingFormat !== null}
                      className="px-3 py-1.5 rounded-lg border border-slate-300 dark:border-slate-700 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-800 flex items-center gap-1.5 transition-colors"
                    >
                      <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                      XLSX
                    </button>
                    <button
                      type="button"
                      onClick={() => handleCreateExport('pdf')}
                      disabled={exportingFormat !== null}
                      className="px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      Descargar PDF
                    </button>
                  </div>
                </div>

                {/* Banner de Hash de Exportación Reciente */}
                {lastExport && (
                  <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-300 dark:border-emerald-800 flex items-center justify-between text-xs text-emerald-900 dark:text-emerald-200">
                    <div className="flex items-center gap-2 truncate">
                      <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                      <span className="font-semibold">Reporte persistido ({lastExport.format.toUpperCase()}):</span>
                      <code className="text-[11px] font-mono text-emerald-700 dark:text-emerald-300 truncate">
                        SHA256: {lastExport.sha256}
                      </code>
                    </div>
                    <a
                      href={lastExport.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-emerald-700 dark:text-emerald-300 hover:underline font-bold shrink-0 ml-2 flex items-center gap-1"
                    >
                      <Download className="w-3 h-3" />
                      Descargar
                    </a>
                  </div>
                )}

                {/* Tarjetas de Métricas / KPIs */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20">
                    <div className="flex items-center justify-between text-emerald-700 dark:text-emerald-300">
                      <span className="text-xs font-bold uppercase">Cumple (Passed)</span>
                      <CheckCircle2 className="w-4 h-4" />
                    </div>
                    <p className="text-2xl font-black text-emerald-900 dark:text-emerald-100 mt-2">
                      {activeRun.summary_stats.passed || 0}
                    </p>
                  </div>

                  <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20">
                    <div className="flex items-center justify-between text-rose-700 dark:text-rose-300">
                      <span className="text-xs font-bold uppercase">No Cumple (Failed)</span>
                      <XCircle className="w-4 h-4" />
                    </div>
                    <p className="text-2xl font-black text-rose-900 dark:text-rose-100 mt-2">
                      {activeRun.summary_stats.failed || 0}
                    </p>
                  </div>

                  <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20">
                    <div className="flex items-center justify-between text-amber-700 dark:text-amber-300">
                      <span className="text-xs font-bold uppercase">Advertencias</span>
                      <AlertTriangle className="w-4 h-4" />
                    </div>
                    <p className="text-2xl font-black text-amber-900 dark:text-amber-100 mt-2">
                      {activeRun.summary_stats.warning || 0}
                    </p>
                  </div>

                  <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40">
                    <div className="flex items-center justify-between text-slate-600 dark:text-slate-400">
                      <span className="text-xs font-bold uppercase">No Evaluable</span>
                      <HelpCircle className="w-4 h-4" />
                    </div>
                    <p className="text-2xl font-black text-slate-800 dark:text-slate-200 mt-2">
                      {activeRun.summary_stats.not_evaluable || 0}
                    </p>
                  </div>
                </div>

                {/* Barra de Fases 1 a 9 */}
                <div>
                  <h3 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider mb-2">
                    Progreso de Fases de Orquestación
                  </h3>
                  <div className="grid grid-cols-9 gap-1.5">
                    {activeRun.steps.map((s) => {
                      const isSucc = s.status === 'succeeded';
                      const isSkip = s.status === 'skipped';
                      return (
                        <div
                          key={s.phase}
                          title={`Fase ${s.phase}: ${s.phase_name} (${s.status})`}
                          className={`p-2 rounded text-center text-[10px] font-bold border ${
                            isSucc
                              ? 'bg-emerald-500 text-white border-emerald-600'
                              : isSkip
                              ? 'bg-slate-200 dark:bg-slate-800 text-slate-400 border-slate-300 dark:border-slate-700'
                              : 'bg-rose-500 text-white border-rose-600'
                          }`}
                        >
                          F{s.phase}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Evaluación de Reglas y Not Evaluable Estructurado */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-4">
                <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-blue-600" />
                  Evaluaciones Individuales de Reglas ({activeRun.executions.length})
                </h3>

                <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden">
                  {activeRun.executions.map((ex) => {
                    const st = ex.status.toLowerCase();
                    return (
                      <div key={ex.id} className="p-4 bg-white dark:bg-slate-900 space-y-2">
                        <div className="flex items-center justify-between text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-slate-900 dark:text-white">
                              {ex.rule_code}
                            </span>
                            <span className="text-slate-400">•</span>
                            <span className="text-slate-700 dark:text-slate-300 font-medium">
                              {ex.rule_name}
                            </span>
                          </div>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            st === 'passed' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' :
                            st === 'failed' ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300' :
                            st === 'warning' ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' :
                            'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                          }`}>
                            {ex.status.toUpperCase()}
                          </span>
                        </div>

                        {/* Razón Estructurada de Not Evaluable */}
                        {ex.not_evaluable_reason_code && (
                          <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200 dark:border-slate-700 space-y-1 text-xs">
                            <div className="flex items-center gap-2">
                              <span className="font-bold text-slate-800 dark:text-slate-200">
                                Código de Causa:
                              </span>
                              <code className="px-1.5 py-0.5 bg-slate-200 dark:bg-slate-700 rounded text-[11px] font-mono font-bold text-slate-900 dark:text-white">
                                {ex.not_evaluable_reason_code}
                              </code>
                            </div>
                            <p className="text-slate-600 dark:text-slate-400">
                              {ex.not_evaluable_reason_message}
                            </p>
                            {ex.recommended_action && (
                              <p className="text-blue-600 dark:text-blue-400 font-medium">
                                Acción recomendada: {ex.recommended_action}
                              </p>
                            )}
                          </div>
                        )}

                        {/* Resumen del Resultado */}
                        {ex.result_summary && !ex.not_evaluable_reason_code && (
                          <p className="text-xs text-slate-600 dark:text-slate-400">
                            {ex.result_summary.description || ex.result_summary.title}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Hallazgos Técnicos QA/QC */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-6 shadow-sm space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                    Hallazgos Técnicos Registrados ({activeRun.findings.length})
                  </h3>
                </div>

                {activeRun.findings.length === 0 ? (
                  <div className="p-8 text-center bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-lg">
                    <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                    <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                      No se registraron discrepancias en esta corrida de revisión.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {activeRun.findings.map((f) => {
                      const isCrit = f.severity === 'critical';
                      const isHigh = f.severity === 'high';
                      return (
                        <div
                          key={f.id}
                          className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2 hover:shadow-md transition-shadow"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-center gap-2 text-xs">
                              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                isCrit ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300' :
                                isHigh ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' :
                                'bg-blue-100 text-blue-800'
                              }`}>
                                {f.severity.toUpperCase()}
                              </span>
                              <span className="font-mono text-slate-500 font-bold">
                                {f.rule_code}
                              </span>
                              <span className="text-slate-400">•</span>
                              <span className="font-bold text-slate-900 dark:text-white">
                                {f.title}
                              </span>
                            </div>

                            {/* Botón para navegar al visor con contexto */}
                            {f.navigation_context?.document_id && (
                              <button
                                type="button"
                                onClick={() => {
                                  navigate(`/viewer?document_id=${f.navigation_context?.document_id}`);
                                }}
                                className="px-2.5 py-1 text-xs font-semibold rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 flex items-center gap-1 transition-colors shrink-0"
                              >
                                <Eye className="w-3.5 h-3.5 text-blue-600" />
                                Visor
                              </button>
                            )}
                          </div>

                          <p className="text-xs text-slate-600 dark:text-slate-300">
                            {f.description}
                          </p>

                          {f.recommendation && (
                            <div className="p-2.5 rounded bg-blue-50/50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 text-xs text-blue-900 dark:text-blue-200">
                              <strong>Recomendación:</strong> {f.recommendation}
                            </div>
                          )}

                          {f.bbox && (
                            <p className="text-[11px] font-mono text-slate-400">
                              Coordenadas BBox: [{f.bbox.map((v: number) => typeof v === 'number' ? v.toFixed(1) : v).join(', ')}]
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
