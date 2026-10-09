import React, { useState, useEffect, useMemo, useCallback } from 'react';
import {
  X,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  Shapes,
  RefreshCw,
  Tag,
  Check,
  Ban,
  FileText,
  Layers,
  Search,
  ShieldCheck,
  Loader2,
  ExternalLink,
  BookOpen,
  ArrowRight
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  SymbolUnknownResearchCaseItem,
  PromoteResearchCaseRequest,
  DismissResearchCaseRequest
} from '../types';

interface ResearchCasesPanelProps {
  isOpen: boolean;
  onClose: () => void;
  onCaseUpdated?: () => void;
}

type StatusFilter =
  | 'all'
  | 'unknown'
  | 'sources_found'
  | 'proposed_identity'
  | 'human_validated'
  | 'unresolved'
  | 'research_exhausted';

export const ResearchCasesPanel: React.FC<ResearchCasesPanelProps> = ({
  isOpen,
  onClose,
  onCaseUpdated
}) => {
  // 1. Estados Principales
  const [cases, setCases] = useState<SymbolUnknownResearchCaseItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // 2. Filtros y Búsqueda
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // 3. Estado de IA en ejecución
  const [runningAiId, setRunningAiId] = useState<string | null>(null);

  // 4. Modal / Sub-formulario de Promoción HITL
  const [promotingCase, setPromotingCase] = useState<SymbolUnknownResearchCaseItem | null>(null);
  const [promoteForm, setPromoteForm] = useState<{
    canonical_code: string;
    canonical_name: string;
    category: string;
    subcategory: string;
    discipline: string;
    standard_reference: string;
    evidence_kind: 'redacted_real' | 'real_authorized';
    reviewer_id: string;
    rationale: string;
    notes: string;
  }>({
    canonical_code: '',
    canonical_name: '',
    category: 'valve',
    subcategory: 'gate_valve',
    discipline: 'piping',
    standard_reference: 'PIP PNC00001',
    evidence_kind: 'redacted_real',
    reviewer_id: 'auditor_lead',
    rationale: 'Validado por auditor humano tras investigación técnica',
    notes: ''
  });
  const [promotingSubmitting, setPromotingSubmitting] = useState<boolean>(false);

  // 5. Modal / Sub-formulario de Descarte
  const [dismissingCase, setDismissingCase] = useState<SymbolUnknownResearchCaseItem | null>(null);
  const [dismissForm, setDismissForm] = useState<{
    reviewer_id: string;
    rationale: string;
  }>({
    reviewer_id: 'auditor_lead',
    rationale: ''
  });
  const [dismissingSubmitting, setDismissingSubmitting] = useState<boolean>(false);

  // 6. Carga de Casos
  const loadCases = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.listResearchCases(
        statusFilter === 'all' ? undefined : statusFilter,
        100
      );
      setCases(data || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Error cargando casos de investigación.');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  // Cargar al abrir o al cambiar de filtro
  useEffect(() => {
    if (isOpen) {
      loadCases();
    }
  }, [isOpen, loadCases]);

  // Limpiar mensajes temporales
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 5000);
      return () => clearTimeout(timer);
    }
  }, [successMessage]);

  // 7. Filtrado en Memoria por Búsqueda
  const filteredCases = useMemo(() => {
    if (!searchQuery.trim()) return cases;
    const q = searchQuery.toLowerCase().trim();
    return cases.filter((c) => {
      const name = (c.proposed_name || '').toLowerCase();
      const std = (c.proposed_standard_reference || '').toLowerCase();
      const tag = (c.detected_tag_or_code || '').toLowerCase();
      const doc = (c.document_filename || '').toLowerCase();
      const notes = (c.research_notes || '').toLowerCase();
      const sheet = (c.sheet_label || '').toLowerCase();
      return (
        name.includes(q) ||
        std.includes(q) ||
        tag.includes(q) ||
        doc.includes(q) ||
        notes.includes(q) ||
        sheet.includes(q)
      );
    });
  }, [cases, searchQuery]);

  // Conteo por estado para los badges de las pestañas
  const countsByStatus = useMemo(() => {
    const map: Record<string, number> = {
      all: cases.length,
      unknown: 0,
      sources_found: 0,
      proposed_identity: 0,
      human_validated: 0,
      unresolved: 0,
      research_exhausted: 0
    };
    cases.forEach((c) => {
      if (map[c.status] !== undefined) {
        map[c.status] += 1;
      }
    });
    return map;
  }, [cases]);

  // 8. Manejo de Acción: Ejecutar Investigación IA
  const handleRunAi = async (c: SymbolUnknownResearchCaseItem) => {
    try {
      setRunningAiId(c.id);
      setError(null);
      const updated = await apiService.runAiResearch(c.id);
      setCases((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setSuccessMessage(
        updated.status === 'proposed_identity'
          ? `Investigación IA completada: «${updated.proposed_name}» (${updated.proposed_standard_reference}).`
          : `Investigación finalizada con estado «${updated.status}». ${updated.research_notes || ''}`
      );
      if (onCaseUpdated) onCaseUpdated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Error ejecutando investigación IA.');
    } finally {
      setRunningAiId(null);
    }
  };

  // 9. Abrir Formulario de Promoción
  const handleOpenPromote = (c: SymbolUnknownResearchCaseItem) => {
    setPromotingCase(c);
    const suggestedCode = c.detected_tag_or_code
      ? `PIP-${c.detected_tag_or_code.toUpperCase()}`
      : c.proposed_name
      ? `PIP-${c.proposed_name.toUpperCase().replace(/\s+/g, '-')}`
      : 'PIP-VALVE-UNKNOWN';

    setPromoteForm({
      canonical_code: suggestedCode,
      canonical_name: c.proposed_name || 'Válvula No Identificada',
      category: 'valve',
      subcategory: 'gate_valve',
      discipline: c.discipline || 'piping',
      standard_reference: c.proposed_standard_reference || 'PIP PNC00001',
      evidence_kind: 'redacted_real',
      reviewer_id: 'auditor_lead',
      rationale: `Promoción HITL autorizada desde caso ${c.id}`,
      notes: c.research_notes || ''
    });
  };

  // 10. Confirmar Promoción
  const handleConfirmPromote = async () => {
    if (!promotingCase) return;
    if (!promoteForm.canonical_code.trim()) {
      alert('El código canónico es obligatorio.');
      return;
    }
    if (!promoteForm.canonical_name.trim()) {
      alert('El nombre canónico es obligatorio.');
      return;
    }
    if (!promoteForm.reviewer_id.trim()) {
      alert('El identificador del revisor HITL es obligatorio.');
      return;
    }

    try {
      setPromotingSubmitting(true);
      setError(null);
      const res = await apiService.promoteResearchCase(promotingCase.id, {
        reviewer_id: promoteForm.reviewer_id.trim(),
        canonical_code: promoteForm.canonical_code.trim(),
        canonical_name: promoteForm.canonical_name.trim(),
        category: promoteForm.category,
        subcategory: promoteForm.subcategory,
        discipline: promoteForm.discipline,
        standard_reference: promoteForm.standard_reference || undefined,
        evidence_kind: promoteForm.evidence_kind,
        rationale: promoteForm.rationale || undefined,
        notes: promoteForm.notes || undefined
      });

      setSuccessMessage(
        `¡Símbolo promovido al catálogo! Código: ${res.canonical_code} • Versión: ${res.version_number} • Plantilla ID: ${res.template_id}`
      );
      setPromotingCase(null);
      await loadCases();
      if (onCaseUpdated) onCaseUpdated();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Error promoviendo símbolo a catálogo canónico.');
    } finally {
      setPromotingSubmitting(false);
    }
  };

  // 11. Abrir Formulario de Descarte
  const handleOpenDismiss = (c: SymbolUnknownResearchCaseItem) => {
    setDismissingCase(c);
    setDismissForm({
      reviewer_id: 'auditor_lead',
      rationale: ''
    });
  };

  // 12. Confirmar Descarte
  const handleConfirmDismiss = async () => {
    if (!dismissingCase) return;
    if (!dismissForm.rationale.trim()) {
      alert('Debe indicar la justificación técnica del descarte.');
      return;
    }
    if (!dismissForm.reviewer_id.trim()) {
      alert('El identificador del revisor es obligatorio.');
      return;
    }

    try {
      setDismissingSubmitting(true);
      setError(null);
      const updated = await apiService.dismissResearchCase(dismissingCase.id, {
        reviewer_id: dismissForm.reviewer_id.trim(),
        rationale: dismissForm.rationale.trim()
      });

      setSuccessMessage(`Caso ${updated.id} descartado y marcado como no resuelto.`);
      setDismissingCase(null);
      await loadCases();
      if (onCaseUpdated) onCaseUpdated();
    } catch (err: any) {
      alert(err?.response?.data?.detail || err?.message || 'Error descartando caso de investigación.');
    } finally {
      setDismissingSubmitting(false);
    }
  };

  // 13. Formateo de Estados
  const renderStatusBadge = (status: string) => {
    switch (status) {
      case 'proposed_identity':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-purple-100 text-purple-800 dark:bg-purple-950/70 dark:text-purple-300 border border-purple-200 dark:border-purple-800">
            <Sparkles className="w-3 h-3 text-purple-600 dark:text-purple-400" />
            Propuesta IA Lista
          </span>
        );
      case 'human_validated':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-100 text-emerald-800 dark:bg-emerald-950/70 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
            <CheckCircle2 className="w-3 h-3 text-emerald-600 dark:text-emerald-400" />
            Validado y Promovido
          </span>
        );
      case 'sources_found':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/70 dark:text-amber-300 border border-amber-200 dark:border-amber-800">
            <Layers className="w-3 h-3 text-amber-600 dark:text-amber-400" />
            Análisis en Curso
          </span>
        );
      case 'research_exhausted':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-orange-100 text-orange-800 dark:bg-orange-950/70 dark:text-orange-300 border border-orange-200 dark:border-orange-800">
            <AlertCircle className="w-3 h-3 text-orange-600 dark:text-orange-400" />
            IA No Disponible
          </span>
        );
      case 'unresolved':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-rose-100 text-rose-800 dark:bg-rose-950/70 dark:text-rose-300 border border-rose-200 dark:border-rose-800">
            <Ban className="w-3 h-3 text-rose-600 dark:text-rose-400" />
            Descartado
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-bold bg-sky-100 text-sky-800 dark:bg-sky-950/70 dark:text-sky-300 border border-sky-200 dark:border-sky-800">
            <Shapes className="w-3 h-3 text-sky-600 dark:text-sky-400" />
            Símbolo Desconocido
          </span>
        );
    }
  };

  // REGLA 8 DE ARQUITECTURA: Retorno condicional estricto POSTERIOR a la declaración incondicional de todos los hooks.
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-md p-3 md:p-6 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-7xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh]">
        
        {/* ========================================================= */}
        {/* ENCABEZADO SUPERIOR DEL MODAL */}
        {/* ========================================================= */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-purple-100 dark:bg-purple-950/50 text-purple-700 dark:text-purple-300 border border-purple-200 dark:border-purple-800/60">
              <Sparkles className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-bold text-slate-900 dark:text-white tracking-tight">
                  Consola de Investigación IA & Curación HITL de Símbolos Desconocidos
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-100 dark:bg-purple-950 text-purple-800 dark:text-purple-300 border border-purple-200 dark:border-purple-800 uppercase tracking-wider">
                  ISA-5.1 • PIP PNC00001
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Bandeja de símbolos con geometría física real no reconocidos en el catálogo canónico activo. Diagnóstico multimodal con Claude Vision y promoción gobernada al catálogo.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={loadCases}
              disabled={loading}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-300 dark:border-slate-700 transition"
              title="Actualizar casos desde base de datos"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              <span>Actualizar</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-slate-800 transition"
              title="Cerrar consola"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* NOTIFICACIONES DE FEEDBACK */}
        {successMessage && (
          <div className="mx-6 mt-4 p-3 bg-emerald-50 dark:bg-emerald-950/50 border border-emerald-200 dark:border-emerald-800 text-emerald-800 dark:text-emerald-200 rounded-xl text-xs flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-600 dark:text-emerald-400 shrink-0" />
              <span>{successMessage}</span>
            </div>
            <button
              onClick={() => setSuccessMessage(null)}
              className="text-emerald-600 dark:text-emerald-400 hover:text-emerald-800"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {error && (
          <div className="mx-6 mt-4 p-3 bg-rose-50 dark:bg-rose-950/50 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 rounded-xl text-xs flex items-center justify-between animate-in fade-in">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 dark:text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
            <button
              onClick={() => setError(null)}
              className="text-rose-600 dark:text-rose-400 hover:text-rose-800"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* ========================================================= */}
        {/* BARRA DE FILTROS, PESTAÑAS Y BÚSQUEDA */}
        {/* ========================================================= */}
        <div className="px-6 py-3 border-b border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 flex flex-col md:flex-row md:items-center justify-between gap-3">
          {/* Pestañas de estado */}
          <div className="flex items-center gap-1 overflow-x-auto pb-1 md:pb-0 scrollbar-thin">
            {[
              { id: 'all', label: 'Todos' },
              { id: 'unknown', label: 'Desconocidos' },
              { id: 'proposed_identity', label: 'Propuesta IA' },
              { id: 'human_validated', label: 'Validados' },
              { id: 'research_exhausted', label: 'IA No Disp.' },
              { id: 'unresolved', label: 'Descartados' }
            ].map((tab) => {
              const active = statusFilter === tab.id;
              const count = countsByStatus[tab.id] ?? 0;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setStatusFilter(tab.id as StatusFilter)}
                  className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all flex items-center gap-1.5 shrink-0 ${
                    active
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800'
                  }`}
                >
                  <span>{tab.label}</span>
                  <span
                    className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                      active
                        ? 'bg-purple-700/80 text-white'
                        : 'bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300'
                    }`}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* Campo de búsqueda */}
          <div className="relative min-w-[260px]">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar por tag, norma, doc o nota..."
              className="w-full pl-9 pr-8 py-1.5 text-xs rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-purple-500"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* ========================================================= */}
        {/* CUERPO PRINCIPAL: LISTADO DE CASOS DE INVESTIGACIÓN */}
        {/* ========================================================= */}
        <div className="flex-1 overflow-y-auto p-6 bg-slate-50/50 dark:bg-slate-950/40">
          {loading ? (
            <div className="py-20 flex flex-col items-center justify-center text-slate-500">
              <Loader2 className="w-8 h-8 animate-spin text-purple-600 mb-2" />
              <p className="text-sm">Cargando casos de investigación de símbolos...</p>
            </div>
          ) : filteredCases.length === 0 ? (
            <div className="py-16 text-center border-2 border-dashed border-slate-200 dark:border-slate-800 rounded-2xl bg-white dark:bg-slate-900 p-8">
              <Shapes className="w-12 h-12 text-slate-400 mx-auto mb-3" />
              <h3 className="text-sm font-bold text-slate-900 dark:text-white mb-1">
                No hay casos de investigación en esta vista
              </h3>
              <p className="text-xs text-slate-500 dark:text-slate-400 max-w-md mx-auto mb-4">
                {statusFilter !== 'all'
                  ? `No se encontraron símbolos con estado «${statusFilter}». Prueba seleccionando «Todos» o limpiando la búsqueda.`
                  : 'No existen registros de símbolos desconocidos pendientes. Cuando el motor de matching detecte geometría real sin coincidencia en catálogo canónico, se registrarán automáticamente aquí.'}
              </p>
              {statusFilter !== 'all' && (
                <button
                  type="button"
                  onClick={() => setStatusFilter('all')}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
                >
                  Ver todos los casos
                </button>
              )}
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {filteredCases.map((c) => {
                const isAiRunning = runningAiId === c.id;
                const canRunAi =
                  c.status !== 'proposed_identity' &&
                  c.status !== 'human_validated' &&
                  c.status !== 'unresolved';

                return (
                  <div
                    key={c.id}
                    className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-4 shadow-sm hover:border-slate-300 dark:hover:border-slate-700 transition flex flex-col md:flex-row items-start md:items-center justify-between gap-4"
                  >
                    {/* Sección Visual y Metadatos del Símbolo */}
                    <div className="flex items-start gap-4 flex-1 min-w-0">
                      {/* Recorte Visual (con patrón onError idéntico a ReviewRunDetailModal) */}
                      <div className="shrink-0">
                        {c.crop_image_url ? (
                          <div className="w-16 h-16 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-1 flex items-center justify-center overflow-hidden shadow-2xs">
                            <img
                              src={c.crop_image_url}
                              alt={c.proposed_name || 'Recorte de símbolo'}
                              className="w-full h-full object-contain"
                              onError={(e) => {
                                const img = e.currentTarget;
                                img.style.display = 'none';
                                const fallback = img.nextElementSibling as HTMLElement;
                                if (fallback) fallback.style.display = 'flex';
                              }}
                            />
                            <div
                              style={{ display: 'none' }}
                              className="fallback-placeholder w-full h-full items-center justify-center text-slate-400"
                            >
                              <Shapes className="w-6 h-6" />
                            </div>
                          </div>
                        ) : (
                          <div className="w-16 h-16 rounded-xl border border-dashed border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center justify-center text-slate-400">
                            <Shapes className="w-6 h-6" />
                          </div>
                        )}
                      </div>

                      {/* Información Técnica y Contexto */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          {renderStatusBadge(c.status)}
                          
                          {c.detected_tag_or_code && (
                            <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-mono font-bold bg-slate-100 dark:bg-slate-800 text-blue-700 dark:text-blue-300 border border-slate-200 dark:border-slate-700">
                              <Tag className="w-3 h-3" />
                              {c.detected_tag_or_code}
                            </span>
                          )}

                          <span className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
                            ID: <span className="font-mono">{c.id.slice(0, 8)}...</span>
                          </span>
                        </div>

                        {/* Nombre Propuesto / Identidad */}
                        <div className="flex items-baseline gap-2 flex-wrap mb-1">
                          <h4 className="text-sm font-bold text-slate-900 dark:text-white">
                            {c.proposed_name || 'Símbolo Pendiente de Clasificación'}
                          </h4>
                          {c.proposed_standard_reference && (
                            <span className="text-xs font-semibold text-purple-700 dark:text-purple-300 bg-purple-50 dark:bg-purple-950/60 px-2 py-0.2 rounded border border-purple-200 dark:border-purple-800/60">
                              {c.proposed_standard_reference}
                            </span>
                          )}
                        </div>

                        {/* Contexto Documental */}
                        <div className="flex items-center gap-3 text-xs text-slate-500 dark:text-slate-400 flex-wrap mb-2">
                          <span className="flex items-center gap-1">
                            <FileText className="w-3.5 h-3.5" />
                            <span className="truncate max-w-[200px]" title={c.document_filename || ''}>
                              {c.document_filename || 'Doc no especificado'}
                            </span>
                          </span>
                          <span>•</span>
                          <span>{c.sheet_label || 'Lámina no especificada'}</span>
                          <span>•</span>
                          <span className="capitalize">{c.discipline || 'piping'}</span>
                        </div>

                        {/* Notas / Razonamiento de IA */}
                        {c.research_notes && (
                          <div className="p-2 rounded-lg bg-slate-50 dark:bg-slate-800/60 border border-slate-200/80 dark:border-slate-800 text-[11px] text-slate-600 dark:text-slate-300 font-mono whitespace-pre-wrap max-h-24 overflow-y-auto">
                            {c.research_notes}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Botones de Acción */}
                    <div className="flex flex-row md:flex-col items-center md:items-end gap-2 shrink-0 w-full md:w-auto justify-end border-t md:border-t-0 pt-3 md:pt-0 border-slate-100 dark:border-slate-800">
                      {/* 1. Botón Investigar con IA */}
                      {canRunAi && (
                        <button
                          type="button"
                          onClick={() => handleRunAi(c)}
                          disabled={isAiRunning}
                          className="w-full md:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-purple-600 hover:bg-purple-700 text-white shadow-xs transition disabled:opacity-50"
                          title="Consultar a Claude Vision con normas ISA-5.1 y PIP PNC00001"
                        >
                          <Sparkles className={`w-3.5 h-3.5 ${isAiRunning ? 'animate-spin' : ''}`} />
                          <span>{isAiRunning ? 'Analizando...' : 'Investigar con IA'}</span>
                        </button>
                      )}

                      {/* 2. Botón Promover al Catálogo (HITL) */}
                      {c.status !== 'human_validated' && (
                        <button
                          type="button"
                          onClick={() => handleOpenPromote(c)}
                          className="w-full md:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-xs transition"
                          title="Validar y promover al catálogo canónico activo"
                        >
                          <ShieldCheck className="w-3.5 h-3.5" />
                          <span>Validar y Promover</span>
                        </button>
                      )}

                      {/* 3. Botón Descartar */}
                      {c.status !== 'unresolved' && (
                        <button
                          type="button"
                          onClick={() => handleOpenDismiss(c)}
                          className="w-full md:w-auto inline-flex items-center justify-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 transition"
                          title="Descartar caso con justificación técnica"
                        >
                          <Ban className="w-3.5 h-3.5 text-rose-500" />
                          <span>Descartar</span>
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* ========================================================= */}
        {/* PIE DEL PANEL */}
        {/* ========================================================= */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950 flex items-center justify-between text-xs text-slate-500">
          <span>
            Mostrando <b>{filteredCases.length}</b> de <b>{cases.length}</b> casos registrados
          </span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 font-semibold transition"
          >
            Cerrar Consola
          </button>
        </div>

        {/* ========================================================= */}
        {/* MODAL SECUNDARIO: FORMULARIO DE PROMOCIÓN AL CATÁLOGO */}
        {/* ========================================================= */}
        {promotingCase && (
          <div
            className="fixed inset-0 z-60 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in"
            role="dialog"
            aria-modal="true"
          >
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Promover Símbolo al Catálogo Canónico
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setPromotingCase(null)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="flex flex-col gap-3 max-h-[65vh] overflow-y-auto pr-1">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Código Canónico <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={promoteForm.canonical_code}
                    onChange={(e) => setPromoteForm({ ...promoteForm, canonical_code: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 font-mono text-slate-900 dark:text-slate-100"
                    placeholder="Ej. PIP-VALVE-GATE"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Nombre Canónico <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={promoteForm.canonical_name}
                    onChange={(e) => setPromoteForm({ ...promoteForm, canonical_name: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    placeholder="Ej. Válvula de Compuerta"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Categoría
                    </label>
                    <input
                      type="text"
                      value={promoteForm.category}
                      onChange={(e) => setPromoteForm({ ...promoteForm, category: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Subcategoría
                    </label>
                    <input
                      type="text"
                      value={promoteForm.subcategory}
                      onChange={(e) => setPromoteForm({ ...promoteForm, subcategory: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Disciplina
                    </label>
                    <input
                      type="text"
                      value={promoteForm.discipline}
                      onChange={(e) => setPromoteForm({ ...promoteForm, discipline: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Norma de Referencia
                    </label>
                    <input
                      type="text"
                      value={promoteForm.standard_reference}
                      onChange={(e) => setPromoteForm({ ...promoteForm, standard_reference: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      Tipo de Evidencia <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={promoteForm.evidence_kind}
                      onChange={(e) =>
                        setPromoteForm({
                          ...promoteForm,
                          evidence_kind: e.target.value as 'redacted_real' | 'real_authorized'
                        })
                      }
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    >
                      <option value="redacted_real">redacted_real (Leyenda/Plano Real)</option>
                      <option value="real_authorized">real_authorized (Norma Autorizada)</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                      ID Revisor HITL <span className="text-rose-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={promoteForm.reviewer_id}
                      onChange={(e) => setPromoteForm({ ...promoteForm, reviewer_id: e.target.value })}
                      className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Justificación de Promoción
                  </label>
                  <textarea
                    rows={2}
                    value={promoteForm.rationale}
                    onChange={(e) => setPromoteForm({ ...promoteForm, rationale: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setPromotingCase(null)}
                  disabled={promotingSubmitting}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleConfirmPromote}
                  disabled={promotingSubmitting}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm transition disabled:opacity-50"
                >
                  {promotingSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Promoviendo...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Confirmar Promoción Productiva</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* MODAL SECUNDARIO: FORMULARIO DE DESCARTE DE CASO */}
        {/* ========================================================= */}
        {dismissingCase && (
          <div
            className="fixed inset-0 z-60 flex items-center justify-center bg-slate-950/80 backdrop-blur-xs p-4 animate-in fade-in"
            role="dialog"
            aria-modal="true"
          >
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl flex flex-col gap-4">
              <div className="flex items-center justify-between border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Ban className="w-5 h-5 text-rose-500" />
                  <h3 className="text-base font-bold text-slate-900 dark:text-white">
                    Descartar Caso de Investigación
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setDismissingCase(null)}
                  className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <p className="text-xs text-slate-500 dark:text-slate-400">
                El caso quedará registrado como no resuelto (<code>unresolved</code>) con trazabilidad inmutable del motivo de auditoría.
              </p>

              <div className="flex flex-col gap-3">
                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    ID Revisor <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={dismissForm.reviewer_id}
                    onChange={(e) => setDismissForm({ ...dismissForm, reviewer_id: e.target.value })}
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 dark:text-slate-300 mb-1">
                    Motivo / Justificación Técnica <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={3}
                    value={dismissForm.rationale}
                    onChange={(e) => setDismissForm({ ...dismissForm, rationale: e.target.value })}
                    placeholder="Ej. Artefacto de dibujo / Logo de plano / Geometría no normativa descartada."
                    className="w-full px-3 py-1.5 text-xs rounded-lg border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-800 text-slate-900 dark:text-slate-100"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-100 dark:border-slate-800">
                <button
                  type="button"
                  onClick={() => setDismissingCase(null)}
                  disabled={dismissingSubmitting}
                  className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleConfirmDismiss}
                  disabled={dismissingSubmitting}
                  className="inline-flex items-center gap-1.5 px-4 py-1.5 text-xs font-bold rounded-lg bg-rose-600 hover:bg-rose-700 text-white shadow-sm transition disabled:opacity-50"
                >
                  {dismissingSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Descartando...</span>
                    </>
                  ) : (
                    <>
                      <Ban className="w-3.5 h-3.5" />
                      <span>Confirmar Descarte</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
};
