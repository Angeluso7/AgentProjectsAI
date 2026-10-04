import React, { useState, useEffect } from 'react';
import {
  X, Check, Trash2, Edit3, ShieldAlert, Sparkles, BookOpen,
  Filter, Layers, CheckCircle2, AlertCircle, Clock, Eye,
  Maximize2, ArrowRight, Database, HelpCircle, ShieldCheck,
  ShieldX, Ban, AlertTriangle, Compass, Merge, Split,
  Share2, Tag, FileText, ChevronRight, BookmarkCheck, Search,
  RefreshCw, CheckSquare, Square, ExternalLink, SlidersHorizontal
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  CandidateCurationDetail, DeduplicationCluster, CanonicalCatalogResponse, SymbolOccurrenceItem
} from '../types';
import { ItemContextViewerModal } from './ItemContextViewerModal';

interface SymbolCurationStudioModalProps {
  isOpen: boolean;
  extractionId?: string | null;
  ruleDocumentId?: string | null;
  initialFamily?: string;
  onClose: () => void;
  onPromoted?: () => void;
}

export const SymbolCurationStudioModal: React.FC<SymbolCurationStudioModalProps> = ({
  isOpen,
  extractionId,
  ruleDocumentId,
  initialFamily,
  onClose,
  onPromoted
}) => {
  const [activeTab, setActiveTab] = useState<'candidates' | 'canonical_catalog'>('candidates');
  const [candidates, setCandidates] = useState<CandidateCurationDetail[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  // Filtros
  const [searchQuery, setSearchQuery] = useState('');
  const [familyFilter, setFamilyFilter] = useState(initialFamily || 'all');
  const [renderModeFilter, setRenderModeFilter] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');

  // Selección múltiple
  const [selectedIds, setSelectedIds] = useState<string[]>([]);

  // Edición Inline / Modal
  const [editingSym, setEditingSym] = useState<CandidateCurationDetail | null>(null);
  const [editName, setEditName] = useState('');
  const [editFamily, setEditFamily] = useState('valves');
  const [editStandard, setEditStandard] = useState('ISA-5.1');
  const [editCategory, setEditCategory] = useState('');
  const [editNotes, setEditNotes] = useState('');

  // Deduplicación
  const [dedupRunning, setDedupRunning] = useState(false);
  const [dedupClusters, setDedupClusters] = useState<DeduplicationCluster[]>([]);
  const [showDedupDrawer, setShowDedupDrawer] = useState(false);

  // Fusión de variantes
  const [mergingSym, setMergingSym] = useState<CandidateCurationDetail | null>(null);
  const [targetGroupId, setTargetGroupId] = useState('');

  // Promoción
  const [promoting, setPromoting] = useState(false);
  const [libraryName, setLibraryName] = useState('ISA-5.1 Piping Library');
  const [userNotes, setUserNotes] = useState('');

  // Catálogo canónico
  const [catalog, setCatalog] = useState<CanonicalCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);

  // Lightbox Zoom
  const [lightboxImg, setLightboxImg] = useState<{ src: string; title: string } | null>(null);

  // Visor Contextual Interactivo de Lámina con BBox Enfocado
  const [viewerTarget, setViewerTarget] = useState<{
    item: any;
    extractionId?: string | null;
  } | null>(null);

  const handleOpenOccurrence = (sym: CandidateCurationDetail, occ: SymbolOccurrenceItem) => {
    setViewerTarget({
      extractionId: sym.extraction_id || extractionId || null,
      item: {
        id: sym.extracted_item_id,
        title: sym.symbol_name,
        page_number: occ.page_number,
        bbox_normalized: occ.bbox_normalized && occ.bbox_normalized.length === 4 ? occ.bbox_normalized : (sym.cell_bbox || []),
        crop_image_path: occ.crop_image_path || sym.crop_image_path,
        content_text: sym.ocr_associated_text || sym.symbol_name,
        description: sym.symbol_name,
        item_type: 'symbol',
        discipline: sym.discipline,
        review_status: sym.review_status,
        source_asset_id: occ.sheet_id,
        extraction_id: sym.extraction_id || extractionId || null,
        metadata_payload: {
          source_table_id: sym.source_table_id,
          row_index: sym.row_index,
          col_index: sym.col_index,
          cell_bbox: sym.cell_bbox,
          row_bbox: sym.row_bbox,
          occurrences: sym.occurrences,
        }
      }
    });
  };

  useEffect(() => {
    if (isOpen) {
      loadCandidates();
      loadCatalog();
    }
  }, [isOpen, extractionId, ruleDocumentId, familyFilter, renderModeFilter, statusFilter]);

  const loadCandidates = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiService.listCurationCandidates({
        extraction_id: extractionId || undefined,
        rule_document_id: ruleDocumentId || undefined,
        family: familyFilter !== 'all' ? familyFilter : undefined,
        render_mode: renderModeFilter !== 'all' ? renderModeFilter : undefined,
        review_status: statusFilter !== 'all' ? statusFilter : undefined,
        search: searchQuery || undefined,
        limit: 150
      });
      setCandidates(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error cargando candidatos para curación.');
    } finally {
      setLoading(false);
    }
  };

  const loadCatalog = async () => {
    try {
      setCatalogLoading(true);
      const data = await apiService.getCanonicalSymbolCatalog(libraryName, 'piping');
      setCatalog(data);
    } catch (err) {
      console.error('Error cargando catálogo canónico:', err);
    } finally {
      setCatalogLoading(false);
    }
  };

  const notifySuccess = (msg: string) => {
    setActionSuccess(msg);
    setTimeout(() => setActionSuccess(null), 3500);
  };

  // 1. Acciones Rápidas: Aprobar, Rechazar, Falso Positivo
  const handleCurateSingle = async (sym: CandidateCurationDetail, action: 'accept' | 'reject' | 'flag_false_positive') => {
    try {
      await apiService.curateSymbolsBatch({
        symbol_ids: [sym.id],
        action,
        reviewer: 'Ingeniero Revisor Piping'
      });
      notifySuccess(`Símbolo «${sym.symbol_name}» ${action === 'accept' ? 'aprobado' : action === 'reject' ? 'rechazado' : 'marcado como falso positivo'}.`);
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al ejecutar curación.');
    }
  };

  // 2. Curación en Lote
  const handleBatchCurate = async (action: 'accept' | 'reject' | 'flag_false_positive') => {
    if (selectedIds.length === 0) return;
    try {
      await apiService.curateSymbolsBatch({
        symbol_ids: selectedIds,
        action,
        reviewer: 'Ingeniero Revisor Piping'
      });
      notifySuccess(`${selectedIds.length} símbolos actualizados con acción: ${action}.`);
      setSelectedIds([]);
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error en curación masiva.');
    }
  };

  // 3. Abrir Edición de Símbolo
  const handleOpenEdit = (sym: CandidateCurationDetail) => {
    setEditingSym(sym);
    setEditName(sym.symbol_name);
    setEditFamily(sym.canonical_symbol_family);
    setEditStandard(sym.standard_reference || 'ISA-5.1');
    setEditCategory(sym.category || '');
    setEditNotes(sym.human_validation_notes || '');
  };

  const handleSaveEdit = async () => {
    if (!editingSym) return;
    try {
      await apiService.updateStructuredSymbol(editingSym.id, {
        symbol_name: editName,
        canonical_symbol_family: editFamily,
        standard_reference: editStandard,
        category: editCategory,
        human_validation_notes: editNotes
      });
      notifySuccess(`Candidato «${editName}» guardado y sincronizado.`);
      setEditingSym(null);
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error actualizando candidato.');
    }
  };

  // 4. Ejecutar Deduplicación Inteligente
  const handleRunDeduplication = async () => {
    try {
      setDedupRunning(true);
      const res = await apiService.deduplicateSymbols({
        extraction_id: extractionId || undefined,
        canonical_symbol_family: familyFilter !== 'all' ? familyFilter : undefined,
        visual_threshold: 0.85,
        semantic_threshold: 0.75
      });
      setDedupClusters(res.clusters);
      setShowDedupDrawer(true);
      notifySuccess(`Deduplicación completada: ${res.duplicates_detected} duplicados y ${res.clusters_count} clusters de variantes.`);
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error ejecutando deduplicación.');
    } finally {
      setDedupRunning(false);
    }
  };

  // 5. Fusión / Separación de Variantes
  const handleMergeVariant = async () => {
    if (!mergingSym || !targetGroupId) return;
    try {
      await apiService.mergeSymbolVariant(mergingSym.id, targetGroupId);
      notifySuccess(`Símbolo fusionado a la variante ${targetGroupId}.`);
      setMergingSym(null);
      setTargetGroupId('');
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error fusionando variante.');
    }
  };

  const handleSplitVariant = async (sym: CandidateCurationDetail) => {
    try {
      const res = await apiService.splitSymbolVariant(sym.id);
      notifySuccess(`Símbolo separado con éxito en nuevo grupo ${res.new_group_id}.`);
      loadCandidates();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error separando variante.');
    }
  };

  // 6. Promoción Controlada a SymbolTemplate
  const handlePromoteSingle = async (sym: CandidateCurationDetail) => {
    try {
      setPromoting(true);
      await apiService.promoteSymbolToTemplate({
        structured_symbol_id: sym.id,
        library_name: libraryName,
        discipline: sym.discipline || 'piping',
        reviewer: 'Ingeniero Revisor Piping (HITL)',
        user_notes: userNotes || 'Aprobado en revisión técnica Fase 2'
      });
      notifySuccess(`Símbolo «${sym.symbol_name}» promovido a ${libraryName}.`);
      loadCandidates();
      loadCatalog();
      if (onPromoted) onPromoted();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al promover símbolo.');
    } finally {
      setPromoting(false);
    }
  };

  const handlePromoteBatch = async () => {
    if (selectedIds.length === 0) return;
    try {
      setPromoting(true);
      const res = await apiService.promoteSymbolsBatch({
        structured_symbol_ids: selectedIds,
        library_name: libraryName,
        discipline: 'piping',
        reviewer: 'Ingeniero Revisor Piping (HITL Lote)',
        user_notes: userNotes || 'Lote canónico aprobado en Fase 2'
      });
      notifySuccess(res.message);
      setSelectedIds([]);
      loadCandidates();
      loadCatalog();
      if (onPromoted) onPromoted();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error en promoción por lote.');
    } finally {
      setPromoting(false);
    }
  };

  // Toggle Selección
  const toggleSelectAll = () => {
    if (selectedIds.length === candidates.length) {
      setSelectedIds([]);
    } else {
      setSelectedIds(candidates.map((c) => c.id));
    }
  };

  const toggleSelectOne = (id: string) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-md p-3 md:p-6 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-7xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[95vh]">
        
        {/* Encabezado Superior */}
        <div className="px-6 py-4 border-b border-slate-800 bg-slate-950/90 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center space-x-3">
            <div className="p-2.5 rounded-xl bg-purple-600/20 text-purple-400 border border-purple-500/30">
              <Compass className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-lg font-black text-white tracking-tight">
                  Estudio de Curación y Validación HITL de Simbología
                </h2>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-purple-950 text-purple-300 border border-purple-800 uppercase tracking-wider">
                  Fase 2 • ISA-5.1 / ASME B16.34
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Revisión humana, deduplicación visual-semántica (dHash + ontología) y promoción controlada a template_memory.
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Pestañas de Alternancia */}
            <div className="flex rounded-lg bg-slate-800/80 p-0.5 border border-slate-700">
              <button
                type="button"
                onClick={() => setActiveTab('candidates')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                  activeTab === 'candidates'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Candidatos ({candidates.length})
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('canonical_catalog')}
                className={`px-3 py-1.5 text-xs font-bold rounded-md transition-all ${
                  activeTab === 'canonical_catalog'
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Catálogo Canónico ({catalog?.total_templates || 0})
              </button>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-2 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Notificación Flotante */}
        {actionSuccess && (
          <div className="px-6 py-2 bg-emerald-950/80 border-b border-emerald-800/60 text-xs font-semibold text-emerald-300 flex items-center justify-between animate-in slide-in-from-top-1">
            <span className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              {actionSuccess}
            </span>
            <button onClick={() => setActionSuccess(null)} className="text-emerald-400 hover:text-white">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Vista 1: Candidatos y Curación HITL */}
        {activeTab === 'candidates' && (
          <div className="flex-1 flex flex-col min-h-0">
            
            {/* Barra de Filtros y Acciones Globales */}
            <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-950/40 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 flex-wrap flex-1 min-w-[280px]">
                {/* Búsqueda */}
                <div className="relative flex-1 min-w-[180px] max-w-xs">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Buscar símbolo, código u OCR..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && loadCandidates()}
                    className="w-full bg-slate-800/80 border border-slate-700/80 rounded-lg pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-400 focus:outline-none focus:border-purple-500"
                  />
                </div>

                {/* Filtro Familia */}
                <select
                  value={familyFilter}
                  onChange={(e) => setFamilyFilter(e.target.value)}
                  className="bg-slate-800/80 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-purple-500"
                >
                  <option value="all">Todas las familias</option>
                  <option value="valves">Válvulas (valves)</option>
                  <option value="instruments">Instrumentación (instruments)</option>
                  <option value="fittings">Accesorios (fittings)</option>
                  <option value="equipment">Equipos (equipment)</option>
                  <option value="line_types">Tipos de Línea (line_types)</option>
                </select>

                {/* Filtro Modo Render */}
                <select
                  value={renderModeFilter}
                  onChange={(e) => setRenderModeFilter(e.target.value)}
                  className="bg-slate-800/80 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-purple-500"
                >
                  <option value="all">Todo modo origen</option>
                  <option value="vector">Vectorial (get_drawings)</option>
                  <option value="raster">Raster (Otsu/Morfología)</option>
                  <option value="mixed">Mixto</option>
                </select>

                {/* Filtro Estado Revisión */}
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="bg-slate-800/80 border border-slate-700 text-xs text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-purple-500"
                >
                  <option value="all">Todos los estados</option>
                  <option value="pending">Por Revisar</option>
                  <option value="accepted">Aprobados</option>
                  <option value="rejected">Rechazados</option>
                  <option value="flagged_false_positive">Falsos Positivos</option>
                </select>
              </div>

              {/* Botones de Acción Masiva */}
              <div className="flex items-center gap-2 flex-wrap">
                {/* Deduplicación Inteligente */}
                <button
                  type="button"
                  onClick={handleRunDeduplication}
                  disabled={dedupRunning}
                  className="px-3 py-1.5 text-xs font-bold rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-sm flex items-center gap-1.5 transition-all disabled:opacity-50"
                  title="Ejecutar análisis dHash + semántico para agrupar duplicados y variantes"
                >
                  {dedupRunning ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5 text-indigo-200" />}
                  <span>Deduplicar Variantes</span>
                </button>

                {/* Acciones para Seleccionados */}
                {selectedIds.length > 0 && (
                  <div className="flex items-center gap-1.5 pl-2 border-l border-slate-800">
                    <span className="text-[11px] font-bold text-purple-300">
                      {selectedIds.length} seleccionados:
                    </span>
                    <button
                      type="button"
                      onClick={() => handleBatchCurate('accept')}
                      className="px-2 py-1 text-xs font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800 hover:bg-emerald-900"
                    >
                      Aprobar
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBatchCurate('reject')}
                      className="px-2 py-1 text-xs font-bold rounded bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700"
                    >
                      Rechazar
                    </button>
                    <button
                      type="button"
                      onClick={() => handleBatchCurate('flag_false_positive')}
                      className="px-2 py-1 text-xs font-bold rounded bg-rose-950 text-rose-300 border border-rose-800 hover:bg-rose-900"
                    >
                      Falso Positivo
                    </button>
                    <button
                      type="button"
                      onClick={handlePromoteBatch}
                      disabled={promoting}
                      className="px-2.5 py-1 text-xs font-bold rounded bg-purple-600 hover:bg-purple-500 text-white shadow flex items-center gap-1"
                    >
                      <BookmarkCheck className="w-3 h-3" />
                      Promover ({selectedIds.length})
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Listado Principal de Candidatos (Grilla / Tabla con las 9 Evidencias) */}
            <div className="p-6 overflow-y-auto flex-1 space-y-3.5 max-h-[calc(95vh-180px)]">
              {error && (
                <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {loading ? (
                <div className="p-16 text-center text-slate-400 text-sm flex flex-col items-center justify-center gap-3">
                  <RefreshCw className="w-8 h-8 text-purple-400 animate-spin" />
                  <span>Cargando candidatos con evidencia perceptual y estructural...</span>
                </div>
              ) : candidates.length === 0 ? (
                <div className="p-16 text-center text-slate-500 text-sm">
                  No se encontraron candidatos para los filtros seleccionados.
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                    <button
                      type="button"
                      onClick={toggleSelectAll}
                      className="flex items-center gap-1.5 text-xs font-semibold text-slate-300 hover:text-white"
                    >
                      {selectedIds.length === candidates.length ? (
                        <CheckSquare className="w-4 h-4 text-purple-400" />
                      ) : (
                        <Square className="w-4 h-4 text-slate-500" />
                      )}
                      <span>Seleccionar Todos ({candidates.length})</span>
                    </button>
                    <span className="text-[11px] text-slate-500">
                      Mostrando candidatos ordenados por fecha y confianza
                    </span>
                  </div>

                  {candidates.map((sym) => {
                    const isSelected = selectedIds.includes(sym.id);
                    const isApproved = sym.review_status === 'accepted';
                    const isRejected = sym.review_status === 'rejected';
                    const isFalsePositive = sym.review_status === 'flagged_false_positive';

                    return (
                      <div
                        key={sym.id}
                        className={`p-4 rounded-xl border transition-all ${
                          isSelected
                            ? 'bg-purple-950/20 border-purple-600/70 shadow-md shadow-purple-950/30'
                            : isApproved
                            ? 'bg-slate-900/90 border-emerald-800/40'
                            : isRejected
                            ? 'bg-slate-950/40 border-slate-800 opacity-60'
                            : isFalsePositive
                            ? 'bg-rose-950/20 border-rose-800/50'
                            : 'bg-slate-900/90 border-slate-800 hover:border-slate-700'
                        }`}
                      >
                        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
                          
                          {/* Columna 1: Checkbox + Recorte Visual (Evidence 1: Crop) */}
                          <div className="flex items-center gap-3 shrink-0">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectOne(sym.id)}
                              className="w-4 h-4 rounded bg-slate-800 border-slate-700 text-purple-600 focus:ring-purple-500"
                            />

                            <div
                              onClick={() => sym.crop_image_path && setLightboxImg({ src: sym.crop_image_path, title: sym.symbol_name })}
                              className="relative group cursor-zoom-in w-24 h-20 bg-slate-950 rounded-lg border border-slate-750 flex items-center justify-center p-1 overflow-hidden"
                              title="Click para ampliar evidencia visual (Lightbox)"
                            >
                              {sym.crop_image_path ? (
                                <img
                                  src={sym.crop_image_path.startsWith('http') || sym.crop_image_path.startsWith('data:') ? sym.crop_image_path : (sym.crop_image_path.startsWith('/') ? sym.crop_image_path : `/${sym.crop_image_path}`)}
                                  alt={sym.symbol_name}
                                  className="max-h-full max-w-full object-contain transition-transform group-hover:scale-110"
                                />
                              ) : (
                                <div className="text-[10px] text-slate-600 font-mono">Sin Crop</div>
                              )}
                              <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center text-cyan-300 transition-opacity">
                                <Maximize2 className="w-3.5 h-3.5" />
                              </div>
                            </div>
                          </div>

                          {/* Columna 2: Evidencias y Metadatos Clave (Evidencias 2 a 9) */}
                          <div className="flex-1 min-w-0 space-y-1.5">
                            <div className="flex items-center gap-2 flex-wrap">
                              {/* Nombre Técnico */}
                              <h4 className="text-sm font-black text-slate-100">
                                {sym.symbol_name}
                              </h4>

                              {/* Familia Canónica */}
                              <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                                {sym.canonical_symbol_family.toUpperCase()}
                              </span>

                              {/* Modo Origen (Evidence 6: render_mode) */}
                              <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border ${
                                sym.source_render_mode === 'vector'
                                  ? 'bg-sky-950 text-sky-300 border-sky-800'
                                  : sym.source_render_mode === 'raster'
                                  ? 'bg-amber-950 text-amber-300 border-amber-800'
                                  : 'bg-indigo-950 text-indigo-300 border-indigo-800'
                              }`}>
                                {sym.source_render_mode.toUpperCase()}
                              </span>

                              {/* Confianza (Evidence 7: score) */}
                              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700">
                                Conf: {Math.round((sym.confidence_score || 0) * 100)}%
                              </span>

                              {/* Estado de Revisión */}
                              {isApproved ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800 flex items-center gap-1">
                                  <Check className="w-3 h-3" /> Aprobado
                                </span>
                              ) : isRejected ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                                  Rechazado
                                </span>
                              ) : isFalsePositive ? (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-800 flex items-center gap-1">
                                  <Ban className="w-3 h-3" /> Falso Positivo
                                </span>
                              ) : (
                                <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-800">
                                  Por Validar
                                </span>
                              )}

                              {/* Grupo Visual Actual (Evidence 8: visual_variant_group_id) */}
                              {sym.visual_variant_group_id && (
                                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                                  Grupo: {sym.visual_variant_group_id}
                                </span>
                              )}
                            </div>

                            {/* Evidencia 2 y 3: Documento origen y página + Evidencia 4: Contexto estructural + Linaje de Tabla */}
                            <div className="flex items-center gap-3 text-[11px] text-slate-400 flex-wrap">
                              <span>
                                Doc: <strong className="text-slate-300">{sym.document_title || 'Documento Técnico'}</strong>
                              </span>
                              <span>• Pág. <strong className="text-slate-300">{sym.page_number}</strong></span>
                              <span>• Contexto: <span className="font-mono text-cyan-400">{sym.layout_context} ({sym.context_association_mode})</span></span>
                              {sym.source_table_id && (
                                <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-teal-800 text-teal-300 font-mono text-[10px]" title={`Tabla: ${sym.source_table_id}`}>
                                  📊 Fila {sym.row_index !== undefined ? sym.row_index + 1 : '?'}:Col {sym.col_index !== undefined ? sym.col_index + 1 : '?'}
                                </span>
                              )}
                              {sym.estimated_physical_size_mm && (
                                <span>• Dim: <strong className="text-slate-300">{sym.estimated_physical_size_mm.width_mm} x {sym.estimated_physical_size_mm.height_mm} mm</strong></span>
                              )}
                              {sym.standard_reference && (
                                <span>• Norma: <span className="text-purple-300 font-semibold">{sym.standard_reference}</span></span>
                              )}
                            </div>

                            {/* Ocurrencias Multipágina Navegables e Interactivas (Clic para "Ampliar" en Visor) */}
                            <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                              <span className="text-[10px] text-slate-400 font-semibold flex items-center gap-1">
                                <Layers className="w-3 h-3 text-cyan-400" />
                                Ocurrencias ({sym.occurrences && sym.occurrences.length > 0 ? sym.occurrences.length : 1}):
                              </span>
                              {sym.occurrences && sym.occurrences.length > 0 ? (
                                sym.occurrences.map((occ, idx) => (
                                  <button
                                    key={idx}
                                    type="button"
                                    onClick={(e) => {
                                      e.stopPropagation();
                                      handleOpenOccurrence(sym, occ);
                                    }}
                                    className="px-2 py-0.5 rounded text-[10.5px] font-mono bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 hover:border-cyan-500 transition-all flex items-center gap-1 shadow-sm group"
                                    title={`Abrir visor en Pág. ${occ.page_number} y enfocar región de símbolo`}
                                  >
                                    <span>Pág. {occ.page_number}</span>
                                    <ExternalLink className="w-2.5 h-2.5 opacity-70 group-hover:opacity-100 group-hover:translate-x-0.5 transition-transform" />
                                  </button>
                                ))
                              ) : (
                                <button
                                  type="button"
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    handleOpenOccurrence(sym, {
                                      page_number: sym.page_number,
                                      bbox_normalized: sym.cell_bbox || [],
                                      source_document_id: sym.document_id,
                                      crop_image_path: sym.crop_image_path
                                    });
                                  }}
                                  className="px-2 py-0.5 rounded text-[10.5px] font-mono bg-cyan-950/80 hover:bg-cyan-900 text-cyan-300 border border-cyan-800/80 hover:border-cyan-500 transition-all flex items-center gap-1"
                                  title={`Abrir visor en Pág. ${sym.page_number} y enfocar región`}
                                >
                                  <span>Pág. {sym.page_number}</span>
                                  <ExternalLink className="w-2.5 h-2.5 opacity-70" />
                                </button>
                              )}
                            </div>

                            {/* Evidencia 5: OCR asociado */}
                            {sym.ocr_associated_text && (
                              <div className="p-1.5 rounded bg-slate-950/70 border border-slate-800 text-[10.5px] font-mono text-slate-300">
                                <span className="text-teal-400 font-bold mr-1.5">OCR:</span>
                                {sym.ocr_associated_text}
                              </div>
                            )}

                            {/* Evidencia 9: Posible plantilla similar existente en template_memory */}
                            {sym.possible_matching_template && (
                              <div className="p-1.5 rounded bg-sky-950/40 border border-sky-800/60 text-[10.5px] text-sky-200 flex items-center justify-between gap-2">
                                <span className="flex items-center gap-1.5">
                                  <Database className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                                  <span>
                                    Plantilla similar existente: <strong className="font-semibold">{sym.possible_matching_template.display_name}</strong> ({sym.possible_matching_template.similarity * 100}% similitud)
                                  </span>
                                </span>
                                <span className="text-[10px] font-mono text-sky-400 font-bold">
                                  {sym.possible_matching_template.library_name}
                                </span>
                              </div>
                            )}

                            {/* Notas de Validación Humana */}
                            {sym.human_validation_notes && (
                              <div className="text-[10.5px] text-amber-300/90 italic flex items-center gap-1">
                                <ShieldAlert className="w-3 h-3 text-amber-400 shrink-0" />
                                <span>{sym.human_validation_notes}</span>
                              </div>
                            )}
                          </div>

                          {/* Columna 3: Acciones Obligatorias del Modal (Acciones 1 a 8) */}
                          <div className="flex flex-col sm:flex-row items-end sm:items-center gap-1.5 shrink-0">
                            
                            {/* Botón Editar */}
                            <button
                              type="button"
                              onClick={() => handleOpenEdit(sym)}
                              className="px-2.5 py-1 text-xs font-semibold rounded bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1"
                              title="Editar nombre técnico, familia o estándar"
                            >
                              <Edit3 className="w-3.5 h-3.5 text-purple-400" />
                              <span>Editar</span>
                            </button>

                            {/* Acciones de Validación */}
                            {!isApproved && (
                              <button
                                type="button"
                                onClick={() => handleCurateSingle(sym, 'accept')}
                                className="px-2.5 py-1 text-xs font-bold rounded bg-emerald-950 text-emerald-300 border border-emerald-800 hover:bg-emerald-900 flex items-center gap-1"
                                title="Aprobar candidato para reutilización"
                              >
                                <Check className="w-3.5 h-3.5 text-emerald-400" />
                                <span>Aprobar</span>
                              </button>
                            )}

                            {!isRejected && (
                              <button
                                type="button"
                                onClick={() => handleCurateSingle(sym, 'reject')}
                                className="px-2 py-1 text-xs font-semibold rounded bg-slate-800/80 text-slate-400 border border-slate-700 hover:bg-slate-800"
                                title="Rechazar candidato"
                              >
                                <X className="w-3.5 h-3.5" />
                              </button>
                            )}

                            {!isFalsePositive && (
                              <button
                                type="button"
                                onClick={() => handleCurateSingle(sym, 'flag_false_positive')}
                                className="px-2 py-1 text-xs font-semibold rounded bg-rose-950/70 text-rose-300 border border-rose-800 hover:bg-rose-900"
                                title="Marcar como Falso Positivo"
                              >
                                <Ban className="w-3.5 h-3.5" />
                              </button>
                            )}

                            {/* Gestión de Variantes: Fusionar / Separar */}
                            <div className="flex items-center gap-1">
                              <button
                                type="button"
                                onClick={() => {
                                  setMergingSym(sym);
                                  setTargetGroupId(sym.visual_variant_group_id || '');
                                }}
                                className="p-1 text-xs rounded bg-slate-800 text-slate-300 hover:text-white border border-slate-700"
                                title="Fusionar con variante existente"
                              >
                                <Merge className="w-3.5 h-3.5 text-indigo-400" />
                              </button>

                              {sym.visual_variant_group_id && (
                                <button
                                  type="button"
                                  onClick={() => handleSplitVariant(sym)}
                                  className="p-1 text-xs rounded bg-slate-800 text-slate-300 hover:text-white border border-slate-700"
                                  title="Separar de grupo de deduplicación"
                                >
                                  <Split className="w-3.5 h-3.5 text-amber-400" />
                                </button>
                              )}
                            </div>

                            {/* Promoción Controlada a SymbolTemplate */}
                            <button
                              type="button"
                              onClick={() => handlePromoteSingle(sym)}
                              disabled={promoting}
                              className="px-2.5 py-1 text-xs font-bold rounded bg-purple-600 hover:bg-purple-500 text-white shadow flex items-center gap-1 transition-all active:scale-95 disabled:opacity-50"
                              title="Promover a SymbolTemplate (requiere aprobación)"
                            >
                              <BookmarkCheck className="w-3.5 h-3.5" />
                              <span>Promover</span>
                            </button>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Vista 2: Catálogo Canónico Consolidado en Template Memory */}
        {activeTab === 'canonical_catalog' && (
          <div className="p-6 overflow-y-auto flex-1 space-y-4 max-h-[calc(95vh-120px)]">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-4 rounded-xl bg-slate-950/70 border border-slate-800">
              <div>
                <h3 className="text-base font-black text-white">
                  {catalog?.library_name || 'Biblioteca Canónica de Piping'}
                </h3>
                <p className="text-xs text-slate-400">
                  Estándar: <strong className="text-purple-300">{catalog?.standard_name || 'ISA-5.1 / ASME B16.34'}</strong> • Total: <strong className="text-emerald-400">{catalog?.total_templates || 0} símbolos canónicos</strong>
                </p>
              </div>

              {/* Conteo por Familias */}
              {catalog?.family_counts && (
                <div className="flex items-center gap-2 flex-wrap">
                  {Object.entries(catalog.family_counts).map(([fam, cnt]) => (
                    <span key={fam} className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700">
                      {fam}: {cnt}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {catalogLoading ? (
              <div className="p-12 text-center text-slate-400 text-sm">Cargando catálogo canónico...</div>
            ) : catalog?.templates.length === 0 ? (
              <div className="p-16 text-center text-slate-500 text-sm">
                Aún no hay plantillas canónicas promovidas en esta biblioteca.
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
                {catalog?.templates.map((tpl) => (
                  <div key={tpl.id} className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 space-y-2.5">
                    <div className="flex items-start gap-3">
                      <div className="w-16 h-16 bg-slate-950 rounded-lg border border-slate-800 p-1 flex items-center justify-center shrink-0">
                        {tpl.image_template_path ? (
                          <img
                            src={tpl.image_template_path.startsWith('http') || tpl.image_template_path.startsWith('data:') ? tpl.image_template_path : (tpl.image_template_path.startsWith('/') ? tpl.image_template_path : `/${tpl.image_template_path}`)}
                            alt={tpl.display_name}
                            className="max-h-full max-w-full object-contain"
                          />
                        ) : (
                          <span className="text-[10px] text-slate-600 font-mono">Sin PNG</span>
                        )}
                      </div>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 flex-wrap">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                            {tpl.symbol_class}
                          </span>
                          {tpl.visual_variant_group_id && (
                            <span className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                              {tpl.visual_variant_group_id}
                            </span>
                          )}
                        </div>
                        <h4 className="text-xs font-black text-slate-100 mt-1 truncate">
                          {tpl.display_name}
                        </h4>
                        <div className="text-[10.5px] text-slate-400 truncate">
                          Alias: {tpl.aliases.join(', ') || 'Ninguno'}
                        </div>
                      </div>
                    </div>

                    <div className="pt-2 border-t border-slate-800/80 text-[10px] text-slate-400 space-y-0.5">
                      <div>Aprobado por: <strong className="text-slate-300">{tpl.approved_by || 'Auditor'}</strong></div>
                      <div>Fecha: {tpl.approved_at ? new Date(tpl.approved_at).toLocaleString() : 'N/A'}</div>
                      {tpl.feature_descriptors?.estimated_physical_size_mm && (
                        <div>Dimensiones: {tpl.feature_descriptors.estimated_physical_size_mm.width_mm} x {tpl.feature_descriptors.estimated_physical_size_mm.height_mm} mm</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Modal Secundario: Edición de Metadatos del Símbolo (HITL) */}
        {editingSym && (
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/70 p-4 animate-in fade-in">
            <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-black text-white flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-purple-400" />
                  Editar Metadatos de Símbolo (HITL)
                </h3>
                <button onClick={() => setEditingSym(null)} className="text-slate-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="text-slate-400 font-semibold block mb-1">Nombre Técnico Normalizado</label>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-slate-400 font-semibold block mb-1">Familia Canónica</label>
                    <select
                      value={editFamily}
                      onChange={(e) => setEditFamily(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500"
                    >
                      <option value="valves">Válvulas (valves)</option>
                      <option value="instruments">Instrumentación (instruments)</option>
                      <option value="fittings">Accesorios (fittings)</option>
                      <option value="equipment">Equipos (equipment)</option>
                      <option value="line_types">Tipos de Línea (line_types)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-slate-400 font-semibold block mb-1">Estándar de Referencia</label>
                    <input
                      type="text"
                      value={editStandard}
                      onChange={(e) => setEditStandard(e.target.value)}
                      placeholder="ISA-5.1 / ASME B16.34"
                      className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="text-slate-400 font-semibold block mb-1">Categoría / Subtipo</label>
                  <input
                    type="text"
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                    placeholder="Compuerta, Retención, Globo, Transmisor..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>

                <div>
                  <label className="text-slate-400 font-semibold block mb-1">Notas de Validación Humana</label>
                  <textarea
                    rows={2}
                    value={editNotes}
                    onChange={(e) => setEditNotes(e.target.value)}
                    placeholder="Observaciones de revisión técnica, especificaciones de catálogo..."
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingSym(null)}
                  className="px-3 py-1.5 text-xs font-semibold rounded bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  className="px-4 py-1.5 text-xs font-bold rounded bg-purple-600 hover:bg-purple-500 text-white shadow"
                >
                  Guardar Cambios
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal Secundario: Fusión Manual a Grupo de Variantes */}
        {mergingSym && (
          <div className="fixed inset-0 z-60 flex items-center justify-center bg-black/70 p-4 animate-in fade-in">
            <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 space-y-4">
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <h3 className="text-sm font-black text-white flex items-center gap-2">
                  <Merge className="w-4 h-4 text-indigo-400" />
                  Fusionar Variante con Grupo Existente
                </h3>
                <button onClick={() => setMergingSym(null)} className="text-slate-400 hover:text-white">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <p className="text-slate-300">
                  Fusionando: <strong className="text-white">{mergingSym.symbol_name}</strong>
                </p>

                <div>
                  <label className="text-slate-400 font-semibold block mb-1">ID del Grupo Destino (visual_variant_group_id)</label>
                  <input
                    type="text"
                    value={targetGroupId}
                    onChange={(e) => setTargetGroupId(e.target.value)}
                    placeholder="Ej. VVG-4A82F19B"
                    className="w-full bg-slate-800 border border-slate-700 rounded-lg p-2 text-white font-mono focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setMergingSym(null)}
                  className="px-3 py-1.5 text-xs font-semibold rounded bg-slate-800 text-slate-300 hover:bg-slate-700"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleMergeVariant}
                  disabled={!targetGroupId}
                  className="px-4 py-1.5 text-xs font-bold rounded bg-indigo-600 hover:bg-indigo-500 text-white shadow disabled:opacity-50"
                >
                  Confirmar Fusión
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal Secundario: Lightbox de Zoom de Evidencia Visual */}
        {lightboxImg && (
          <div
            className="fixed inset-0 z-70 flex items-center justify-center bg-black/90 p-4"
            onClick={() => setLightboxImg(null)}
          >
            <div className="relative max-w-2xl max-h-[85vh] bg-slate-950 p-3 rounded-2xl border border-slate-700 flex flex-col items-center">
              <img
                src={lightboxImg.src.startsWith('http') || lightboxImg.src.startsWith('data:') ? lightboxImg.src : (lightboxImg.src.startsWith('/') ? lightboxImg.src : `/${lightboxImg.src}`)}
                alt={lightboxImg.title}
                className="max-h-[70vh] object-contain rounded-lg shadow-2xl"
              />
              <div className="mt-3 text-center text-xs font-bold text-slate-200">
                {lightboxImg.title}
              </div>
              <button
                onClick={() => setLightboxImg(null)}
                className="absolute top-2 right-2 p-1.5 bg-slate-800 text-white rounded-full hover:bg-slate-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}

        {/* Visor Contextual Interactivo de Lámina con BBox Enfocado (Navegación Multipágina) */}
        {viewerTarget && (
          <ItemContextViewerModal
            isOpen={!!viewerTarget}
            extractionId={viewerTarget.extractionId || null}
            item={viewerTarget.item}
            onClose={() => setViewerTarget(null)}
          />
        )}

      </div>
    </div>
  );
};
