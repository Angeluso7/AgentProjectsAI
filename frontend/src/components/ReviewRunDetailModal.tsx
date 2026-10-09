import React, { useState, useEffect, useMemo } from 'react';
import {
  X,
  ShieldCheck,
  AlertTriangle,
  AlertCircle,
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
  Check,
  Shapes,
  MapPin,
  Search,
  ChevronRight,
  ChevronDown,
  ArrowLeft,
  PieChart as PieChartIcon
} from 'lucide-react';
import {
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Tooltip as RechartsTooltip,
  Legend as RechartsLegend
} from 'recharts';
import {
  ReviewRunDetailResponse,
  ReviewFindingDetail,
  ReviewReportItem,
  SymbolInventoryResponse,
  SymbolInventoryMetrics,
  SymbolInventoryGroupItem,
  SymbolOccurrenceSummaryItem,
  SymbolExecutiveSummaryItem
} from '../types';
import { apiService } from '../services/api';

const defaultMetrics: SymbolInventoryMetrics = {
  documents_reviewed: 0,
  sheets_reviewed: 0,
  geometric_candidates: 0,
  valid_symbol_occurrences: 0,
  inventory_groups: 0,
  recognized_production: 0,
  recognized_sandbox: 0,
  recognized_reference_only: 0,
  unknown: 0,
  ambiguous: 0,
  requires_review: 0,
  figures_excluded: 0,
  not_symbols: 0,
  inventory_coverage: 0,
  production_coverage: 0,
  sandbox_coverage: 0,
  unknown_rate: 0,
  review_required_rate: 0,
  exclusion_rate: 0,
  by_document: {}
};

interface ReviewRunDetailModalProps {
  isOpen: boolean;
  onClose: () => void;
  run: ReviewRunDetailResponse | null;
  projectName?: string;
  onNavigateContext?: (finding: ReviewFindingDetail) => void;
  onRefreshRun?: () => void;
  initialTab?: TabType;
}

type TabType = 'overview' | 'phases' | 'rules' | 'findings' | 'inventory' | 'exports';

export const ReviewRunDetailModal: React.FC<ReviewRunDetailModalProps> = ({
  isOpen,
  onClose,
  run,
  projectName,
  onNavigateContext,
  onRefreshRun,
  initialTab = 'overview'
}) => {
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [generatingFormat, setGeneratingFormat] = useState<'json' | 'xlsx' | 'pdf' | null>(null);
  const [statusMessage, setStatusMessage] = useState<{ text: string; type: 'info' | 'success' | 'error' } | null>(null);
  const [copiedHash, setCopiedHash] = useState<string | null>(null);

  // Estados para Inventario de Simbología y Ocurrencias (Tabla 1 y Tabla 2)
  // Inicialización completamente defensiva: nunca lee run.symbol_inventory si run es null
  const [inventoryData, setInventoryData] = useState<SymbolInventoryResponse | null>(() => run?.symbol_inventory ?? null);
  const [isLoadingInventory, setIsLoadingInventory] = useState<boolean>(false);
  const [isRegeneratingInventory, setIsRegeneratingInventory] = useState<boolean>(false);
  const [selectedGroup, setSelectedGroup] = useState<SymbolInventoryGroupItem | null>(null);
  const [groupOccurrences, setGroupOccurrences] = useState<SymbolOccurrenceSummaryItem[]>([]);
  const [isLoadingOccurrences, setIsLoadingOccurrences] = useState<boolean>(false);
  const [inventoryFilter, setInventoryFilter] = useState<'all' | 'production' | 'sandbox' | 'unknown' | 'excluded'>('all');

  useEffect(() => {
    if (run?.symbol_inventory) {
      setInventoryData(run.symbol_inventory);
    } else if (!run) {
      setInventoryData(null);
    }
  }, [run?.id, run?.symbol_inventory]);

  const loadInventory = async (force = false) => {
    if (!run?.id) return;
    if (!force && inventoryData) return;
    setIsLoadingInventory(true);
    try {
      const data = await apiService.getSymbolInventory(run.id);
      setInventoryData(data);
    } catch (err: any) {
      console.error('Error cargando inventario de simbología:', err);
      setInventoryData({
        status: 'failed',
        metrics: defaultMetrics,
        groups: [],
        excluded_groups: [],
        reason_code: 'INVENTORY_API_ERROR',
        reason_message: err?.response?.data?.detail || err?.message || 'Error al consultar inventario de simbología.',
        can_generate: true
      });
    } finally {
      setIsLoadingInventory(false);
    }
  };

  const handleRegenerateInventory = async () => {
    if (!run?.id) return;
    setIsRegeneratingInventory(true);
    setStatusMessage({ text: 'Regenerando inventario técnico de simbología...', type: 'info' });
    try {
      const data = await apiService.regenerateSymbolInventory(run.id);
      setInventoryData(data);
      setStatusMessage({
        text: `Inventario de simbología generado exitosamente (Versión ${data.inventory_version || 'v1'}).`,
        type: 'success'
      });
      if (onRefreshRun) {
        await onRefreshRun();
      }
      setTimeout(() => setStatusMessage(null), 5000);
    } catch (err: any) {
      console.error('Error regenerando inventario de simbología:', err);
      const errMsg = err?.response?.data?.detail || err?.message || 'Error al regenerar inventario.';
      setStatusMessage({
        text: errMsg,
        type: 'error'
      });
      setInventoryData({
        status: 'failed',
        metrics: defaultMetrics,
        groups: [],
        excluded_groups: [],
        reason_code: 'INVENTORY_BUILD_FAILED',
        reason_message: errMsg,
        can_generate: true
      });
    } finally {
      setIsRegeneratingInventory(false);
    }
  };

  const handleSelectGroup = async (group: SymbolInventoryGroupItem) => {
    if (!run?.id) return;
    setSelectedGroup(group);
    setIsLoadingOccurrences(true);
    try {
      const occs = await apiService.getSymbolGroupOccurrences(run.id, group.id);
      setGroupOccurrences(occs);
    } catch (err: any) {
      console.error('Error cargando ocurrencias del grupo:', err);
      setGroupOccurrences([]);
    } finally {
      setIsLoadingOccurrences(false);
    }
  };

  if (!isOpen || !run) return null;

  const isSandbox = run.execution_mode === 'sandbox';

  // Fallback seguro defensivo para inventario
  const rawInventory = inventoryData ?? run?.symbol_inventory;
  const inventory: SymbolInventoryResponse = {
    status: rawInventory?.status ?? 'unavailable',
    metrics: rawInventory?.metrics ?? defaultMetrics,
    groups: rawInventory?.groups ?? [],
    excluded_groups: rawInventory?.excluded_groups ?? [],
    reason_code: rawInventory?.reason_code ?? (run?.id ? 'INVENTORY_NOT_AVAILABLE' : null),
    reason_message: rawInventory?.reason_message ?? 'Inventario no disponible.',
    can_generate: rawInventory?.can_generate ?? Boolean(run?.id),
    inventory_version: rawInventory?.inventory_version ?? null,
    inventory_generated_at: rawInventory?.inventory_generated_at ?? null,
    inventory_source_snapshot_hash: rawInventory?.inventory_source_snapshot_hash ?? null
  };

  const metrics = inventory.metrics ?? defaultMetrics;
  const groups = inventory.groups ?? [];
  const excludedGroups = inventory.excluded_groups ?? [];

  // Derivación de estado empty según requisito 3:
  // status=available + inventory_generated_at != null + valid_symbol_occurrences=0
  const isAvailableEmpty = inventory.status === 'available' &&
    inventory.inventory_generated_at != null &&
    (metrics.valid_symbol_occurrences ?? 0) === 0 &&
    groups.length === 0;

  // Derivación ejecutiva de simbología para el punto de revisión
  const isSymbolRun = Boolean(
    run.topic_code === 'PID_SYMBOLS' ||
    run.discipline_code === 'PIPING' ||
    (inventory.executive_summary && inventory.executive_summary.length > 0)
  );

  const executiveRows: SymbolExecutiveSummaryItem[] = useMemo(() => {
    if (inventory.executive_summary && inventory.executive_summary.length > 0) {
      return inventory.executive_summary;
    }
    if (!groups || groups.length === 0) return [];
    return groups.map((g, idx) => {
      const occSheetMap = g.occurrences_by_sheet || {};
      const labels = Object.keys(occSheetMap).map((s, sIdx) => `Lámina ${sIdx + 1}`);
      return {
        item_index: idx + 1,
        symbol_code: g.display_code || 'S-001',
        description: g.canonical_name || g.description || 'Componente técnico de piping',
        found: (g.total_occurrences || 0) > 0,
        quantity: g.total_occurrences || 0,
        sheet_labels: labels,
        sheets_display: labels.length > 0 ? labels.join(', ') : ((g.total_occurrences || 0) > 0 ? 'Ubicación no determinada' : '-')
      };
    });
  }, [inventory.executive_summary, groups]);

  const foundCount = useMemo(() => executiveRows.filter((r) => r.found).length, [executiveRows]);
  const missingCount = useMemo(() => executiveRows.filter((r) => !r.found).length, [executiveRows]);
  const totalExecutiveOccurrences = useMemo(
    () => executiveRows.reduce((acc, r) => acc + (r.quantity || 0), 0),
    [executiveRows]
  );
  const distinctSheetsCount = useMemo(() => {
    const s = new Set<string>();
    executiveRows.forEach((r) => {
      (r.sheet_labels || []).forEach((l) => s.add(l));
    });
    return s.size > 0 ? s.size : (foundCount > 0 ? 1 : 0);
  }, [executiveRows, foundCount]);

  const symbolChartData = useMemo(() => {
    return [
      { name: 'Encontrados', value: foundCount, color: '#10b981' },
      { name: 'No encontrados / Faltantes', value: missingCount, color: '#f59e0b' }
    ];
  }, [foundCount, missingCount]);

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
            onClick={() => {
              setActiveTab('inventory');
              loadInventory();
            }}
            className={`py-3 border-b-2 transition-all flex items-center gap-1.5 ${
              activeTab === 'inventory'
                ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
            }`}
          >
            <Shapes className="w-4 h-4" />
            Inventario de Simbología ({inventory.groups?.length ?? 0})
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

                        {(() => {
                          const [mainDesc, techDetail] = (f.description || '').includes(' / Detalle técnico: ')
                            ? (f.description || '').split(' / Detalle técnico: ')
                            : [f.description, null];

                          return (
                            <div className="space-y-1.5">
                              <p className="text-slate-700 dark:text-slate-200 text-xs font-medium leading-relaxed">
                                {mainDesc}
                              </p>
                              {techDetail && (
                                <details className="group pt-0.5">
                                  <summary className="cursor-pointer text-[11px] font-semibold text-blue-600 dark:text-blue-400 hover:underline list-none inline-flex items-center gap-1 select-none">
                                    <span className="group-open:rotate-90 transition-transform inline-block text-[10px]">▸</span>
                                    <span>Ver detalle técnico normativo</span>
                                  </summary>
                                  <div className="mt-1.5 p-2 rounded-lg bg-slate-50 dark:bg-slate-950/60 border border-slate-200/80 dark:border-slate-800 text-[11px] font-mono text-slate-600 dark:text-slate-400 leading-relaxed">
                                    {techDetail}
                                  </div>
                                </details>
                              )}
                            </div>
                          );
                        })()}

                        {f.recommendation && (
                          <div className="p-2.5 rounded-lg bg-blue-50/50 dark:bg-blue-950/30 border border-blue-100 dark:border-blue-900/40 text-blue-900 dark:text-blue-200">
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

          {/* TAB: INVENTARIO DE SIMBOLOGÍA (TABLA 1 Y TABLA 2) */}
          {activeTab === 'inventory' && (
            <div className="space-y-6">
              {isLoadingInventory ? (
                <div className="py-12 flex flex-col items-center justify-center gap-3 text-slate-500">
                  <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
                  <p className="text-xs font-semibold">Cargando inventario consolidado y doble recortes técnicos...</p>
                </div>
              ) : selectedGroup ? (
                /* TABLA 2: OCURRENCIAS Y LOCALIZACIONES DEL GRUPO SELECCIONADO */
                <div className="space-y-4">
                  <div className="flex items-center justify-between pb-3 border-b border-slate-200 dark:border-slate-800">
                    <button
                      type="button"
                      onClick={() => {
                        setSelectedGroup(null);
                        setGroupOccurrences([]);
                      }}
                      className="flex items-center gap-1.5 text-xs font-bold text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <ArrowLeft className="w-4 h-4" />
                      Volver a Inventario Consolidado (Tabla 1)
                    </button>
                    <span className="text-xs text-slate-500">
                      Grupo: <strong className="text-slate-900 dark:text-white">{selectedGroup.display_code}</strong>
                    </span>
                  </div>

                  {/* Cabecera del Grupo Seleccionado */}
                  <div className="p-4 rounded-xl border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/40 space-y-2">
                    <div className="flex items-start justify-between flex-wrap gap-2">
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="px-2.5 py-0.5 rounded font-mono text-xs font-bold bg-blue-100 dark:bg-blue-950/60 text-blue-800 dark:text-blue-300">
                            {selectedGroup.display_code}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold uppercase ${
                            selectedGroup.catalog_status === 'recognized_production' ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300' :
                            selectedGroup.catalog_status === 'recognized_sandbox' ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300' :
                            selectedGroup.catalog_status === 'unknown_symbol' ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300' :
                            selectedGroup.catalog_status === 'ambiguous_symbol' ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300' :
                            'bg-slate-100 text-slate-700'
                          }`}>
                            {selectedGroup.catalog_status.replace('_', ' ')}
                          </span>
                          <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                            {selectedGroup.canonical_name || 'Símbolo Técnico'}
                          </h3>
                        </div>
                        <p className="text-xs text-slate-600 dark:text-slate-300">
                          {selectedGroup.description || selectedGroup.explanation || 'Sin descripción técnica registrada.'}
                        </p>
                      </div>
                      <div className="text-right text-xs text-slate-500">
                        <div>Total Ocurrencias: <strong className="text-slate-900 dark:text-white">{selectedGroup.total_occurrences}</strong></div>
                        <div>Norma: <strong className="text-slate-700 dark:text-slate-300">{selectedGroup.standard_reference || 'N/A'}</strong></div>
                      </div>
                    </div>
                  </div>

                  {/* Listado / Grilla de Ocurrencias (Tabla 2) */}
                  <div className="space-y-2">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                      <MapPin className="w-3.5 h-3.5 text-blue-600" />
                      Tabla 2: Localización y Doble Recorte por Ocurrencia ({groupOccurrences.length})
                    </h4>

                    {isLoadingOccurrences ? (
                      <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-500">
                        <RefreshCw className="w-5 h-5 animate-spin text-blue-600" />
                        <span className="text-xs">Cargando ocurrencias y coordenadas de recortes...</span>
                      </div>
                    ) : groupOccurrences.length === 0 ? (
                      <div className="p-8 text-center text-xs text-slate-500 italic border rounded-xl border-dashed">
                        No hay ocurrencias registradas para este grupo.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {groupOccurrences.map((occ, idx) => (
                          <div
                            key={occ.occurrence_id || idx}
                            className="p-3.5 rounded-xl border border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 space-y-2.5 text-xs shadow-sm hover:border-blue-300 dark:hover:border-blue-700 transition-colors"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <div>
                                <span className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                                  <FileText className="w-3.5 h-3.5 text-slate-400" />
                                  {occ.document_name}
                                </span>
                                <span className="text-[11px] text-slate-500">
                                  {occ.sheet_name || `Lámina Pág ${occ.page_number}`} • Pág {occ.page_number}
                                </span>
                              </div>
                              <button
                                type="button"
                                onClick={() => {
                                  if (onNavigateContext) {
                                    onNavigateContext({
                                      id: occ.occurrence_id,
                                      rule_code: 'PID_SYMBOLS',
                                      rule_name: 'Simbología P&ID',
                                      severity: 'info',
                                      status: 'open',
                                      title: `${selectedGroup.display_code} - ${selectedGroup.canonical_name || 'Símbolo'}`,
                                      description: `Ocurrencia identificada en ${occ.document_name} (${occ.sheet_name})`,
                                      bbox: occ.symbol_crop_bbox || occ.bbox_normalized,
                                      navigation_context: occ.navigation_context
                                    });
                                    onClose();
                                  }
                                }}
                                className="px-2.5 py-1 text-xs font-bold rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:hover:bg-blue-900/80 dark:text-blue-300 flex items-center gap-1 transition-colors shrink-0"
                              >
                                <Eye className="w-3.5 h-3.5 text-blue-600 dark:text-blue-400" />
                                Abrir en Visor
                              </button>
                            </div>

                            {/* Metadatos de Doble Recorte Técnico */}
                            <div className="p-2 rounded bg-slate-50 dark:bg-slate-950/40 border border-slate-100 dark:border-slate-800/60 space-y-1 font-mono text-[10px] text-slate-600 dark:text-slate-400">
                              <div className="flex items-center justify-between">
                                <span>Tag/Código: <strong className="text-slate-800 dark:text-slate-200">{occ.detected_tag_or_code || 'N/A'}</strong></span>
                                <span>Confianza: <strong className="text-emerald-700 dark:text-emerald-400">{((occ.geometric_confidence || 1.0) * 100).toFixed(1)}%</strong></span>
                              </div>
                              <div>
                                Symbol Crop (3mm): [{occ.symbol_crop_bbox?.map((v: number) => v.toFixed(2)).join(', ') || occ.bbox_normalized?.map((v: number) => v.toFixed(2)).join(', ') || '-'}]
                              </div>
                              <div>
                                Context Crop (15mm): [{occ.occurrence_context_crop_bbox?.map((v: number) => v.toFixed(2)).join(', ') || '-'}]
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* TABLA 1: INVENTARIO CONSOLIDADO O ESTADOS ALTERNATIVOS */
                <div className="space-y-6">
                  {/* ESTADO 1: PENDING (En proceso) */}
                  {inventory.status === 'pending' && (
                    <div className="py-16 flex flex-col items-center justify-center gap-3 text-slate-500">
                      <RefreshCw className="w-8 h-8 animate-spin text-blue-600" />
                      <p className="text-sm font-bold text-slate-700 dark:text-slate-300">
                        Inventario de simbología en proceso...
                      </p>
                      <span className="text-xs text-slate-400">
                        La corrida de revisión o el recálculo está en ejecución.
                      </span>
                    </div>
                  )}

                  {/* ESTADO 2: UNAVAILABLE (Corrida histórica sin inventario) */}
                  {inventory.status === 'unavailable' && (
                    <div className="p-8 rounded-2xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/40 dark:bg-amber-950/20 text-center space-y-4">
                      <div className="w-12 h-12 rounded-full bg-amber-100 dark:bg-amber-900/40 flex items-center justify-center mx-auto text-amber-600 dark:text-amber-400">
                        <Clock className="w-6 h-6" />
                      </div>
                      <div className="max-w-md mx-auto space-y-1">
                        <h3 className="text-sm font-bold text-amber-900 dark:text-amber-100">
                          Inventario no generado en esta corrida
                        </h3>
                        <p className="text-xs text-amber-700 dark:text-amber-300">
                          {inventory.reason_message || 'Esta corrida fue creada antes del inventario de simbología.'}
                        </p>
                        <p className="text-[11px] text-amber-600/80 dark:text-amber-400/80 pt-1">
                          Puedes generar el inventario técnico consolidado bajo demanda a partir de las geometrías y documentos existentes sin necesidad de reprocesar toda la auditoría.
                        </p>
                      </div>
                      {inventory.can_generate && (
                        <div className="pt-2">
                          <button
                            type="button"
                            onClick={handleRegenerateInventory}
                            disabled={isRegeneratingInventory}
                            className="px-4 py-2 text-xs font-bold rounded-xl bg-amber-600 hover:bg-amber-700 text-white shadow-sm inline-flex items-center gap-2 transition-all disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isRegeneratingInventory ? 'animate-spin' : ''}`} />
                            {isRegeneratingInventory ? 'Generando Inventario...' : 'Generar Inventario Ahora'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ESTADO 3: FAILED (Error técnico seguro) */}
                  {inventory.status === 'failed' && (
                    <div className="p-8 rounded-2xl border border-rose-200 dark:border-rose-900/40 bg-rose-50/40 dark:bg-rose-950/20 text-center space-y-4">
                      <div className="w-12 h-12 rounded-full bg-rose-100 dark:bg-rose-900/40 flex items-center justify-center mx-auto text-rose-600 dark:text-rose-400">
                        <AlertCircle className="w-6 h-6" />
                      </div>
                      <div className="max-w-md mx-auto space-y-1">
                        <h3 className="text-sm font-bold text-rose-900 dark:text-rose-100">
                          Error al Cargar o Generar Inventario
                        </h3>
                        <p className="text-xs text-rose-700 dark:text-rose-300">
                          {inventory.reason_message || 'Ocurrió un error técnico al procesar el inventario de simbología.'}
                        </p>
                        {inventory.reason_code && (
                          <span className="inline-block mt-1 px-2 py-0.5 rounded font-mono text-[10px] bg-rose-200/60 dark:bg-rose-900/60 text-rose-800 dark:text-rose-200">
                            Código: {inventory.reason_code}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center justify-center gap-3 pt-2">
                        <button
                          type="button"
                          onClick={() => loadInventory(true)}
                          className="px-3 py-1.5 text-xs font-semibold rounded-lg border border-rose-300 dark:border-rose-800 text-rose-700 dark:text-rose-300 hover:bg-rose-100 dark:hover:bg-rose-900/40 transition-colors"
                        >
                          Reintentar Consulta
                        </button>
                        {inventory.can_generate && (
                          <button
                            type="button"
                            onClick={handleRegenerateInventory}
                            disabled={isRegeneratingInventory}
                            className="px-3.5 py-1.5 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-sm inline-flex items-center gap-1.5 transition-all disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isRegeneratingInventory ? 'animate-spin' : ''}`} />
                            {isRegeneratingInventory ? 'Reintentando...' : 'Reintentar Generación'}
                          </button>
                        )}
                      </div>
                    </div>
                  )}

                  {/* ESTADO 4: AVAILABLE PERO VACÍO (0 símbolos detectados) */}
                  {inventory.status === 'available' && isAvailableEmpty && (
                    <div className="p-8 rounded-2xl border border-slate-200 dark:border-slate-800 bg-slate-50/50 dark:bg-slate-900/50 text-center space-y-4">
                      <div className="w-12 h-12 rounded-full bg-slate-100 dark:bg-slate-800 flex items-center justify-center mx-auto text-slate-500">
                        <Shapes className="w-6 h-6" />
                      </div>
                      <div className="max-w-md mx-auto space-y-1">
                        <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                          No se detectaron símbolos geométricos válidos
                        </h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">
                          La corrida de revisión evaluó los documentos pero no identificó geometrías coincidentes con el catálogo de símbolos ni candidatos geométricos válidos.
                        </p>
                      </div>
                      <div className="inline-flex flex-wrap items-center justify-center gap-4 text-xs font-mono text-slate-600 dark:text-slate-400 pt-2 border-t border-slate-200 dark:border-slate-800">
                        <span>Figuras excluidas: <strong>{metrics.figures_excluded || 0}</strong></span>
                        <span>No-símbolos: <strong>{metrics.not_symbols || 0}</strong></span>
                        <span>Láminas revisadas: <strong>{metrics.sheets_reviewed || 0}</strong></span>
                      </div>
                      {inventory.can_generate && (
                        <div className="pt-2">
                          <button
                            type="button"
                            onClick={handleRegenerateInventory}
                            disabled={isRegeneratingInventory}
                            className="px-4 py-2 text-xs font-bold rounded-xl bg-blue-600 hover:bg-blue-700 text-white shadow-sm inline-flex items-center gap-2 transition-all disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isRegeneratingInventory ? 'animate-spin' : ''}`} />
                            {isRegeneratingInventory ? 'Regenerando...' : 'Regenerar Inventario'}
                          </button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ESTADO 5: AVAILABLE CON GRUPOS */}
                  {inventory.status === 'available' && !isAvailableEmpty && (
                    <>
                      {/* BLOQUE EJECUTIVO: RESUMEN GRÁFICO DE SIMBOLOGÍA POR PUNTO DE REVISIÓN */}
                      {isSymbolRun && (
                        <div className="p-5 rounded-2xl border border-slate-200 dark:border-slate-800 bg-gradient-to-br from-slate-50/80 via-white to-blue-50/20 dark:from-slate-900/90 dark:via-slate-900 dark:to-slate-950 space-y-5 shadow-sm">
                          <div className="flex items-start justify-between flex-wrap gap-2 pb-3 border-b border-slate-200/80 dark:border-slate-800">
                            <div className="space-y-1">
                              <div className="flex items-center gap-2">
                                <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-300 flex items-center gap-1">
                                  <Sparkles className="w-3 h-3 text-blue-600" />
                                  Punto de Revisión: {run.topic_name || 'Revisión de Válvulas y Equipos P&ID'}
                                </span>
                                <span className="text-[11px] font-mono text-slate-400">
                                  [{run.topic_code || 'PID_SYMBOLS'}]
                                </span>
                              </div>
                              <h3 className="text-sm font-bold text-slate-900 dark:text-white">
                                Resumen Gráfico de Simbología
                              </h3>
                              <p className="text-xs text-slate-500 dark:text-slate-400">
                                Estado de presencia y conteo de componentes evaluados para este punto de revisión.
                              </p>
                            </div>
                          </div>

                          {/* B) GRÁFICO MINIMALISTA (DONA CON RECHARTS) + TARJETAS DE SÍNTESIS */}
                          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
                            {/* Columna de Gráfico */}
                            <div className="md:col-span-5 flex flex-col items-center justify-center p-3 rounded-xl bg-white dark:bg-slate-950/40 border border-slate-200/80 dark:border-slate-800/80 min-h-[190px]">
                              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                                Presencia de Símbolos en Láminas
                              </span>
                              <div className="w-full h-36 flex items-center justify-center">
                                <ResponsiveContainer width="100%" height="100%">
                                  <PieChart>
                                    <Pie
                                      data={symbolChartData}
                                      cx="50%"
                                      cy="50%"
                                      innerRadius={36}
                                      outerRadius={56}
                                      paddingAngle={4}
                                      dataKey="value"
                                    >
                                      {symbolChartData.map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.color} stroke="transparent" />
                                      ))}
                                    </Pie>
                                    <RechartsTooltip
                                      contentStyle={{
                                        backgroundColor: '#0f172a',
                                        borderColor: '#334155',
                                        borderRadius: '0.5rem',
                                        fontSize: '11px',
                                        color: '#fff'
                                      }}
                                    />
                                    <RechartsLegend
                                      verticalAlign="bottom"
                                      height={28}
                                      iconSize={8}
                                      wrapperStyle={{ fontSize: '11px' }}
                                    />
                                  </PieChart>
                                </ResponsiveContainer>
                              </div>
                            </div>

                            {/* Columna de Métricas de Resumen */}
                            <div className="md:col-span-7 grid grid-cols-2 gap-3">
                              <div className="p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-900/40 bg-emerald-50/50 dark:bg-emerald-950/20">
                                <div className="flex items-center gap-1.5 text-emerald-800 dark:text-emerald-300">
                                  <CheckCircle2 className="w-4 h-4 text-emerald-600" />
                                  <span className="text-xs font-bold">Encontrados en Plano</span>
                                </div>
                                <p className="text-2xl font-black text-emerald-900 dark:text-emerald-100 mt-1">
                                  {foundCount}
                                </p>
                                <p className="text-[11px] text-emerald-700/80 dark:text-emerald-400/80">
                                  {executiveRows.length > 0 ? `${((foundCount / executiveRows.length) * 100).toFixed(0)}% del catálogo evaluado` : 'Símbolos presentes'}
                                </p>
                              </div>

                              <div className="p-3.5 rounded-xl border border-amber-200 dark:border-amber-900/40 bg-amber-50/50 dark:bg-amber-950/20">
                                <div className="flex items-center gap-1.5 text-amber-800 dark:text-amber-300">
                                  <AlertCircle className="w-4 h-4 text-amber-600" />
                                  <span className="text-xs font-bold">No encontrados / Faltantes</span>
                                </div>
                                <p className="text-2xl font-black text-amber-900 dark:text-amber-100 mt-1">
                                  {missingCount}
                                </p>
                                <p className="text-[11px] text-amber-700/80 dark:text-amber-400/80">
                                  {executiveRows.length > 0 ? `${((missingCount / executiveRows.length) * 100).toFixed(0)}% no detectado en plano` : 'Sin apariciones'}
                                </p>
                              </div>

                              <div className="p-3.5 rounded-xl border border-blue-200 dark:border-blue-900/40 bg-blue-50/50 dark:bg-blue-950/20">
                                <div className="flex items-center gap-1.5 text-blue-800 dark:text-blue-300">
                                  <Layers className="w-4 h-4 text-blue-600" />
                                  <span className="text-xs font-bold">Total Apariciones</span>
                                </div>
                                <p className="text-2xl font-black text-blue-900 dark:text-blue-100 mt-1">
                                  {totalExecutiveOccurrences}
                                </p>
                                <p className="text-[11px] text-blue-700/80 dark:text-blue-400/80">
                                  Elementos contados en proyecto
                                </p>
                              </div>

                              <div className="p-3.5 rounded-xl border border-purple-200 dark:border-purple-900/40 bg-purple-50/50 dark:bg-purple-950/20">
                                <div className="flex items-center gap-1.5 text-purple-800 dark:text-purple-300">
                                  <FileText className="w-4 h-4 text-purple-600" />
                                  <span className="text-xs font-bold">Láminas con Simbología</span>
                                </div>
                                <p className="text-2xl font-black text-purple-900 dark:text-purple-100 mt-1">
                                  {distinctSheetsCount}
                                </p>
                                <p className="text-[11px] text-purple-700/80 dark:text-purple-400/80">
                                  Láminas con componentes
                                </p>
                              </div>
                            </div>
                          </div>

                          {/* A) TABLA: RESUMEN GRÁFICO DE SIMBOLOGÍA */}
                          <div className="space-y-2">
                            <div className="flex items-center justify-between">
                              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                                <Shapes className="w-3.5 h-3.5 text-blue-600" />
                                Tabla Resumen Gráfico de Simbología ({executiveRows.length} ítems)
                              </h4>
                              <span className="text-[11px] text-slate-500">
                                ITEM | Símbolo | Descripción | Encontrado | Cantidad | Lámina
                              </span>
                            </div>

                            <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-slate-900 shadow-sm">
                              <div className="overflow-x-auto">
                                <table className="w-full text-left text-xs">
                                  <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase text-slate-600 dark:text-slate-300">
                                    <tr>
                                      <th className="px-3.5 py-2.5 text-center w-12">ITEM</th>
                                      <th className="px-3.5 py-2.5">Símbolo</th>
                                      <th className="px-3.5 py-2.5">Descripción</th>
                                      <th className="px-3.5 py-2.5 text-center">Encontrado (Sí/No)</th>
                                      <th className="px-3.5 py-2.5 text-right">Cantidad</th>
                                      <th className="px-3.5 py-2.5">Página/Lámina</th>
                                    </tr>
                                  </thead>
                                  <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                                    {executiveRows.map((row) => (
                                      <tr
                                        key={row.item_index}
                                        className={`hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors ${
                                          !row.found ? 'opacity-85 bg-slate-50/40 dark:bg-slate-950/20' : ''
                                        }`}
                                      >
                                        <td className="px-3.5 py-2.5 text-center font-mono font-bold text-slate-500">
                                          {row.item_index}
                                        </td>
                                        <td className="px-3.5 py-2.5 font-mono font-bold text-slate-900 dark:text-white">
                                          <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-blue-700 dark:text-blue-300">
                                            {row.symbol_code}
                                          </span>
                                        </td>
                                        <td className="px-3.5 py-2.5 text-slate-700 dark:text-slate-200 max-w-md">
                                          {row.description}
                                        </td>
                                        <td className="px-3.5 py-2.5 text-center">
                                          {row.found ? (
                                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800/60">
                                              <Check className="w-3 h-3 text-emerald-600" />
                                              Sí
                                            </span>
                                          ) : (
                                            <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-100/80 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-200/80 dark:border-amber-800/60">
                                              <X className="w-3 h-3 text-amber-600" />
                                              No
                                            </span>
                                          )}
                                        </td>
                                        <td className="px-3.5 py-2.5 text-right font-mono font-bold text-slate-900 dark:text-white">
                                          {row.quantity}
                                        </td>
                                        <td className="px-3.5 py-2.5 font-medium text-slate-600 dark:text-slate-300">
                                          {row.sheets_display || '-'}
                                        </td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {/* SECCIÓN DETALLADA DE INVENTARIO TÉCNICO Y NORMAS */}
                      <div className="pt-4 border-t border-slate-200 dark:border-slate-800 space-y-3">
                        <div className="flex items-center justify-between flex-wrap gap-2">
                          <div>
                            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-white">
                              Inventario Técnico Detallado (Catálogo Canónico y Trazabilidad)
                            </h4>
                            <p className="text-[11px] text-slate-500">
                              Detalle por plantilla técnica, normas de ingeniería, recortes y filtros avanzados.
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Tarjetas de Métricas de Cobertura */}
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        <div className="p-3.5 rounded-xl border border-emerald-200 dark:border-emerald-900/50 bg-emerald-50/40 dark:bg-emerald-950/20">
                          <span className="text-[11px] font-bold uppercase text-emerald-700 dark:text-emerald-300">
                            Cob. Productiva
                          </span>
                          <p className="text-xl font-black text-emerald-900 dark:text-emerald-100 mt-1">
                            {((metrics.production_coverage || 0) * 100).toFixed(1)}%
                          </p>
                          <span className="text-[10px] text-emerald-600 dark:text-emerald-400">
                            {metrics.recognized_production || 0} ocurrencias
                          </span>
                        </div>

                        <div className="p-3.5 rounded-xl border border-amber-200 dark:border-amber-900/50 bg-amber-50/40 dark:bg-amber-950/20">
                          <span className="text-[11px] font-bold uppercase text-amber-700 dark:text-amber-300">
                            Cob. Sandbox
                          </span>
                          <p className="text-xl font-black text-amber-900 dark:text-amber-100 mt-1">
                            {((metrics.sandbox_coverage || 0) * 100).toFixed(1)}%
                          </p>
                          <span className="text-[10px] text-amber-600 dark:text-amber-400">
                            {metrics.recognized_sandbox || 0} ocurrencias
                          </span>
                        </div>

                        <div className="p-3.5 rounded-xl border border-rose-200 dark:border-rose-900/50 bg-rose-50/40 dark:bg-rose-950/20">
                          <span className="text-[11px] font-bold uppercase text-rose-700 dark:text-rose-300">
                            Tasa Desconocidos
                          </span>
                          <p className="text-xl font-black text-rose-900 dark:text-rose-100 mt-1">
                            {((metrics.unknown_rate || 0) * 100).toFixed(1)}%
                          </p>
                          <span className="text-[10px] text-rose-600 dark:text-rose-400">
                            {metrics.unknown || 0} sin catálogo
                          </span>
                        </div>

                        <div className="p-3.5 rounded-xl border border-blue-200 dark:border-blue-900/50 bg-blue-50/40 dark:bg-blue-950/20">
                          <span className="text-[11px] font-bold uppercase text-blue-700 dark:text-blue-300">
                            Ocurrencias Totales
                          </span>
                          <p className="text-xl font-black text-blue-900 dark:text-blue-100 mt-1">
                            {metrics.valid_symbol_occurrences || 0}
                          </p>
                          <span className="text-[10px] text-blue-600 dark:text-blue-400">
                            {metrics.inventory_groups || 0} grupos canónicos
                          </span>
                        </div>
                      </div>

                      {/* Barra de Versión y Filtros de la Tabla */}
                      <div className="flex items-center justify-between flex-wrap gap-2 pt-1">
                        <div className="flex items-center gap-1.5 text-xs font-semibold">
                          {(['all', 'production', 'sandbox', 'unknown', 'excluded'] as const).map((flt) => (
                            <button
                              key={flt}
                              type="button"
                              onClick={() => setInventoryFilter(flt)}
                              className={`px-3 py-1 rounded-lg transition-colors ${
                                inventoryFilter === flt
                                  ? 'bg-blue-600 text-white font-bold'
                                  : 'bg-slate-100 hover:bg-slate-200 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-300'
                              }`}
                            >
                              {flt === 'all' ? 'Todos los Grupos' :
                               flt === 'production' ? 'Productivos' :
                               flt === 'sandbox' ? 'Sandbox' :
                               flt === 'unknown' ? 'Desconocidos' : 'Excluidos'}
                            </button>
                          ))}
                        </div>

                        <div className="flex items-center gap-2">
                          {inventory.inventory_version && (
                            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
                              Versión: {inventory.inventory_version}
                            </span>
                          )}
                          <button
                            type="button"
                            onClick={handleRegenerateInventory}
                            disabled={isRegeneratingInventory}
                            className="px-2.5 py-1 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white flex items-center gap-1 rounded bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 transition-colors disabled:opacity-50"
                          >
                            <RefreshCw className={`w-3.5 h-3.5 ${isRegeneratingInventory ? 'animate-spin' : ''}`} />
                            {isRegeneratingInventory ? 'Recalculando...' : 'Recalcular'}
                          </button>
                        </div>
                      </div>

                      {/* Tabla 1: Inventario Consolidado */}
                      <div className="border border-slate-200 dark:border-slate-800 rounded-xl overflow-hidden bg-white dark:bg-slate-900">
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-xs">
                            <thead className="bg-slate-50 dark:bg-slate-950/60 border-b border-slate-200 dark:border-slate-800 text-[11px] font-bold uppercase text-slate-500">
                              <tr>
                                <th className="px-4 py-3">Código</th>
                                <th className="px-4 py-3">Identidad & Función Técnica</th>
                                <th className="px-4 py-3">Estado Catálogo</th>
                                <th className="px-4 py-3">Norma</th>
                                <th className="px-4 py-3">Conteo Documentos</th>
                                <th className="px-4 py-3 text-right">Total</th>
                                <th className="px-4 py-3 text-right">Confianza</th>
                                <th className="px-4 py-3 text-center">Acción</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
                              {(() => {
                                const allGroups = [
                                  ...groups,
                                  ...(inventoryFilter === 'all' || inventoryFilter === 'excluded' ? excludedGroups : [])
                                ];

                            const filtered = allGroups.filter((g) => {
                              if (inventoryFilter === 'production') return g.catalog_status === 'recognized_production';
                              if (inventoryFilter === 'sandbox') return g.catalog_status === 'recognized_sandbox';
                              if (inventoryFilter === 'unknown') return g.catalog_status === 'unknown_symbol';
                              if (inventoryFilter === 'excluded') return g.catalog_status === 'figure_excluded' || g.catalog_status === 'not_symbol';
                              return true;
                            });

                            if (filtered.length === 0) {
                              return (
                                <tr>
                                  <td colSpan={8} className="px-4 py-8 text-center text-slate-500 italic">
                                    No hay grupos de simbología identificados bajo este filtro.
                                  </td>
                                </tr>
                              );
                            }

                            return filtered.map((g) => {
                              const isProd = g.catalog_status === 'recognized_production';
                              const isSand = g.catalog_status === 'recognized_sandbox';
                              const isUnk = g.catalog_status === 'unknown_symbol';
                              const isAmb = g.catalog_status === 'ambiguous_symbol';

                              return (
                                <tr key={g.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-800/40 transition-colors">
                                  <td className="px-4 py-3 font-mono font-bold text-slate-900 dark:text-white">
                                    <span className="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-xs">
                                      {g.display_code}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 space-y-0.5 max-w-xs">
                                    <div className="font-bold text-slate-900 dark:text-white">
                                      {g.canonical_name || 'Símbolo'}
                                    </div>
                                    <div className="text-[11px] text-slate-500 truncate" title={g.description || g.explanation}>
                                      {g.description || g.explanation || '-'}
                                    </div>
                                  </td>
                                  <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
                                      isProd ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300' :
                                      isSand ? 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300' :
                                      isUnk ? 'bg-rose-100 text-rose-800 dark:bg-rose-950/60 dark:text-rose-300' :
                                      isAmb ? 'bg-purple-100 text-purple-800 dark:bg-purple-950/60 dark:text-purple-300' :
                                      'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300'
                                    }`}>
                                      {g.catalog_status.replace('_', ' ')}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-slate-500 text-[11px]">
                                    {g.standard_reference || '-'}
                                  </td>
                                  <td className="px-4 py-3">
                                    <div className="flex flex-wrap gap-1">
                                      {Object.entries(g.occurrences_by_document || {}).map(([doc, cnt]) => (
                                        <span key={doc} className="px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-[10px] text-slate-600 dark:text-slate-300" title={doc}>
                                          {doc.slice(0, 12)}...: <strong>{cnt}</strong>
                                        </span>
                                      ))}
                                    </div>
                                  </td>
                                  <td className="px-4 py-3 text-right font-black text-slate-900 dark:text-white text-sm">
                                    {g.total_occurrences}
                                  </td>
                                  <td className="px-4 py-3 text-right font-semibold text-slate-600 dark:text-slate-300">
                                    {(((g.confidence_summary?.avg ?? 1.0) * 100)).toFixed(1)}%
                                  </td>
                                  <td className="px-4 py-3 text-center">
                                    <button
                                      type="button"
                                      onClick={() => handleSelectGroup(g)}
                                      className="px-2.5 py-1 text-xs font-bold rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 dark:bg-blue-950/60 dark:hover:bg-blue-900/80 dark:text-blue-300 inline-flex items-center gap-1 transition-colors"
                                    >
                                      <span>Ver ({g.total_occurrences})</span>
                                      <ChevronRight className="w-3.5 h-3.5" />
                                    </button>
                                  </td>
                                </tr>
                              );
                            });
                          })()}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </>
              )}
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
