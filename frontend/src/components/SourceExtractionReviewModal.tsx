import React, { useState, useEffect } from 'react';
import {
  X, Check, Trash2, Edit3, ShieldAlert, Sparkles, BookOpen,
  Filter, Layers, CheckCircle2, AlertCircle, Clock, Eye,
  Table as TableIcon, Shapes, FileText, BookmarkPlus, ArrowRight,
  Database, HelpCircle, Globe, ExternalLink, ShieldCheck, Link2
} from 'lucide-react';
import { apiService } from '../services/api';
import { SourceExtraction, ExtractedItem, ExtractedItemType, ItemNatureType, WebCitation } from '../types';

interface SourceExtractionReviewModalProps {
  isOpen: boolean;
  extractionId: string | null;
  ruleDocumentId?: string | null;
  readOnly?: boolean;
  onClose: () => void;
  onCommitted?: () => void;
}

export const SourceExtractionReviewModal: React.FC<SourceExtractionReviewModalProps> = ({
  isOpen,
  extractionId,
  ruleDocumentId,
  readOnly = false,
  onClose,
  onCommitted,
}) => {
  const [extraction, setExtraction] = useState<SourceExtraction | null>(null);
  const [items, setItems] = useState<ExtractedItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [committing, setCommitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [originFilter, setOriginFilter] = useState<'all' | 'document' | 'web'>('all');
  const [editingItem, setEditingItem] = useState<ExtractedItem | null>(null);
  const [showCitations, setShowCitations] = useState<boolean>(false);

  // Formulario de edición
  const [editTitle, setEditTitle] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editOcr, setEditOcr] = useState('');
  const [editDestination, setEditDestination] = useState<'rules_engine' | 'knowledge_base' | 'both'>('rules_engine');
  const [editType, setEditType] = useState<ExtractedItemType>('rule');
  const [editNature, setEditNature] = useState<ItemNatureType>('official_rule');
  const [editSourceRef, setEditSourceRef] = useState('');

  useEffect(() => {
    if (isOpen) {
      if (extractionId) {
        loadExtractionData(extractionId);
      } else if (ruleDocumentId) {
        loadRuleDocumentItems(ruleDocumentId);
      }
    }
  }, [isOpen, extractionId, ruleDocumentId]);

  const loadExtractionData = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.getExtractionDetail(id);
      setExtraction(data);
      setItems(data.items || []);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar la extracción.');
    } finally {
      setLoading(false);
    }
  };

  const loadRuleDocumentItems = async (docId: string) => {
    setLoading(true);
    setError(null);
    try {
      const doc = await apiService.getRuleDocumentDetail(docId);
      const isWeb = doc.source_origin === 'con_ia_web';
      setExtraction({
        id: doc.id,
        organization_id: doc.organization_id,
        extraction_mode: doc.source_origin === 'con_ia_web' ? 'ai_web_research' : doc.source_origin === 'con_ia_documento' ? 'ai_document' : 'without_ai',
        source_origin: isWeb ? 'web' : 'document',
        search_query: doc.metadata_info?.search_query,
        search_citations: doc.metadata_info?.search_citations,
        title: doc.title,
        document_type: doc.document_type,
        authority: doc.authority,
        discipline: doc.discipline,
        status: doc.status as any,
        summary: doc.description,
        total_items: doc.items_count,
        created_at: doc.created_at,
        updated_at: doc.updated_at,
      });
      // Mapear items de rule document a extracted items para visualización uniforme
      const mapped: ExtractedItem[] = (doc.items || []).map((it: any) => ({
        id: it.id,
        extraction_id: doc.id,
        item_type: it.item_type as ExtractedItemType,
        title: it.title,
        code_or_number: it.code_or_number,
        description: it.description,
        content_text: it.content_text,
        ocr_text: it.ocr_text,
        crop_image_path: it.crop_image_path,
        bbox_normalized: [],
        page_number: 1,
        target_destination: it.target_destination as any,
        review_status: 'accepted',
        source_origin: (it.source_origin as any) || (isWeb ? 'web' : 'document'),
        source_reference: it.source_reference,
        item_nature: (it.item_nature as ItemNatureType) || (isWeb ? 'proposed_rule' : 'official_rule'),
        governance_note: isWeb ? 'Incorporado desde investigación en Internet' : undefined,
        created_at: it.created_at,
        updated_at: it.created_at,
      }));
      setItems(mapped);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar contenido del documento.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const handleStatusChange = async (item: ExtractedItem, newStatus: 'to_confirm' | 'accepted' | 'rejected') => {
    if (!extractionId) return;
    try {
      await apiService.updateExtractedItem(extractionId, item.id, { review_status: newStatus });
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, review_status: newStatus } : i)));
    } catch (err) {
      console.error('Error actualizando estado de item:', err);
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!extractionId) return;
    try {
      await apiService.deleteExtractedItem(extractionId, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      console.error('Error eliminando item:', err);
    }
  };

  const handleStartEdit = (item: ExtractedItem) => {
    setEditingItem(item);
    setEditTitle(item.title);
    setEditCode(item.code_or_number || '');
    setEditDesc(item.description || item.content_text || '');
    setEditOcr(item.ocr_text || '');
    setEditDestination(item.target_destination);
    setEditType(item.item_type);
    setEditNature(item.item_nature || (item.source_origin === 'web' ? 'proposed_rule' : 'official_rule'));
    setEditSourceRef(item.source_reference || '');
  };

  const handleSaveEdit = async () => {
    if (!editingItem || !extractionId) return;
    try {
      const updated = await apiService.updateExtractedItem(extractionId, editingItem.id, {
        title: editTitle.trim(),
        code_or_number: editCode.trim() || undefined,
        description: editDesc.trim() || undefined,
        ocr_text: editOcr.trim() || undefined,
        target_destination: editDestination,
        item_type: editType,
        item_nature: editNature,
        source_reference: editSourceRef.trim() || undefined,
      });
      setItems((prev) => prev.map((i) => (i.id === editingItem.id ? { ...i, ...updated } : i)));
      setEditingItem(null);
    } catch (err) {
      console.error('Error guardando cambios del elemento:', err);
    }
  };

  const handleCommitAll = async () => {
    if (!extractionId) return;
    setCommitting(true);
    setError(null);
    try {
      await apiService.commitExtractionToRules(extractionId, {});
      if (onCommitted) onCommitted();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al incorporar elementos al Motor de Reglas.');
    } finally {
      setCommitting(false);
    }
  };

  const filteredItems = items.filter((it) => {
    // Filtro por procedencia
    if (originFilter !== 'all' && (it.source_origin || 'document') !== originFilter) {
      return false;
    }
    // Filtro por tipo de elemento
    if (filterType === 'all') return true;
    if (filterType === 'rules') return ['rule', 'restriction', 'requirement'].includes(it.item_type);
    if (filterType === 'articles') return ['article', 'chapter'].includes(it.item_type);
    if (filterType === 'tables') return it.item_type === 'table';
    if (filterType === 'figures') return ['figure', 'image', 'symbol'].includes(it.item_type);
    if (filterType === 'notes') return ['text_note', 'definition', 'procedure', 'concept', 'reference'].includes(it.item_type);
    return true;
  });

  const getItemTypeBadge = (type: string, nature?: string, origin?: string) => {
    if (origin === 'web' || nature === 'proposed_rule') {
      if (type === 'rule' || type === 'restriction' || type === 'requirement') {
        return { label: 'REGLA PROPUESTA (WEB)', bg: 'bg-amber-500/10 text-amber-300 border-amber-800/60' };
      }
    }
    switch (type) {
      case 'rule':
      case 'restriction':
      case 'requirement':
        return { label: 'REGLA QA/QC OFICIAL', bg: 'bg-rose-500/10 text-rose-400 border-rose-800/40' };
      case 'article':
      case 'chapter':
        return { label: 'ARTÍCULO / CAPÍTULO', bg: 'bg-sky-500/10 text-sky-400 border-sky-800/40' };
      case 'table':
        return { label: 'TABLA DE PARÁMETROS', bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-800/40' };
      case 'figure':
      case 'image':
      case 'symbol':
        return { label: 'FIGURA / ESQUEMA', bg: 'bg-purple-500/10 text-purple-400 border-purple-800/40' };
      case 'definition':
      case 'concept':
      case 'procedure':
      case 'text_note':
        return { label: 'CONCEPTO / PROCEDIMIENTO', bg: 'bg-indigo-500/10 text-indigo-300 border-indigo-800/40' };
      case 'reference':
        return { label: 'REFERENCIA WEB / LEGAL', bg: 'bg-slate-700/20 text-slate-300 border-slate-700' };
      default:
        return { label: 'OTRO', bg: 'bg-slate-700/20 text-slate-400 border-slate-700' };
    }
  };

  const isWebExtraction = extraction?.source_origin === 'web' || extraction?.extraction_mode === 'ai_web_research';

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${isWebExtraction ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-teal-500/10 text-teal-400 border border-teal-500/20'}`}>
              {isWebExtraction ? <Globe className="w-5 h-5" /> : extraction?.extraction_mode === 'with_ai' || extraction?.extraction_mode === 'ai_document' ? <Sparkles className="w-5 h-5" /> : <BookOpen className="w-5 h-5 text-sky-400" />}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-bold text-slate-100">
                  {extraction ? extraction.title : 'Revisión y Validación de Contenido Estructurado'}
                </h2>
                
                {/* Badge de Procedencia */}
                {isWebExtraction ? (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700 flex items-center gap-1">
                    <Globe className="w-3 h-3" /> Origen: Búsqueda en Internet
                  </span>
                ) : (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-teal-950 text-teal-300 border border-teal-700 flex items-center gap-1">
                    <FileText className="w-3 h-3" /> Origen: Documento Interno
                  </span>
                )}

                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {extraction?.document_type || 'Norma'}
                </span>
                {extraction?.authority && (
                  <span className="text-[10px] font-medium text-slate-400">
                    • {extraction.authority}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Valida, edita o descarta elementos antes de incorporarlos al Motor de Reglas QA/QC y a la Base de Conocimiento
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Banner de Gobernanza para Extracciones de Origen Web */}
        {isWebExtraction && (
          <div className="px-6 py-3 bg-indigo-950/40 border-b border-indigo-800/40 flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-start gap-2.5 text-xs text-indigo-200 flex-1">
              <ShieldAlert className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <span className="font-bold text-amber-300">Contenido de Apoyo e Investigación:</span>{' '}
                {extraction?.search_query ? (
                  <span>Tema consultado: <em>"{extraction.search_query}"</em>. </span>
                ) : null}
                Las reglas propuestas están marcadas como sugerencias de apoyo técnico y requieren validación humana reforzada.
              </div>
            </div>

            {extraction?.search_citations && extraction.search_citations.length > 0 && (
              <button
                type="button"
                onClick={() => setShowCitations(!showCitations)}
                className="text-xs font-semibold text-indigo-300 hover:text-indigo-100 flex items-center gap-1.5 bg-indigo-900/60 hover:bg-indigo-800 px-3 py-1 rounded-lg border border-indigo-700 transition-colors"
              >
                <Link2 className="w-3.5 h-3.5" />
                <span>{showCitations ? 'Ocultar' : 'Ver'} Fuentes Consultadas ({extraction.search_citations.length})</span>
              </button>
            )}
          </div>
        )}

        {/* Desglose de Citas y Fuentes Web (Colapsable) */}
        {isWebExtraction && showCitations && extraction?.search_citations && (
          <div className="px-6 py-3 bg-slate-950/90 border-b border-slate-800 text-xs space-y-2 animate-in fade-in">
            <span className="font-semibold text-slate-300 block text-[11px] uppercase tracking-wider">
              Referencias y Fuentes Recuperadas en la Web:
            </span>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {extraction.search_citations.map((c, idx) => (
                <a
                  key={idx}
                  href={c.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-indigo-500/60 flex items-start justify-between gap-2 text-slate-300 hover:text-indigo-300 transition-colors group"
                >
                  <div className="space-y-0.5 min-w-0">
                    <div className="font-semibold text-slate-200 text-xs truncate group-hover:text-indigo-200">
                      {c.title || c.domain}
                    </div>
                    <div className="text-[10px] text-slate-500 truncate font-mono">
                      {c.url}
                    </div>
                  </div>
                  <ExternalLink className="w-3.5 h-3.5 text-slate-500 group-hover:text-indigo-400 shrink-0 mt-0.5" />
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Filtros de Categorías y Procedencia */}
        <div className="px-6 py-2.5 border-b border-slate-800 bg-slate-900/60 flex items-center justify-between gap-4 flex-wrap">
          <div className="flex items-center gap-1.5 overflow-x-auto flex-wrap">
            <span className="text-xs font-semibold text-slate-400 mr-1 flex items-center gap-1">
              <Filter className="w-3.5 h-3.5" /> Filtrar:
            </span>
            <button
              onClick={() => setFilterType('all')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'all' ? 'bg-teal-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Todos ({items.length})
            </button>
            <button
              onClick={() => setFilterType('rules')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'rules' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Reglas QA/QC
            </button>
            <button
              onClick={() => setFilterType('articles')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'articles' ? 'bg-sky-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Artículos & Capítulos
            </button>
            <button
              onClick={() => setFilterType('tables')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'tables' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Tablas
            </button>
            <button
              onClick={() => setFilterType('figures')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'figures' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Figuras & Esquemas
            </button>
            <button
              onClick={() => setFilterType('notes')}
              className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'notes' ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
            >
              Notas & Conceptos
            </button>
          </div>

          <div className="flex items-center gap-3 text-xs text-slate-400">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Aceptados: {items.filter((i) => i.review_status === 'accepted').length}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" /> Por Confirmar: {items.filter((i) => i.review_status === 'to_confirm').length}
            </span>
          </div>
        </div>

        {/* Lista de Elementos Extraídos */}
        <div className="p-6 overflow-y-auto space-y-3.5 flex-1 max-h-[calc(92vh-220px)]">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="p-12 text-center text-slate-400 text-sm">
              Cargando elementos estructurados del documento...
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm">
              No hay elementos en esta categoría.
            </div>
          ) : (
            filteredItems.map((item) => {
              const badge = getItemTypeBadge(item.item_type, item.item_nature, item.source_origin);
              const isAccepted = item.review_status === 'accepted';
              const isRejected = item.review_status === 'rejected';
              const isWebItem = item.source_origin === 'web';

              return (
                <div
                  key={item.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isAccepted
                      ? isWebItem
                        ? 'bg-slate-900/90 border-indigo-800/50 shadow-sm shadow-indigo-950/30'
                        : 'bg-slate-900/90 border-emerald-800/40'
                      : isRejected
                      ? 'bg-slate-950/40 border-slate-800 opacity-60'
                      : isWebItem
                      ? 'bg-slate-900/90 border-indigo-900/40'
                      : 'bg-slate-900/90 border-slate-800'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    
                    {/* Contenido Principal */}
                    <div className="space-y-1.5 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        
                        {/* Tipo de Elemento */}
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider ${badge.bg}`}>
                          {badge.label}
                        </span>

                        {/* Badge de Procedencia por Item */}
                        {isWebItem ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-800/80 flex items-center gap-1">
                            <Globe className="w-3 h-3 text-indigo-400" /> Web Research
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-800/80 flex items-center gap-1">
                            <FileText className="w-3 h-3 text-teal-400" /> Documento
                          </span>
                        )}

                        {item.code_or_number && (
                          <span className="font-mono text-xs font-bold text-teal-400">
                            {item.code_or_number}
                          </span>
                        )}

                        <h4 className="text-sm font-bold text-slate-100">
                          {item.title}
                        </h4>
                        
                        {/* Destino Badge */}
                        <span className="text-[10px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
                          Destino: {item.target_destination === 'both' ? 'Reglas + Base Conocimiento' : item.target_destination === 'knowledge_base' ? 'Base de Conocimiento' : 'Motor de Reglas'}
                        </span>
                      </div>

                      {/* Descripción o Regla */}
                      <p className="text-xs text-slate-300 leading-relaxed">
                        {item.description || item.content_text}
                      </p>

                      {/* Enlace o Referencia Normativa si existe */}
                      {item.source_reference && (
                        <div className="flex items-center gap-1.5 text-[11px] text-indigo-300 bg-indigo-950/40 px-2.5 py-1 rounded-lg border border-indigo-800/40 w-fit mt-1">
                          <Link2 className="w-3 h-3 text-indigo-400" />
                          <span className="font-medium">Referencia / Enlace:</span>
                          <span className="font-mono text-[10px] text-indigo-200">{item.source_reference}</span>
                        </div>
                      )}

                      {/* Nota de Gobernanza si existe */}
                      {item.governance_note && (
                        <div className="text-[10.5px] text-amber-300/90 italic flex items-center gap-1 mt-0.5">
                          <ShieldAlert className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>{item.governance_note}</span>
                        </div>
                      )}

                      {/* OCR Text si aplica */}
                      {item.ocr_text && (
                        <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800/70 text-[11px] font-mono text-slate-400">
                          <span className="text-[10px] text-teal-500 font-bold block mb-0.5">OCR EXTRAÍDO:</span>
                          {item.ocr_text}
                        </div>
                      )}

                      {/* Recorte o Imagen si existe */}
                      {item.crop_image_path && (
                        <div className="mt-2 inline-block p-1.5 rounded-lg bg-slate-950 border border-slate-800">
                          <img
                            src={item.crop_image_path.startsWith('http') ? item.crop_image_path : `http://localhost:8000${item.crop_image_path}`}
                            alt={item.title}
                            className="max-h-28 rounded object-contain"
                          />
                        </div>
                      )}
                    </div>

                    {/* Acciones de Validación */}
                    {!readOnly && (
                      <div className="flex items-center gap-1.5 shrink-0">
                        <button
                          onClick={() => handleStartEdit(item)}
                          className="p-1.5 text-slate-400 hover:text-teal-400 hover:bg-slate-800 rounded-lg transition-colors"
                          title="Editar elemento"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        
                        <button
                          onClick={() => handleStatusChange(item, isAccepted ? 'to_confirm' : 'accepted')}
                          className={`p-1.5 rounded-lg transition-colors ${isAccepted ? 'text-emerald-400 bg-emerald-950/50 border border-emerald-800' : 'text-slate-400 hover:text-emerald-400 hover:bg-slate-800'}`}
                          title={isAccepted ? 'Aceptado (clic para desmarcar)' : 'Aceptar elemento'}
                        >
                          <Check className="w-4 h-4" />
                        </button>

                        <button
                          onClick={() => handleDeleteItem(item.id)}
                          className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
                          title="Eliminar elemento"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Inline de Edición de Item */}
        {editingItem && (
          <div className="p-4 border-t border-slate-800 bg-slate-950/90 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wide flex items-center gap-1.5">
                <Edit3 className="w-3.5 h-3.5 text-teal-400" />
                Editando Elemento: {editingItem.title}
              </h4>
              <button
                onClick={() => setEditingItem(null)}
                className="text-xs text-slate-400 hover:text-slate-200"
              >
                Cerrar edición
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Título</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Código / Artículo</label>
                <input
                  type="text"
                  value={editCode}
                  onChange={(e) => setEditCode(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Naturaleza del Ítem</label>
                <select
                  value={editNature}
                  onChange={(e: any) => setEditNature(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="official_rule">Regla Oficial (Documento)</option>
                  <option value="proposed_rule">Regla Propuesta (Web / Sugerida)</option>
                  <option value="support_research">Contenido de Apoyo / Parámetro</option>
                  <option value="concept">Concepto / Definición</option>
                  <option value="reference">Referencia / Enlace</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Destino</label>
                <select
                  value={editDestination}
                  onChange={(e: any) => setEditDestination(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="rules_engine">Motor de Reglas QA/QC</option>
                  <option value="knowledge_base">Base de Conocimiento</option>
                  <option value="both">Ambos (Reglas + Conocimiento)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Descripción o Contenido</label>
                <textarea
                  rows={2}
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="w-full p-2 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Referencia / Enlace Web (URL o Cita)</label>
                <input
                  type="text"
                  value={editSourceRef}
                  onChange={(e) => setEditSourceRef(e.target.value)}
                  className="w-full px-2.5 py-2 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                  placeholder="https://... o Art. 4.2.4 OGUC"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingItem(null)}
                className="px-3 py-1 text-xs font-medium text-slate-400 hover:text-slate-200"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                className="px-4 py-1 text-xs font-semibold text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-all"
              >
                Guardar Cambios
              </button>
            </div>
          </div>
        )}

        {/* Footer con Acciones Finales */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Total: <strong>{items.length}</strong> elementos analizados ({items.filter((i) => i.review_status === 'accepted').length} aprobados)
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 rounded-xl"
            >
              {readOnly ? 'Cerrar' : 'Cancelar'}
            </button>

            {!readOnly && extractionId && (
              <button
                type="button"
                onClick={handleCommitAll}
                disabled={committing || items.length === 0}
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl transition-all shadow-lg flex items-center space-x-2 disabled:opacity-50 ${
                  isWebExtraction
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-indigo-950/50'
                    : 'bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 shadow-teal-950/50'
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>
                  {committing
                    ? 'Incorporando...'
                    : isWebExtraction
                    ? 'Aceptar e Incorporar Reglas de Apoyo (Web)'
                    : 'Aceptar Todo / Incorporar a Reglas QA/QC'}
                </span>
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
