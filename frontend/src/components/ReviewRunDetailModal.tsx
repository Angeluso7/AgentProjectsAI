import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileText,
  FileSpreadsheet,
  Download,
  Eye,
  Clock,
  Layers,
  Sparkles,
  RefreshCw,
  FolderGit2,
  Copy,
  Check
} from 'lucide-react';
import { ReviewRunDetailResponse, ReviewFindingDetail, ReviewReportItem } from '../types';
import { apiService } from '../services/api';

interface ReviewRunDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  run: ReviewRunDetailResponse | null;
  projectName?: string;
  onNavigateContext?: (finding: ReviewFindingDetail) => void;
  onRefreshRun?: () => void;
}

type TabType = 'overview' | 'phases' | 'rules' | 'findings' | 'exports';

export const ReviewRunDetailModal: React.FC<ReviewRunDetailModalProps> = ({
  isOpen,
  onClose,
  run,
  projectName,
  onNavigateContext,
  onRefreshRun
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [generatingFormat, setGeneratingFormat] = useState<'json' | 'xlsx' | 'pdf' | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'info' | 'success' | 'error' } | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  if (!isOpen || !run) return null;

  const isSandbox = run.execution_mode === 'sandbox';

  const handleDownload = async (reportId: string, format: string) => {
    setDownloadingId(reportId);
    setStatusMessage({ text: 'Preparando descarga autenticada...', type: 'info' });
    try {
      const { filename, size } = await apiService.downloadReviewReport(reportId);
      setStatusMessage({
        text: `Descarga completada: ${filename} (${(size / 1024).toFixed(1)} KB)`,
        type: 'success'
      });
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      console.error('Error en descarga autenticada:', err);
      setStatusMessage({
        text: err?.message || 'Error al descargar el reporte.',
        type: 'error'
      });
    } finally {
      setDownloadingId(null);
    }
  };

  const handleCreateAndDownloadExport = async (format: 'json' | 'xlsx' | 'pdf') => {
    setGeneratingFormat(format);
    setStatusMessage({ text: `Generando y persistiendo reporte ${format.toUpperCase()}...`, type: 'info' });
    try {
      const rep = await apiService.createReviewExport(run.id, format);
      setStatusMessage({ text: `Descargando reporte ${format.toUpperCase()}...`, type: 'info' });
      const { filename } = await apiService.downloadReviewReport(rep.id);
      setStatusMessage({
        text: `Reporte ${format.toUpperCase()} generado y descargado: ${filename}`,
        type: 'success'
      });
      if (onRefreshRun) onRefreshRun();
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      console.error('Error generando exportación:', err);
      setStatusMessage({
        text: err?.message || 'Error al generar o descargar el reporte.',
        type: 'error'
      });
    } finally {
      setGeneratingFormat(null);
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedHash(text);
    setTimeout(() => setCopiedHash(null), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Encabezado Principal */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-start justify-between bg-slate-50/50 dark:bg-slate-950/40">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider ${
                isSandbox
                  ? 'bg-amber-100 text-amber-900 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300 dark:border-amber-800'
                  : 'bg-emerald-100 text-emerald-900 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800'
              }`}>
                {run.execution_mode.toUpperCase()}
              </span>
              <span className="text-xs font-semibold text-slate-500 dark:text-slate-400">
                {projectName || run.project_id}
              </span>
              <span className="text-slate-400">•</span>
              <span className="text-xs font-bold text-blue-600 dark:text-blue-400">
                {run.discipline_name} ({run.discipline_code})
              </span>
              <span className="text-slate-400">•</span>
              <span className="text-xs font-medium text-slate-700 dark:text-slate-300">
                {run.topic_name}
              </span>
            </div>
            <h2 className="text-xl font-bold text-slate-900 dark:text-white flex items-center gap-2">
              {run.run_name}
            </h2>
            <div className="flex items-center gap-4 text-xs text-slate-500 dark:text-slate-400">
              <span className="flex items-center gap-1">
                <Clock className="w-3.5 h-3.5 text-slate-400" />
                {run.requested_at ? new Date(run.requested_at).toLocaleString() : 'N/A'}
              </span>
              <span>Duración: <strong>{run.execution_time_sec.toFixed(2)}s</strong></span>
              <span>Solicitado por: <strong>{run.requested_by}</strong></span>
              {run.baseline_catalog_version && (
                <span className="truncate max-w-xs" title={run.baseline_catalog_version}>
                  Línea base: <strong>{run.baseline_catalog_version}</strong>
                </span>
              )}
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
            title="Cerrar ventana"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Banner Fijo de Modo Sandbox */}
        {isSandbox && (
          <div className="px-6 py-2.5 bg-amber-50 dark:bg-amber-950/50 border-b border-amber-200 dark:border-amber-800/60 flex items-center gap-2 text-xs font-medium text-amber-900 dark:text-amber-200">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              <strong>Resultado exploratorio en entorno Sandbox:</strong> Esta corrida contiene hallazgos preliminares y experimentales sin validación de catálogo productivo certificado.
            </span>
          </div>
        )}

        {/* Mensaje de Estado / Feedback de Descarga */}
        {statusMessage && (
          <div className={`px-6 py-2 text-xs font-semibold border-b flex items-center justify-between ${
            statusMessage.type === 'success'
              ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-200 border-emerald-200 dark:border-emerald-800'
              : statusMessage.type === 'error'
              ? 'bg-rose-50 dark:bg-rose-950/40 text-rose-900 dark:text-rose-200 border-rose-200 dark:border-rose-800'
              : 'bg-blue-50 dark:bg-blue-950/40 text-blue-900 dark:text-blue-200 border-blue-200 dark:border-blue-800'
          }`}>
            <span>{statusMessage.text}</span>
            <button
              type="button"
              onClick={() => setStatusMessage(null)}
              className="text-xs hover:opacity-75"
            >
              ×
            </button>
          </div>
        )}

        {/* Barra de Pestañas */}
        <div className="px-6 border-b border-slate-200 dark:border-slate-800 flex gap-4 bg-white dark:bg-slate-900 text-xs font-bold">
          <button
            type="button"
            onClick={() => setActiveTab('overview')}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'overview'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Layers className="w-4 h-4" />
            Resumen & Cobertura
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('phases')}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'phases'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Clock className="w-4 h-4" />
            Fases de Ejecución ({run.steps.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('rules')}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'rules'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <ShieldCheck className="w-4 h-4" />
            Reglas Evaluadas ({run.executions.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('findings')}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'findings'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <AlertTriangle className="w-4 h-4" />
            Hallazgos ({run.findings.length})
          </button>
          <button
            type="button"
            onClick={() => setActiveTab('exports')}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'exports'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Download className="w-4 h-4" />
            Exportaciones ({run.reports?.length || 0})
          </button>
        </div>

        {/* Contenedor Scrolleable de Contenido */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* TAB 1: OVERVIEW */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* KPIs de Resultados */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                <div className="p-4 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20">
                  <div className="flex items-center justify-between text-emerald-700 dark:text-emerald-300">
                    <span className="text-xs font-bold uppercase">Cumple (Passed)</span>
                    <CheckCircle2 className="w-4 h-4" />
                  </div>
                  <p className="text-2xl font-black text-emerald-900 dark:text-emerald-100 mt-2">
                    {run.summary_stats.passed || 0}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20">
                  <div className="flex items-center justify-between text-rose-700 dark:text-rose-300">
                    <span className="text-xs font-bold uppercase">No Cumple (Failed)</span>
                    <XCircle className="w-4 h-4" />
                  </div>
                  <p className="text-2xl font-black text-rose-900 dark:text-rose-100 mt-2">
                    {run.summary_stats.failed || 0}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20">
                  <div className="flex items-center justify-between text-amber-700 dark:text-amber-300">
                    <span className="text-xs font-bold uppercase">Advertencias</span>
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <p className="text-2xl font-black text-amber-900 dark:text-amber-100 mt-2">
                    {run.summary_stats.warning || 0}
                  </p>
                </div>

                <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40">
                  <div className="flex items-center justify-between text-slate-600 dark:text-slate-400">
                    <span className="text-xs font-bold uppercase">No Evaluable</span>
                    <HelpCircle className="w-4 h-4" />
                  </div>
                  <p className="text-2xl font-black text-slate-800 dark:text-slate-200 mt-2">
                    {run.summary_stats.not_evaluable || 0}
                  </p>
                </div>
              </div>

              {/* Cobertura Documental */}
              <div className="bg-white dark:bg-slate-900 rounded-xl border border-slate-200 dark:border-slate-800 p-5 space-y-3">
                <h3 className="text-sm font-bold text-slate-900 dark:text-white flex items-center gap-2">
                  <FolderGit2 className="w-4 h-4 text-blue-600" />
                  Documentos Evaluados en la Corrida ({run.documents.length})
                </h3>
                <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden text-xs">
                  {run.documents.map((doc, idx) => (
                    <div key={idx} className="p-3 flex items-center justify-between bg-white dark:bg-slate-900 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                      <div className="space-y-0.5">
                        <p className="font-bold text-slate-900 dark:text-white">
                          {doc.filename}
                        </p>
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          Rol: <span className="font-medium text-slate-700 dark:text-slate-300">{doc.document_role}</span> • Motivo: <span className="italic">{doc.inclusion_reason}</span>
                        </p>
                      </div>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                        {doc.status?.toUpperCase() || 'LISTO'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: PHASES */}
          {activeTab === 'phases' && (
            <div className="space-y-3">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">
                Secuencia de Fases Técnicas y Normativas (Fases 1 a 9)
              </h3>
              <div className="space-y-2.5">
                {run.steps.map((st) => {
                  const isSuccess = st.status === 'succeeded';
                  const isSkipped = st.status === 'skipped';
                  const isFailed = st.status === 'failed';

                  return (
                    <div
                      key={st.phase}
                      className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-full bg-slate-100 dark:bg-slate-800 font-bold flex items-center justify-center text-[11px] text-slate-700 dark:text-slate-300">
                            {st.phase}
                          </span>
                          <span className="font-bold text-slate-900 dark:text-white">
                            {st.phase_name}
                          </span>
                          <span className="text-[10px] uppercase font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-500">
                            {st.step_type}
                          </span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isSuccess ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' :
                          isSkipped ? 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-400' :
                          isFailed ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300' :
                          'bg-blue-100 text-blue-800'
                        }`}>
                          {st.status.toUpperCase()}
                        </span>
                      </div>

                      {/* Resúmenes de fase */}
                      {st.output_summary && Object.keys(st.output_summary).length > 0 && (
                        <div className="p-2.5 rounded bg-slate-50 dark:bg-slate-950/40 font-mono text-[11px] text-slate-600 dark:text-slate-400">
                          {JSON.stringify(st.output_summary)}
                        </div>
                      )}

                      {st.error_summary && (
                        <p className="p-2 rounded bg-rose-50 text-rose-800 text-xs">
                          {st.error_summary}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 3: RULES & NOT EVALUABLE */}
          {activeTab === 'rules' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">
                Evaluaciones de Reglas ({run.executions.length})
              </h3>
              <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden">
                {run.executions.map((ex) => {
                  const isPass = ex.status === 'passed';
                  const isFail = ex.status === 'failed';
                  const isWarn = ex.status === 'warning';
                  const isNotEval = ex.status === 'not_evaluable';

                  return (
                    <div key={ex.id} className="p-4 bg-white dark:bg-slate-900 space-y-2 text-xs">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="font-mono font-bold text-slate-900 dark:text-white">
                            {ex.rule_code}
                          </span>
                          <span className="text-slate-400">•</span>
                          <span className="font-medium text-slate-700 dark:text-slate-300">
                            {ex.rule_name}
                          </span>
                        </div>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isPass ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300' :
                          isFail ? 'bg-rose-100 text-rose-800 dark:bg-rose-900/40 dark:text-rose-300' :
                          isWarn ? 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300' :
                          'bg-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                        }`}>
                          {ex.status.toUpperCase()}
                        </span>
                      </div>

                      {/* Not Evaluable Causa Estructurada */}
                      {isNotEval && ex.not_evaluable_reason_code && (
                        <div className="p-3 rounded-lg bg-amber-50/60 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/40 space-y-1 text-xs">
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-amber-900 dark:text-amber-200">
                              Causa:
                            </span>
                            <code className="px-1.5 py-0.5 bg-amber-200 dark:bg-amber-900 rounded font-mono font-bold text-amber-900 dark:text-amber-100 text-[11px]">
                              {ex.not_evaluable_reason_code}
                            </code>
                          </div>
                          <p className="text-amber-800 dark:text-amber-300">
                            {ex.not_evaluable_reason_message}
                          </p>
                          {ex.recommended_action && (
                            <p className="text-blue-700 dark:text-blue-300 font-semibold pt-1">
                              Acción recomendada: {ex.recommended_action}
                            </p>
                          )}
                        </div>
                      )}

                      {/* Resumen del Resultado */}
                      {ex.result_summary && !isNotEval && (
                        <p className="text-slate-600 dark:text-slate-400">
                          {ex.result_summary.description || ex.result_summary.title}
                        </p>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 4: FINDINGS */}
          {activeTab === 'findings' && (
            <div className="space-y-4">
              <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-2">
                Hallazgos Técnicos Registrados ({run.findings.length})
              </h3>
              {run.findings.length === 0 ? (
                <div className="p-8 text-center bg-slate-50 dark:bg-slate-950/40 border border-slate-200 dark:border-slate-800 rounded-xl">
                  <CheckCircle2 className="w-8 h-8 text-emerald-600 mx-auto mb-2" />
                  <p className="text-sm font-semibold text-slate-700 dark:text-slate-300">
                    No se registraron discrepancias en esta corrida de revisión.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {run.findings.map((f) => {
                    const isCrit = f.severity === 'critical';
                    const isHigh = f.severity === 'high';

                    return (
                      <div
                        key={f.id}
                        className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2 hover:shadow-md transition-shadow text-xs"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="flex items-center gap-2">
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

                          {/* Botón de Contexto / Visor */}
                          {f.navigation_context?.document_id ? (
                            <button
                              type="button"
                              onClick={() => {
                                if (onNavigateContext) onNavigateContext(f);
                                onClose();
                              }}
                              className="px-2.5 py-1 text-xs font-semibold rounded bg-blue-50 hover:bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:hover:bg-blue-900/50 dark:text-blue-300 flex items-center gap-1 transition-colors shrink-0"
                            >
                              <Eye className="w-3.5 h-3.5 text-blue-600" />
                              Abrir Contexto
                            </button>
                          ) : (
                            <span className="text-slate-400 italic text-[11px]">
                              Sin contexto visual
                            </span>
                          )}
                        </div>

                        <p className="text-slate-600 dark:text-slate-300">
                          {f.description}
                        </p>

                        {f.recommendation && (
                          <div className="p-2.5 rounded bg-blue-50/50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 text-blue-900 dark:text-blue-200">
                            <strong>Recomendación:</strong> {f.recommendation}
                          </div>
                        )}

                        {f.bbox && (
                          <p className="text-[11px] font-mono text-slate-400">
                            BBox: [{f.bbox.map((v: number) => typeof v === 'number' ? v.toFixed(1) : v).join(', ')}]
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 5: EXPORTS & AUTHENTICATED DOWNLOADS */}
          {activeTab === 'exports' && (
            <div className="space-y-6">
              {/* Acciones para generar nuevas exportaciones */}
              <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 flex items-center justify-between flex-wrap gap-3">
                <div>
                  <h4 className="text-xs font-bold text-slate-900 dark:text-white uppercase tracking-wider">
                    Generar Nuevo Reporte Persistido
                  </h4>
                  <p className="text-[11px] text-slate-500">
                    Crea y descarga instantáneamente el artefacto certificado en formato JSON, XLSX o PDF.
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleCreateAndDownloadExport('json')}
                    disabled={generatingFormat !== null}
                    className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 text-slate-800 dark:text-slate-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
                  >
                    <FileText className="w-3.5 h-3.5 text-blue-600" />
                    {generatingFormat === 'json' ? 'Generando...' : 'JSON'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCreateAndDownloadExport('xlsx')}
                    disabled={generatingFormat !== null}
                    className="px-3 py-1.5 rounded-lg bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 text-slate-800 dark:text-slate-200 text-xs font-bold flex items-center gap-1.5 transition-colors"
                  >
                    <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-600" />
                    {generatingFormat === 'xlsx' ? 'Generando...' : 'XLSX'}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleCreateAndDownloadExport('pdf')}
                    disabled={generatingFormat !== null}
                    className="px-3.5 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-xs font-bold flex items-center gap-1.5 shadow-sm transition-colors"
                  >
                    <Download className="w-3.5 h-3.5" />
                    {generatingFormat === 'pdf' ? 'Generando...' : 'PDF Oficial'}
                  </button>
                </div>
              </div>

              {/* Lista de Reportes Persistidos */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold text-slate-700 dark:text-slate-300 uppercase tracking-wider">
                  Reportes Existentes en Almacenamiento ({run.reports?.length || 0})
                </h4>

                {(!run.reports || run.reports.length === 0) ? (
                  <p className="text-xs text-slate-500 italic text-center py-6 border border-dashed border-slate-200 dark:border-slate-800 rounded-xl">
                    No se han generado exportaciones físicas para esta corrida aún. Utilice los botones superiores para generarlas.
                  </p>
                ) : (
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden text-xs">
                    {run.reports.map((rep) => (
                      <div key={rep.id} className="p-4 bg-white dark:bg-slate-900 flex items-center justify-between gap-4 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                        <div className="space-y-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase ${
                              rep.format === 'pdf' ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300' :
                              rep.format === 'xlsx' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300' :
                              'bg-blue-100 text-blue-800 dark:bg-blue-950/60 dark:text-blue-300'
                            }`}>
                              {rep.format}
                            </span>
                            <span className="font-bold text-slate-900 dark:text-white truncate">
                              {rep.report_name}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-slate-500 text-[11px]">
                            <span>
                              {rep.created_at ? new Date(rep.created_at).toLocaleString() : 'N/A'}
                            </span>
                            {rep.file_size_bytes ? (
                              <span>{(rep.file_size_bytes / 1024).toFixed(1)} KB</span>
                            ) : null}
                            <span className="flex items-center gap-1 font-mono text-[10px] text-slate-400">
                              SHA256: {rep.sha256.slice(0, 12)}...
                              <button
                                type="button"
                                onClick={() => handleCopy(rep.sha256)}
                                className="hover:text-slate-600 transition-colors"
                                title="Copiar SHA256 completo"
                              >
                                {copiedHash === rep.sha256 ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
                              </button>
                            </span>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => handleDownload(rep.id, rep.format)}
                          disabled={downloadingId === rep.id}
                          className="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-bold text-xs flex items-center gap-1.5 transition-colors shrink-0"
                        >
                          {downloadingId === rep.id ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              <span>Descargando...</span>
                            </>
                          ) : (
                            <>
                              <Download className="w-3.5 h-3.5" />
                              <span>Descargar</span>
                            </>
                          )}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 flex items-center justify-between bg-slate-50/50 dark:bg-slate-950/40 text-xs">
          <span className="text-slate-500">
            ID de Corrida: <code className="font-mono text-slate-700 dark:text-slate-300">{run.id}</code>
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 font-bold text-slate-700 dark:text-slate-300 transition-colors"
          >
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
};
