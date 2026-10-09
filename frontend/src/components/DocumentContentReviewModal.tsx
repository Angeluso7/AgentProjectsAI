import React, { useState, useEffect, useRef } from 'react';
import {
  X, Check, Trash2, Edit3, ShieldAlert, Sparkles, BookOpen,
  Filter, Layers, CheckCircle2, AlertCircle, Clock, Eye,
  Table as TableIcon, Shapes, FileText, BookmarkPlus, ArrowRight,
  Database, HelpCircle, Globe, ExternalLink, ShieldCheck, Link2,
  Search, RefreshCw, GripHorizontal, SquareCheck, Loader2, Save, CheckSquare, Square
} from 'lucide-react';
import { apiService } from '../services/api';
import { RuleDocument, RuleDocumentItem } from '../types';
import { SymbolCurationStudioModal } from './SymbolCurationStudioModal';
import { PromoteDocumentScopeModal } from './PromoteDocumentScopeModal';

interface DocumentContentReviewModalProps {
  isOpen: boolean;
  ruleDocumentId: string | null;
  onClose: () => void;
  onConfirmed?: () => void;
}

export const DocumentContentReviewModal: React.FC<DocumentContentReviewModalProps> = ({
  isOpen,
  ruleDocumentId,
  onClose,
  onConfirmed,
}) => {
  const [doc, setDoc] = useState<RuleDocument | null>(null);
  const [items, setItems] = useState<RuleDocumentItem[]>([]);
  const [contentResponse, setContentResponse] = useState<any | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [reprocessing, setReprocessing] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filtros y Búsqueda
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'rules' | 'symbols' | 'tables' | 'figures'>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [zoomImage, setZoomImage] = useState<string | null>(null);

  // Validación Masiva de Reglas
  const [bulkValidating, setBulkValidating] = useState<boolean>(false);
  const [selectedRuleIds, setSelectedRuleIds] = useState<string[]>([]);

  // Control de Selección de Alcance (Disciplina + Tópico) para Promoción / Re-sincronización
  const [showScopeModal, setShowScopeModal] = useState<boolean>(false);
  const [scopeModalMode, setScopeModalMode] = useState<'promote' | 'resync'>('promote');

  // Estado de Edición de Regla Individual
  const [editingItem, setEditingItem] = useState<RuleDocumentItem | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editType, setEditType] = useState('rule');

  // Estado para Modal de Promoción de Regla Candidata a Baseline QA/QC
  const [promotingItem, setPromotingItem] = useState<RuleDocumentItem | null>(null);
  const [promCode, setPromCode] = useState('');
  const [promTitle, setPromTitle] = useState('');
  const [promDiscipline, setPromDiscipline] = useState('GENERAL');
  const [promTopic, setPromTopic] = useState('REGULATORY_COMPLIANCE');
  const [promPhase, setPromPhase] = useState(6);
  const [promSeverity, setPromSeverity] = useState('medium');
  const [promRationale, setPromRationale] = useState('');
  const [promAction, setPromAction] = useState<'promote_and_activate' | 'promote_for_review'>('promote_and_activate');
  const [promSubmitting, setPromSubmitting] = useState(false);
  const [promSuccess, setPromSuccess] = useState<any | null>(null);

  // Posición y tamaño de la ventana flotante (Fondo Sólido Oscuro)
  const [panelPos, setPanelPos] = useState<{ x: number; y: number }>({ x: 80, y: 50 });
  const [panelSize, setPanelSize] = useState<{ width: number; height: number }>({ width: 880, height: 700 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 80, posY: 50 });
  const resizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 880, height: 700 });

  useEffect(() => {
    if (isOpen && ruleDocumentId) {
      loadDocumentDetails(ruleDocumentId);
    }
  }, [isOpen, ruleDocumentId]);

  const loadDocumentDetails = async (id: string) => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const data = await apiService.getRuleDocumentContent(id);
      setContentResponse(data);
      setDoc(data);
      setItems(Array.isArray(data.items) ? data.items : []);
    } catch (err: any) {
      const statusCode = err?.response?.status;
      if (statusCode === 401 || statusCode === 403) {
        setError(`No tiene permisos para acceder al contenido del documento (HTTP ${statusCode}).`);
      } else if (statusCode === 404) {
        setError('Documento de reglas no encontrado o ha sido eliminado (HTTP 404).');
      } else if (statusCode === 500) {
        setError(`Error del servidor al cargar el contenido (HTTP 500): ${err?.response?.data?.detail || 'Inconsistencia de datos'}`);
      } else {
        setError(err?.response?.data?.detail || 'Error al cargar el contenido del documento.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReprocess = async () => {
    if (!ruleDocumentId) return;
    setReprocessing(true);
    setError(null);
    try {
      const res = await apiService.reprocessRuleDocumentContent(ruleDocumentId);
      setSuccessMessage(res.message || 'Contenido reprocesado exitosamente.');
      await loadDocumentDetails(ruleDocumentId);
      onConfirmed?.();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al reprocesar el contenido del documento.');
    } finally {
      setReprocessing(false);
    }
  };

  // Drag & Resize Handlers
  const handleHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select') || (e.target as HTMLElement).closest('textarea')) return;
    e.preventDefault();
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: panelPos.x,
      posY: panelPos.y,
    };
  };

  const handleResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizing(true);
    resizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      width: panelSize.width,
      height: panelSize.height,
    };
  };

  useEffect(() => {
    if (!isDragging && !isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        const dx = e.clientX - dragRef.current.startX;
        const dy = e.clientY - dragRef.current.startY;
        setPanelPos({
          x: Math.min(Math.max(10, dragRef.current.posX + dx), window.innerWidth - 340),
          y: Math.min(Math.max(10, dragRef.current.posY + dy), window.innerHeight - 100),
        });
      } else if (isResizing) {
        const dx = e.clientX - resizeRef.current.startX;
        const dy = e.clientY - resizeRef.current.startY;
        setPanelSize({
          width: Math.min(Math.max(540, resizeRef.current.width + dx), window.innerWidth - 30),
          height: Math.min(Math.max(460, resizeRef.current.height + dy), window.innerHeight - 40),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      setIsResizing(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, isResizing]);

  // Actualizar estado individual de un item
  const handleUpdateItemStatus = async (item: RuleDocumentItem, newStatus: 'por_confirmar' | 'validada' | 'eliminado') => {
    if (!ruleDocumentId) return;
    try {
      if (newStatus === 'eliminado') {
        await apiService.deleteRuleDocumentItem(ruleDocumentId, item.id);
        setItems((prev) => prev.filter((i) => i.id !== item.id));
      } else {
        const updated = await apiService.updateRuleDocumentItem(ruleDocumentId, item.id, {
          status: newStatus,
        });
        setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, status: newStatus } : i)));
      }
    } catch (err) {
      console.error('Error actualizando estado:', err);
    }
  };

  // Abrir formulario de edición de un item
  const handleStartEdit = (item: RuleDocumentItem) => {
    setEditingItem(item);
    setEditTitle(item.title);
    setEditCode(item.code_or_number || '');
    setEditDesc(item.description || item.content_text || '');
    setEditType(item.item_type || 'rule');
  };

  const handleSaveEdit = async () => {
    if (!editingItem || !ruleDocumentId) return;
    try {
      const updated = await apiService.updateRuleDocumentItem(ruleDocumentId, editingItem.id, {
        title: editTitle.trim(),
        code_or_number: editCode.trim() || undefined,
        description: editDesc.trim() || undefined,
        content_text: editDesc.trim() || undefined,
        item_type: editType,
        status: 'editado',
      });
      setItems((prev) => prev.map((i) => (i.id === editingItem.id ? { ...i, ...updated, status: 'editado' } : i)));
      setEditingItem(null);
    } catch (err) {
      console.error('Error guardando edición de regla:', err);
    }
  };

  // Validación Masiva de Reglas del Documento
  const handleBulkValidateRules = async (specificIds?: string[]) => {
    if (!ruleDocumentId) return;
    setBulkValidating(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const targetIds = specificIds && specificIds.length > 0 ? specificIds : undefined;
      const res = await apiService.bulkValidateRuleItems(ruleDocumentId, targetIds ? { item_ids: targetIds } : {});

      // Actualizar estado local de los items en memoria
      setItems((prev) =>
        prev.map((it) => {
          if (!isRuleItem(it)) return it;
          if (targetIds && !targetIds.includes(it.id)) return it;
          return { ...it, status: 'validada' };
        })
      );

      // Limpiar selección
      setSelectedRuleIds([]);
      setSuccessMessage(res.message || `Se validaron ${res.validated_count} regla(s) documental(es) exitosamente.`);

      // Actualizar doc.rules_count local si doc está presente
      if (doc) {
        setDoc((prev) => prev ? { ...prev, rules_count: res.total_validated_rules ?? prev.rules_count } : null);
      }
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error en la validación masiva de reglas.');
    } finally {
      setBulkValidating(false);
    }
  };

  // Confirmar Contenido Documental (Aceptar dentro de la ventana Contenido)
  const handleConfirmDocumentContent = async () => {
    if (!ruleDocumentId) return;
    setSaving(true);
    setSuccessMessage(null);
    try {
      const validatedItems = items.filter((i) => i.status === 'validada' || i.status === 'active' || i.status === 'accepted');
      const confirmedIds = validatedItems.map((i) => i.id);

      const res = await apiService.confirmRuleDocumentContent(ruleDocumentId, {
        confirmed_item_ids: confirmedIds,
      });

      setSuccessMessage(res.message);

      setTimeout(() => {
        if (onConfirmed) onConfirmed();
        onClose();
      }, 1500);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al confirmar contenido del documento.');
    } finally {
      setSaving(false);
    }
  };

  // Abrir Modal de Promoción para una regla candidata individual
  const handleOpenPromotion = (item: RuleDocumentItem) => {
    setPromotingItem(item);
    setPromSuccess(null);
    setPromTitle(item.title);

    // Derivar y normalizar código
    let initCode = (item.code_or_number || '').trim().toUpperCase().replace(/[^A-Z0-9_\-]+/g, '_');
    if (!initCode || initCode.length < 3) {
      const discPrefix = (doc?.discipline || 'GEN').substring(0, 3).toUpperCase();
      initCode = `${discPrefix}-RULE-${item.id.substring(0, 6).toUpperCase()}`;
    }
    setPromCode(initCode);

    // Mapear disciplina técnica canónica
    const discStr = (doc?.discipline || 'GENERAL').toUpperCase();
    if (['ARQUITECTURA', 'ARCHITECTURE'].includes(discStr)) setPromDiscipline('ARCHITECTURE');
    else if (['ESTRUCTURA', 'ESTRUCTURAS', 'STRUCTURES'].includes(discStr)) setPromDiscipline('STRUCTURES');
    else if (['TUBERIAS', 'TUBERÍAS', 'PIPING'].includes(discStr)) setPromDiscipline('PIPING');
    else if (['ELECTRICO', 'ELECTRICA', 'ELECTRICAL'].includes(discStr)) setPromDiscipline('ELECTRICAL');
    else if (['MECANICA', 'MECÁNICA', 'HVAC'].includes(discStr)) setPromDiscipline('HVAC');
    else if (['CIVIL'].includes(discStr)) setPromDiscipline('CIVIL');
    else if (['INCENDIO', 'FIRE_PROTECTION'].includes(discStr)) setPromDiscipline('FIRE_PROTECTION');
    else if (['SANITARIA', 'SANITARY'].includes(discStr)) setPromDiscipline('SANITARY');
    else setPromDiscipline('GENERAL');

    setPromTopic('REGULATORY_COMPLIANCE');
    setPromPhase(6);
    setPromSeverity('high');
    setPromRationale(`Promoción técnica de regla normativa desde documento «${doc?.title || 'Fuente'}».`);
    setPromAction('promote_and_activate');
  };

  // Enviar Promoción Individual
  const handleSubmitPromotion = async (actionOverride?: 'promote_and_activate' | 'promote_for_review') => {
    if (!promotingItem) return;
    const finalAction = actionOverride || promAction;
    setPromSubmitting(true);
    setError(null);
    try {
      const res = await apiService.promoteRuleCandidate(promotingItem.id, {
        decision: 'approve',
        action: finalAction,
        reviewer_rationale: promRationale.trim() || 'Aprobación y promoción técnica a Baseline QA/QC.',
        rule_code: promCode.trim().toUpperCase(),
        title: promTitle.trim(),
        severity: promSeverity,
        discipline_ids: [promDiscipline],
        topic_ids: [promTopic],
        execution_phase: promPhase,
        enabled: finalAction === 'promote_and_activate'
      });

      setPromSuccess(res);
      // Actualizar el item localmente en el estado
      setItems((prev) =>
        prev.map((i) =>
          i.id === promotingItem.id
            ? {
                ...i,
                status: 'validada',
                promotion_status: res.candidate_status,
                promoted_rule_definition_id: res.rule_definition_id,
              }
            : i
        )
      );

      // Notificar al componente superior (RulesPage) para refrescar Baseline y Documentos
      if (onConfirmed) {
        onConfirmed();
      }

      setTimeout(() => {
        setPromotingItem(null);
        setPromSuccess(null);
      }, 2200);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al promover regla candidata a Baseline QA/QC.');
    } finally {
      setPromSubmitting(false);
    }
  };

  // Promoción Masiva del Documento Completo a Baseline QA/QC (o Re-sincronización) con Alcance Explícito
  const handleOpenScopeModal = (mode: 'promote' | 'resync') => {
    setScopeModalMode(mode);
    setShowScopeModal(true);
  };

  const handleScopeSuccess = async (res: any) => {
    setSuccessMessage(res.message);
    if (doc) {
      setDoc({ ...doc, status: 'promovido_baseline' });
    }
    if (onConfirmed) {
      onConfirmed();
    }
    if (ruleDocumentId) {
      await loadDocumentDetails(ruleDocumentId);
    }
  };

  const handlePromoteAllDocumentToBaseline = async () => {
    handleOpenScopeModal('promote');
  };

  const getItemTypeBadge = (type: string) => {
    const t = (type || '').toLowerCase();
    switch (t) {
      case 'simbolo':
      case 'symbol':
      case 'symbol_candidate':
        return <span className="px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800 text-[10px] font-bold">🔘 Símbolo</span>;
      case 'tabla':
      case 'table':
        return <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-bold">📊 Tabla</span>;
      case 'figura':
      case 'figure':
      case 'image':
      case 'foto':
        return <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-bold">📐 Figura</span>;
      case 'rule':
      case 'regla':
        return <span className="px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 text-[10px] font-bold">⚖️ Regla QA/QC</span>;
      case 'article':
        return <span className="px-1.5 py-0.5 rounded bg-violet-950 text-violet-300 border border-violet-800 text-[10px] font-bold">📜 Artículo</span>;
      case 'requirement':
        return <span className="px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] font-bold">✅ Requisito</span>;
      case 'restriction':
        return <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px] font-bold">⛔ Restricción</span>;
      default:
        return <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-bold">{type}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'validada':
      case 'accepted':
      case 'active':
        return <span className="px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[10px] font-bold flex items-center gap-1">🟢 Validada</span>;
      case 'por_confirmar':
      case 'to_confirm':
      case 'draft':
        return <span className="px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-700 text-[10px] font-bold flex items-center gap-1">🟡 Por confirmar</span>;
      case 'editado':
        return <span className="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700 text-[10px] font-bold flex items-center gap-1">🔵 Editado</span>;
      case 'eliminado':
      case 'rejected':
        return <span className="px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-700 text-[10px] font-bold flex items-center gap-1">🔴 Eliminado</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-medium flex items-center gap-1">⚪ {status}</span>;
    }
  };

  const filteredItems = items.filter((it) => {
    const itType = (it.item_type || '').toLowerCase();
    if (categoryFilter !== 'all') {
      if (categoryFilter === 'symbols') {
        if (!['symbol', 'simbolo', 'symbol_candidate'].includes(itType)) return false;
      } else if (categoryFilter === 'tables') {
        if (!['table', 'tabla'].includes(itType)) return false;
      } else if (categoryFilter === 'figures') {
        if (!['figure', 'figura', 'image', 'sello', 'foto'].includes(itType)) return false;
      } else if (categoryFilter === 'rules') {
        if (['symbol', 'simbolo', 'symbol_candidate', 'table', 'tabla', 'figure', 'figura', 'image', 'sello', 'foto'].includes(itType)) return false;
      }
    }
    if (filterStatus !== 'all') {
      if (filterStatus === 'validada' && it.status !== 'validada' && it.status !== 'accepted' && it.status !== 'active') return false;
      if (filterStatus === 'por_confirmar' && it.status !== 'por_confirmar' && it.status !== 'to_confirm' && it.status !== 'draft') return false;
      if (filterStatus === 'editado' && it.status !== 'editado') return false;
    }
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchTitle = it.title.toLowerCase().includes(q);
      const matchCode = it.code_or_number?.toLowerCase().includes(q);
      const matchDesc = it.description?.toLowerCase().includes(q) || it.content_text?.toLowerCase().includes(q);
      return matchTitle || matchCode || matchDesc;
    }
    return true;
  });

  const isRuleItem = (item: RuleDocumentItem) =>
    !['symbol', 'simbolo', 'symbol_candidate', 'table', 'tabla', 'figure', 'figura', 'image', 'sello', 'foto'].includes(
      (item.item_type || '').toLowerCase()
    ) && item.status !== 'eliminado';

  const totalCount = items.length;
  const symbolCount = items.filter((i) => ['symbol', 'simbolo', 'symbol_candidate'].includes((i.item_type || '').toLowerCase())).length;
  const tableCount = items.filter((i) => ['table', 'tabla'].includes((i.item_type || '').toLowerCase())).length;
  const figureCount = items.filter((i) => ['figure', 'figura', 'image', 'sello', 'foto'].includes((i.item_type || '').toLowerCase())).length;
  const ruleCount = items.filter(isRuleItem).length;
  const pendingRulesCount = items.filter((i) => isRuleItem(i) && !['validada', 'active', 'accepted'].includes(i.status)).length;

  if (!isOpen) return null;

  return (
    <>
      <div
      style={{
        position: 'fixed',
        left: `${panelPos.x}px`,
        top: `${panelPos.y}px`,
        width: `${panelSize.width}px`,
        height: `${panelSize.height}px`,
        zIndex: 70,
        maxWidth: 'calc(100vw - 20px)',
        maxHeight: 'calc(100vh - 20px)',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#0f172a',
        color: '#f8fafc',
        border: '1px solid #334155',
        borderRadius: '1rem',
        boxShadow: '0 30px 80px -15px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
        userSelect: isDragging || isResizing ? 'none' : 'auto',
      }}
      className="overflow-hidden animate-in fade-in duration-150"
    >
      {/* Header Arrastrable (Drag Handle) */}
      <div
        onMouseDown={handleHeaderMouseDown}
        style={{
          cursor: isDragging ? 'grabbing' : 'grab',
          backgroundColor: '#020617',
          borderBottom: '1px solid #1e293b',
        }}
        className="px-5 py-3.5 flex items-center justify-between select-none"
      >
        <div className="flex items-center gap-2.5 text-teal-400">
          <GripHorizontal className="w-4 h-4 text-slate-500" />
          <div className="p-1.5 rounded-xl bg-teal-950 text-teal-400 border border-teal-800">
            <BookOpen className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2 flex-wrap">
              <span>Contenido Documental: {loading ? 'Cargando...' : (doc?.title || 'Norma')}</span>
              {!loading && !error && (
                <>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {contentResponse?.summary?.total_items ?? items.length} items
                  </span>
                  {(contentResponse?.summary?.rule_candidates ?? ruleCount) > 0 && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800">
                      ⚖️ {contentResponse?.summary?.rule_candidates ?? ruleCount} reglas
                    </span>
                  )}
                  {(contentResponse?.summary?.validated_rules ?? 0) > 0 && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-800">
                      🟢 {contentResponse?.summary?.validated_rules} validadas
                    </span>
                  )}
                  {(contentResponse?.summary?.promoted_rules ?? 0) > 0 && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                      🛡️ {contentResponse?.summary?.promoted_rules} en Baseline
                    </span>
                  )}
                  {(symbolCount > 0 || (contentResponse?.summary?.symbol_candidates || 0) > 0) && (
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800">
                      🔘 {contentResponse?.summary?.symbol_candidates ?? symbolCount} símb.
                    </span>
                  )}
                </>
              )}
            </h3>
            <p className="text-[11px] text-slate-400">
              Autoridad: {doc?.authority || 'N/A'} • Disciplina: {doc?.discipline || 'General'} • v{doc?.version || '1.0'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {ruleCount > 0 && (
            <button
              onClick={() => handleBulkValidateRules(selectedRuleIds.length > 0 ? selectedRuleIds : undefined)}
              disabled={bulkValidating || (pendingRulesCount === 0 && selectedRuleIds.length === 0)}
              className="px-2.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow transition-all"
              title={
                selectedRuleIds.length > 0
                  ? `Validar ${selectedRuleIds.length} regla(s) seleccionada(s)`
                  : pendingRulesCount > 0
                  ? `Validar en bloque todas las ${pendingRulesCount} reglas pendientes de este documento`
                  : 'Todas las reglas ya están validadas'
              }
            >
              {bulkValidating ? (
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
              ) : (
                <CheckCircle2 className="w-3.5 h-3.5" />
              )}
              <span>
                {selectedRuleIds.length > 0
                  ? `Validar Seleccionadas (${selectedRuleIds.length})`
                  : `Validar Reglas (${pendingRulesCount})`}
              </span>
            </button>
          )}

          {(symbolCount > 0 || (doc?.symbols_count || 0) > 0) && (
            <button
              onClick={() => setIsStudioOpen(true)}
              className="px-2.5 py-1.5 bg-gradient-to-r from-purple-700 to-indigo-600 hover:from-purple-600 hover:to-indigo-500 text-white rounded-lg text-xs font-bold flex items-center gap-1.5 shadow transition-all"
              title="Abrir estudio de curación HITL para símbolos y leyendas"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Curar Símbolos ({symbolCount || doc?.symbols_count})</span>
            </button>
          )}
          <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Panel Flotante</span>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg"
            title="Cerrar panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Barra de Filtros y Búsqueda */}
      <div
        style={{ backgroundColor: '#020617', borderBottom: '1px solid #1e293b' }}
        className="px-5 py-2.5 flex items-center justify-between gap-4 flex-wrap text-xs"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-slate-400 font-medium">Categoría:</span>
          <button
            onClick={() => setCategoryFilter('all')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              categoryFilter === 'all'
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Todos ({totalCount})
          </button>
          <button
            onClick={() => setCategoryFilter('rules')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              categoryFilter === 'rules'
                ? 'bg-sky-950 text-sky-300 border border-sky-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            ⚖️ Reglas ({ruleCount})
          </button>
          {symbolCount > 0 && (
            <button
              onClick={() => setCategoryFilter('symbols')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                categoryFilter === 'symbols'
                  ? 'bg-purple-950 text-purple-300 border border-purple-800 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              🔘 Símbolos ({symbolCount})
            </button>
          )}
          {tableCount > 0 && (
            <button
              onClick={() => setCategoryFilter('tables')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                categoryFilter === 'tables'
                  ? 'bg-cyan-950 text-cyan-300 border border-cyan-800'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              📊 Tablas ({tableCount})
            </button>
          )}
          {figureCount > 0 && (
            <button
              onClick={() => setCategoryFilter('figures')}
              className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                categoryFilter === 'figures'
                  ? 'bg-amber-950 text-amber-300 border border-amber-800'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              📐 Figuras ({figureCount})
            </button>
          )}

          <div className="h-4 w-px bg-slate-800 mx-1" />

          <span className="text-slate-400 font-medium">Estado:</span>
          <button
            onClick={() => setFilterStatus('all')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'all'
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Todos
          </button>
          <button
            onClick={() => setFilterStatus('validada')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'validada'
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🟢 Validadas ({items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length})
          </button>
          <button
            onClick={() => setFilterStatus('por_confirmar')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'por_confirmar'
                ? 'bg-amber-950 text-amber-300 border border-amber-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🟡 Por confirmar ({items.filter((i) => i.status === 'por_confirmar' || i.status === 'to_confirm' || i.status === 'draft').length})
          </button>
        </div>

        {/* Búsqueda rápida */}
        <div className="relative w-52">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
          <input
            type="text"
            placeholder="Buscar reglas o símbolos..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
            className="w-full pl-8 pr-3 py-1 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-teal-500 border"
          />
        </div>
      </div>

      {/* Cuerpo Principal: Lista de Reglas del Documento */}
      <div style={{ backgroundColor: '#0f172a' }} className="p-5 flex-1 overflow-y-auto space-y-3">
        
        {/* Mensaje de Éxito o Error */}
        {successMessage && (
          <div style={{ backgroundColor: '#064e3b', borderColor: '#047857' }} className="p-4 border rounded-xl text-center space-y-1 text-xs text-emerald-200">
            <CheckCircle2 className="w-6 h-6 text-emerald-400 mx-auto" />
            <p className="font-bold">{successMessage}</p>
          </div>
        )}

        {error && (
          <div style={{ backgroundColor: '#4c0519', borderColor: '#e11d48' }} className="p-5 border rounded-xl text-center space-y-3 text-xs text-rose-200">
            <AlertCircle className="w-8 h-8 text-rose-400 mx-auto" />
            <div>
              <p className="font-bold text-sm text-rose-100">Error al cargar el contenido del documento</p>
              <p className="text-slate-300 mt-1">{error}</p>
            </div>
            <div className="flex items-center justify-center gap-3 pt-2">
              <button
                onClick={() => ruleDocumentId && loadDocumentDetails(ruleDocumentId)}
                className="px-3.5 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg font-bold flex items-center gap-1.5 shadow transition-all"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Reintentar</span>
              </button>
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="px-3.5 py-1.5 bg-teal-700 hover:bg-teal-600 text-white rounded-lg font-bold flex items-center gap-1.5 shadow transition-all"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${reprocessing ? 'animate-spin' : ''}`} />
                <span>{reprocessing ? 'Reprocesando...' : 'Reprocesar Contenido'}</span>
              </button>
            </div>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-400" />
            <p className="text-xs">Cargando reglas y contenido estructurado del documento...</p>
          </div>
        ) : !error && items.length === 0 ? (
          <div className="p-10 border border-dashed border-slate-700 rounded-2xl text-center text-slate-400 space-y-4 my-4">
            <div className="p-3 bg-slate-800/80 rounded-2xl w-fit mx-auto text-teal-400 border border-slate-700">
              <BookOpen className="w-8 h-8" />
            </div>
            <div className="max-w-md mx-auto space-y-1">
              <h4 className="text-sm font-bold text-slate-200">Este documento no tiene contenido estructurado compatible</h4>
              <p className="text-xs text-slate-400">
                {contentResponse?.explanation_code === 'CONTENT_NOT_EXTRACTED'
                  ? 'Aún no se han estructurado reglas normativas ni candidatos para este documento incorporado.'
                  : contentResponse?.explanation_code === 'NO_RULE_CANDIDATES_FOUND'
                  ? 'Este documento solo contiene símbolos o figuras sin reglas prescriptivas extraídas.'
                  : 'Documento existente o legacy sin candidatos de reglas estructurados.'}
              </p>
            </div>
            <div className="pt-2">
              <button
                onClick={handleReprocess}
                disabled={reprocessing}
                className="px-4 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white font-bold text-xs rounded-xl flex items-center gap-2 mx-auto shadow-lg transition-all"
              >
                <RefreshCw className={`w-4 h-4 ${reprocessing ? 'animate-spin' : ''}`} />
                <span>{reprocessing ? 'Reprocesando contenido...' : 'Reprocesar contenido'}</span>
              </button>
            </div>
          </div>
        ) : !error && filteredItems.length === 0 ? (
          <div className="p-10 text-center text-slate-500 space-y-2">
            <AlertCircle className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-sm font-semibold text-slate-400">No hay reglas ni elementos en este filtro</p>
            <button
              onClick={() => { setCategoryFilter('all'); setFilterStatus('all'); setSearchTerm(''); }}
              className="text-xs text-teal-400 hover:underline font-semibold"
            >
              Restablecer filtros
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Banner de Validación Masiva Rápida para Reglas */}
            {pendingRulesCount > 0 && (categoryFilter === 'all' || categoryFilter === 'rules') && (
              <div
                style={{ backgroundColor: '#064e3b25', borderColor: '#05966955' }}
                className="p-3 rounded-xl border flex items-center justify-between gap-3 flex-wrap text-xs text-emerald-200 shadow-sm"
              >
                <div className="flex items-center gap-2.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <span className="font-semibold text-emerald-300">
                      {pendingRulesCount} regla(s) pendiente(s) de validación
                    </span>
                    <p className="text-[11px] text-emerald-400/80">
                      Valida en bloque para habilitar su confirmación y promoción hacia Baseline QA/QC del Sistema.
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {selectedRuleIds.length > 0 && (
                    <button
                      type="button"
                      onClick={() => setSelectedRuleIds([])}
                      className="px-2.5 py-1 text-[11px] text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800 transition-colors"
                    >
                      Deseleccionar ({selectedRuleIds.length})
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const allPendingIds = items.filter((i) => isRuleItem(i) && !['validada', 'active', 'accepted'].includes(i.status)).map((i) => i.id);
                      setSelectedRuleIds(selectedRuleIds.length === allPendingIds.length ? [] : allPendingIds);
                    }}
                    className="px-2.5 py-1 text-[11px] font-medium text-emerald-300 bg-emerald-950/60 hover:bg-emerald-900 border border-emerald-800/80 rounded-lg transition-colors"
                  >
                    {selectedRuleIds.length > 0 && selectedRuleIds.length === pendingRulesCount
                      ? 'Deseleccionar todas'
                      : `Seleccionar todas (${pendingRulesCount})`}
                  </button>
                  <button
                    type="button"
                    onClick={() => handleBulkValidateRules(selectedRuleIds.length > 0 ? selectedRuleIds : undefined)}
                    disabled={bulkValidating}
                    className="px-3 py-1 text-[11px] font-bold text-white bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 rounded-lg shadow flex items-center gap-1.5 transition-all disabled:opacity-50"
                  >
                    {bulkValidating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                    <span>
                      {selectedRuleIds.length > 0
                        ? `Validar Seleccionadas (${selectedRuleIds.length})`
                        : `Validar Todas (${pendingRulesCount})`}
                    </span>
                  </button>
                </div>
              </div>
            )}

            {filteredItems.map((item) => (
              <div
                key={item.id}
                style={{ backgroundColor: '#020617', borderColor: selectedRuleIds.includes(item.id) ? '#059669' : '#334155' }}
                className={`p-4 rounded-xl border flex items-start justify-between gap-4 transition-all ${
                  selectedRuleIds.includes(item.id) ? 'ring-1 ring-emerald-500/50' : 'hover:border-slate-600'
                }`}
              >
                {/* Checkbox de Selección Masiva para Reglas */}
                {isRuleItem(item) && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedRuleIds((prev) =>
                        prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]
                      );
                    }}
                    className="mt-1 p-0.5 text-slate-400 hover:text-teal-400 transition-colors shrink-0"
                    title={selectedRuleIds.includes(item.id) ? 'Deseleccionar regla' : 'Seleccionar regla para acción masiva'}
                  >
                    {selectedRuleIds.includes(item.id) ? (
                      <CheckSquare className="w-4 h-4 text-emerald-400" />
                    ) : (
                      <Square className="w-4 h-4 text-slate-600 hover:text-slate-400" />
                    )}
                  </button>
                )}
                {/* Contenido: Recorte Visual + Metadatos y Enunciado */}
                {(() => {
                  const cropPath = item.crop_image_path || item.metadata_payload?.crop_image_path;
                  const isSymbol = ['symbol', 'simbolo', 'symbol_candidate'].includes((item.item_type || '').toLowerCase());
                  const needsCrop = (item as any).completeness_status === 'needs_visual_crop' || item.metadata_payload?.needs_visual_crop || (isSymbol && !cropPath);
                  const rowIndex = item.metadata_payload?.row_index;
                  const colIndex = item.metadata_payload?.col_index;
                  const stdRef = item.metadata_payload?.standard_reference;

                  return (
                    <div className="flex flex-col sm:flex-row items-start gap-3 flex-1 min-w-0">
                      {/* Recorte Visual */}
                      {cropPath ? (
                        <div
                          onClick={() => setZoomImage(cropPath)}
                          className="relative group shrink-0 w-20 h-20 sm:w-24 sm:h-24 bg-white border border-slate-700 rounded-xl overflow-hidden flex items-center justify-center cursor-zoom-in shadow-md hover:border-purple-500 transition-all"
                          title="Click para ampliar recorte en alta definición"
                        >
                          <img
                            src={cropPath.startsWith('http') ? cropPath : cropPath.startsWith('/') ? cropPath : `/${cropPath}`}
                            alt={item.title}
                            className="w-full h-full object-contain p-1 filter contrast-125"
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                          <div className="absolute inset-0 bg-purple-950/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-all">
                            <Eye className="w-5 h-5 text-white drop-shadow" />
                          </div>
                        </div>
                      ) : isSymbol ? (
                        <div className="shrink-0 w-20 h-20 sm:w-24 sm:h-24 bg-rose-950/30 border border-rose-800/60 rounded-xl flex flex-col items-center justify-center p-2 text-center text-[10px] text-rose-400">
                          <AlertCircle className="w-5 h-5 mb-1 text-rose-400" />
                          <span>Sin crop visual</span>
                        </div>
                      ) : null}

                      {/* Metadatos y Enunciado */}
                      <div className="space-y-1.5 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {getItemTypeBadge(item.item_type)}
                          <span className="text-xs font-bold text-slate-200">
                            {item.title}
                          </span>
                          {item.code_or_number && (
                            <span style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="font-mono text-[10px] px-1.5 py-0.5 rounded text-slate-400 border">
                              {item.code_or_number}
                            </span>
                          )}
                          {rowIndex !== undefined && rowIndex !== null && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 font-medium">
                              📊 Tabla: Fila {rowIndex}{colIndex !== undefined && colIndex !== null ? `, Col ${colIndex}` : ''}
                            </span>
                          )}
                          {stdRef && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 font-medium">
                              🏷️ {stdRef}
                            </span>
                          )}
                          {isSymbol && item.metadata_payload?.geometric_evidence && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-teal-950 text-teal-300 border border-teal-800 font-medium flex items-center gap-1">
                              📐 Geometría validada {item.metadata_payload?.geometric_confidence ? `(${Math.round(item.metadata_payload.geometric_confidence * 100)}%)` : ''}
                            </span>
                          )}
                          {item.metadata_payload?.requires_human_review && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 font-medium">
                              ⚠️ Requiere validación
                            </span>
                          )}
                          {needsCrop && (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-700 font-bold animate-pulse">
                              ⚠️ Recorte visual requerido
                            </span>
                          )}
                        </div>

                        {/* Ocurrencias clicables multipágina / multicelda */}
                        {item.metadata_payload?.occurrences && item.metadata_payload.occurrences.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                            <span className="text-[10px] text-slate-400 font-semibold">Ocurrencias ({item.metadata_payload.occurrences.length}):</span>
                            {item.metadata_payload.occurrences.map((occ: any, oIdx: number) => (
                              <span
                                key={occ.occurrence_id || oIdx}
                                className="text-[10px] px-2 py-0.5 rounded-full bg-slate-900 text-slate-300 border border-slate-700 font-mono"
                              >
                                {occ.source_reference || `Pág. ${occ.page_number}`}
                              </span>
                            ))}
                          </div>
                        )}

                        {(item.description || item.content_text) && (
                          <p className="text-xs text-slate-300 leading-relaxed font-sans">
                            {item.description || item.content_text}
                          </p>
                        )}

                        {item.ocr_text && item.ocr_text !== item.description && (
                          <div style={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }} className="p-2 border rounded-lg text-[11px] font-mono text-slate-400">
                            <span className="text-[10px] uppercase font-bold text-slate-500 block">Texto Fuente / OCR:</span>
                            <p className="line-clamp-2">{item.ocr_text}</p>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })()}

                {/* Acciones Individuales por Regla */}
                <div className="flex flex-col items-end gap-2 shrink-0">
                  <div className="flex items-center gap-1.5 flex-wrap justify-end">
                    {item.promoted_rule_definition_id || item.promotion_status === 'promoted' ? (
                      <span className="px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-700 text-[10px] font-bold flex items-center gap-1 shadow-sm">
                        <ShieldCheck className="w-3 h-3 text-purple-400" />
                        <span>✓ En Baseline QA/QC</span>
                      </span>
                    ) : item.promotion_status === 'promoted_draft' ? (
                      <span className="px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-700 text-[10px] font-bold flex items-center gap-1">
                        <Clock className="w-3 h-3 text-amber-400" />
                        <span>⏳ En Revisión Baseline</span>
                      </span>
                    ) : null}
                    <div>{getStatusBadge(item.status)}</div>
                  </div>

                  <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="flex items-center gap-1.5 p-1 rounded-xl border flex-wrap justify-end">
                    
                    {/* 1. EDITAR */}
                    <button
                      onClick={() => handleStartEdit(item)}
                      className="px-2 py-1 text-[11px] font-semibold text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg flex items-center gap-1 transition-all"
                      title="Editar campos de la regla"
                    >
                      <Edit3 className="w-3 h-3 text-sky-400" />
                      <span>Editar</span>
                    </button>

                    {/* 2. POR CONFIRMAR */}
                    <button
                      onClick={() => handleUpdateItemStatus(item, 'por_confirmar')}
                      className={`px-2 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                        item.status === 'por_confirmar' || item.status === 'to_confirm' || item.status === 'draft'
                          ? 'bg-amber-950 text-amber-300 border border-amber-800'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                      title="Dejar pendiente para validar después"
                    >
                      <Clock className="w-3 h-3" />
                      <span>Por confirmar</span>
                    </button>

                    {/* 3. VALIDAR CONTENIDO */}
                    <button
                      onClick={() => handleUpdateItemStatus(item, 'validada')}
                      className={`px-2 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                        item.status === 'validada' || item.status === 'accepted' || item.status === 'active'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                      title="Validar contenido de la regla en este documento"
                    >
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span>Validar contenido</span>
                    </button>

                    {/* 4. PROMOVER A BASELINE (Solo para reglas, nunca símbolos) */}
                    {!['symbol', 'simbolo', 'symbol_candidate'].includes((item.item_type || '').toLowerCase()) && (
                      <button
                        onClick={() => handleOpenPromotion(item)}
                        className={`px-2.5 py-1 text-[11px] font-bold rounded-lg flex items-center gap-1 transition-all shadow-sm ${
                          item.promoted_rule_definition_id || item.promotion_status === 'promoted'
                            ? 'bg-purple-900/80 hover:bg-purple-800 text-purple-200 border border-purple-600'
                            : 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white'
                        }`}
                        title="Promover regla candidata hacia RuleDefinition y Baseline QA/QC del Sistema"
                      >
                        <ShieldCheck className="w-3 h-3 text-purple-300" />
                        <span>{item.promoted_rule_definition_id ? 'Re-promover' : 'Promover a Baseline'}</span>
                      </button>
                    )}

                    {/* 5. ELIMINAR */}
                    <button
                      onClick={() => handleUpdateItemStatus(item, 'eliminado')}
                      className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950 rounded-lg transition-all"
                      title="Eliminar regla del documento"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Modal de Edición de Regla Individual */}
        {editingItem && (
          <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.75)' }} className="fixed inset-0 z-80 flex items-center justify-center p-4">
            <div
              style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
              className="w-full max-w-lg p-5 border rounded-2xl shadow-2xl space-y-4 text-xs"
            >
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <Edit3 className="w-4 h-4 text-sky-400" />
                  <span>Editar Regla del Documento</span>
                </h4>
                <button onClick={() => setEditingItem(null)} className="text-slate-400 hover:text-slate-200">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Título de la Regla</label>
                  <input
                    type="text"
                    value={editTitle}
                    onChange={(e) => setEditTitle(e.target.value)}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Código Identificador</label>
                    <input
                      type="text"
                      value={editCode}
                      onChange={(e) => setEditCode(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 font-mono focus:outline-none focus:border-sky-500"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Tipo</label>
                    <select
                      value={editType}
                      onChange={(e) => setEditType(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500"
                    >
                      <option value="rule">⚖️ Regla QA/QC</option>
                      <option value="article">📜 Artículo</option>
                      <option value="requirement">✅ Requisito</option>
                      <option value="restriction">⛔ Restricción</option>
                      <option value="text_note">📝 Nota Técnica</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Enunciado / Descripción Técnica</label>
                  <textarea
                    rows={3}
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-3 py-1.5 text-slate-400 hover:text-slate-200"
                >
                  Cancelar
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  className="px-4 py-1.5 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-xl shadow flex items-center gap-1.5"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>Guardar Cambios</span>
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Modal de Promoción de Regla Candidata a Baseline QA/QC */}
        {promotingItem && (
          <div style={{ backgroundColor: 'rgba(0, 0, 0, 0.85)' }} className="fixed inset-0 z-[90] flex items-center justify-center p-4 animate-in fade-in duration-150">
            <div
              style={{ backgroundColor: '#0f172a', borderColor: '#6366f1' }}
              className="w-full max-w-2xl max-h-[92vh] overflow-y-auto p-6 border rounded-2xl shadow-2xl space-y-4 text-xs"
            >
              {/* Header */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 rounded-xl bg-purple-950/80 border border-purple-800 text-purple-300">
                    <ShieldCheck className="w-5 h-5 text-purple-400" />
                  </div>
                  <div>
                    <h3 className="font-bold text-sm text-slate-100">
                      Promover Regla Candidata a Baseline QA/QC del Sistema
                    </h3>
                    <p className="text-[11px] text-slate-400">
                      Vincular formalmente al catálogo canónico de reglas de revisión y asociar aplicabilidad aprobada.
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setPromotingItem(null)}
                  className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Mensaje de Éxito al promover */}
              {promSuccess && (
                <div className="p-3 rounded-xl bg-emerald-950/80 border border-emerald-700 text-emerald-200 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                  <div>
                    <p className="font-bold">¡Regla promovida exitosamente a Baseline QA/QC!</p>
                    <p className="text-[11px] text-emerald-300">
                      Código: <strong>{promSuccess.rule_code}</strong> • Estado Baseline: <strong>{promSuccess.baseline_status}</strong>.
                    </p>
                  </div>
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Grid de Metadatos Inmutables Derivados de DB */}
              <div style={{ backgroundColor: '#020617', borderColor: '#1e293b' }} className="p-4 rounded-xl border space-y-2">
                <div className="flex items-center justify-between text-[11px] text-slate-400 border-b border-slate-800/80 pb-1.5">
                  <span className="font-semibold text-slate-300 uppercase tracking-wider">Metadatos de Linaje Fuente (Inmutables de DB)</span>
                  <span className="font-mono text-purple-400">ID: {promotingItem.id.substring(0, 8)}...</span>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-[11px]">
                  <div>
                    <span className="text-slate-500 block">Documento Fuente:</span>
                    <span className="text-slate-200 font-semibold truncate block" title={doc?.title || 'Fuente'}>{doc?.title || 'N/A'}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Autoridad / Versión:</span>
                    <span className="text-slate-200 font-medium">{doc?.authority || 'N/A'} (v{doc?.version || '1.0'})</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Ubicación / Página:</span>
                    <span className="text-sky-300 font-mono font-bold">Pág. {promotingItem.metadata_payload?.page_number || 1}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 block">Evidencia BBox:</span>
                    <span className="text-slate-300 font-mono text-[10px]">
                      {promotingItem.metadata_payload?.bbox ? 'Detectado en DB' : 'Referencia textual'}
                    </span>
                  </div>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px] uppercase font-bold mt-1">Extracto Normativo Fuente:</span>
                  <p className="text-xs text-slate-300 bg-slate-900/80 p-2 rounded-lg border border-slate-800 italic font-serif leading-relaxed">
                    «{promotingItem.content_text || promotingItem.description || promotingItem.title}»
                  </p>
                </div>
              </div>

              {/* Formulario de Especificación de Regla */}
              <div className="space-y-3 pt-1">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <div className="sm:col-span-2">
                    <label className="block font-semibold text-slate-300 mb-1">Título de la Regla en Baseline</label>
                    <input
                      type="text"
                      value={promTitle}
                      onChange={(e) => setPromTitle(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    />
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Código Canónico</label>
                    <input
                      type="text"
                      value={promCode}
                      onChange={(e) => setPromCode(e.target.value.toUpperCase())}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-purple-300 font-mono font-bold focus:outline-none focus:border-purple-500 uppercase"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Disciplina</label>
                    <select
                      value={promDiscipline}
                      onChange={(e) => setPromDiscipline(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    >
                      <option value="GENERAL">GENERAL</option>
                      <option value="ARCHITECTURE">ARQUITECTURA</option>
                      <option value="STRUCTURES">ESTRUCTURAS</option>
                      <option value="PIPING">TUBERÍAS / PIPING</option>
                      <option value="HVAC">CLIMATIZACIÓN / HVAC</option>
                      <option value="ELECTRICAL">ELECTRICIDAD</option>
                      <option value="CIVIL">CIVIL</option>
                      <option value="FIRE_PROTECTION">PROTECCIÓN INCENDIO</option>
                      <option value="SANITARY">SANITARIA</option>
                      <option value="BIM_COORDINATION">BIM</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Tópico de Revisión</label>
                    <select
                      value={promTopic}
                      onChange={(e) => setPromTopic(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    >
                      <option value="REGULATORY_COMPLIANCE">Cumplimiento Normativo</option>
                      <option value="DOCUMENT_COMPLETENESS">Completitud Documental</option>
                      <option value="COORDINATION">Coordinación Especialidades</option>
                      <option value="SAFETY">Seguridad y Evacuación</option>
                      <option value="CONSTRUCTABILITY">Constructabilidad</option>
                      <option value="PID_SYMBOLS">Simbología P&ID</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Fase de Ejecución</label>
                    <select
                      value={promPhase}
                      onChange={(e) => setPromPhase(Number(e.target.value))}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    >
                      <option value={1}>Fase 1: Viñetas y Rótulos</option>
                      <option value={2}>Fase 2: Identificación Planos</option>
                      <option value={3}>Fase 3: Geometría</option>
                      <option value={4}>Fase 4: Tablas y Listados</option>
                      <option value={5}>Fase 5: Simbología</option>
                      <option value={6}>Fase 6: Reglas Normativas (Default)</option>
                      <option value={7}>Fase 7: Verificaciones Cruzadas</option>
                      <option value={8}>Fase 8: Cierre y Emisión</option>
                    </select>
                  </div>

                  <div>
                    <label className="block font-semibold text-slate-300 mb-1">Severidad Default</label>
                    <select
                      value={promSeverity}
                      onChange={(e) => setPromSeverity(e.target.value)}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    >
                      <option value="critical">Crítica</option>
                      <option value="high">Alta (Mayor)</option>
                      <option value="medium">Media</option>
                      <option value="low">Baja</option>
                      <option value="info">Informativa</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block font-semibold text-slate-300 mb-1">Razón y Criterio del Revisor (Auditoría HITL)</label>
                  <textarea
                    rows={2}
                    value={promRationale}
                    onChange={(e) => setPromRationale(e.target.value)}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-purple-500"
                    placeholder="Indique justificación técnica para incorporar esta regla al Baseline QA/QC..."
                  />
                </div>

                {/* Previsualización del Estado Futuro */}
                <div style={{ backgroundColor: '#020617', borderColor: '#1e293b' }} className="p-3 rounded-xl border flex items-center justify-between text-[11px]">
                  <div>
                    <span className="text-slate-400 block font-semibold">Estado Futuro según Acción:</span>
                    <span className="text-emerald-400 font-bold">
                      {promAction === 'promote_and_activate'
                        ? '✓ Baseline Activo (Aprobada) • Inmediatamente ejecutable en One-Click Review'
                        : '⏳ Borrador de Revisión (Pending) • Requiere visto bueno de Lead/Admin'}
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setPromAction('promote_for_review')}
                      className={`px-2 py-1 rounded-lg border text-[10px] font-semibold transition-all ${
                        promAction === 'promote_for_review'
                          ? 'bg-amber-950 text-amber-300 border-amber-700'
                          : 'text-slate-400 border-slate-700 hover:text-white'
                      }`}
                    >
                      Revisión (Draft)
                    </button>
                    <button
                      type="button"
                      onClick={() => setPromAction('promote_and_activate')}
                      className={`px-2 py-1 rounded-lg border text-[10px] font-semibold transition-all ${
                        promAction === 'promote_and_activate'
                          ? 'bg-emerald-950 text-emerald-300 border-emerald-700'
                          : 'text-slate-400 border-slate-700 hover:text-white'
                      }`}
                    >
                      Activar en Baseline
                    </button>
                  </div>
                </div>
              </div>

              {/* Botones de Acción */}
              <div className="flex flex-wrap items-center justify-between gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    handleUpdateItemStatus(promotingItem, 'validada');
                    setPromotingItem(null);
                  }}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl"
                  title="Sólo valida el contenido local sin crear regla en Baseline"
                >
                  Validar contenido solamente
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPromotingItem(null)}
                    className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
                  >
                    Cancelar
                  </button>

                  <button
                    type="button"
                    disabled={promSubmitting}
                    onClick={() => handleSubmitPromotion('promote_for_review')}
                    className="px-3 py-1.5 text-xs font-semibold text-amber-300 bg-amber-950/80 hover:bg-amber-900 border border-amber-700 rounded-xl flex items-center gap-1.5"
                  >
                    <Clock className="w-3.5 h-3.5" />
                    <span>Promover para revisión baseline</span>
                  </button>

                  <button
                    type="button"
                    disabled={promSubmitting}
                    onClick={() => handleSubmitPromotion('promote_and_activate')}
                    className="px-4 py-1.5 text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 rounded-xl shadow-lg flex items-center gap-1.5"
                  >
                    {promSubmitting ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <ShieldCheck className="w-3.5 h-3.5" />}
                    <span>Promover y activar en Baseline QA/QC</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Footer de la Ventana Contenido */}
      <div
        style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
        className="px-5 py-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 relative"
      >
        <div className="text-xs text-slate-400 max-w-md">
          <strong>«Validar Contenido»:</strong> valida las reglas en este documento. <strong>«Promover a Baseline QA/QC»:</strong> publica y activa las reglas en el motor global y One-Click Review.
        </div>

        <div className="flex items-center gap-2.5 flex-wrap justify-end">
          <button
            onClick={onClose}
            className="px-3.5 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 rounded-xl"
          >
            Cerrar
          </button>

          {/* Acción 1: Validar Contenido */}
          <button
            onClick={handleConfirmDocumentContent}
            disabled={saving || items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length === 0}
            className="px-4 py-2 text-xs font-bold text-teal-200 bg-teal-950/80 hover:bg-teal-900 border border-teal-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow flex items-center gap-1.5"
            title="Confirma el contenido validado dentro del documento normativo"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
            <span>
              Validar Contenido ({items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length})
            </span>
          </button>

          {/* Acción 2: Promover o Re-sincronizar Documento Completo a Baseline QA/QC */}
          {doc?.status === 'promovido_baseline' ? (
            <div className="flex items-center gap-2">
              <button
                onClick={() => handleOpenScopeModal('resync')}
                disabled={saving}
                className="px-3.5 py-2 text-xs font-bold text-emerald-200 bg-emerald-950/80 hover:bg-emerald-900 border border-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow flex items-center gap-1.5"
                title="Re-sincronizar y reparar la disciplina y punto de revisión de todas las reglas promovidas en el motor"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Re-sincronizar Alcance</span>
              </button>
              <button
                onClick={() => handleOpenScopeModal('promote')}
                disabled={saving}
                className="px-4 py-2 text-xs font-bold text-white bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg flex items-center gap-1.5"
                title="Sincronizar y actualizar reglas hacia Baseline QA/QC del Sistema"
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Sincronizar Baseline</span>
              </button>
            </div>
          ) : (
            <button
              onClick={() => handleOpenScopeModal('promote')}
              disabled={saving || items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length === 0}
              className="px-4 py-2 text-xs font-bold text-white bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg flex items-center gap-1.5"
              title="Promover y activar todas las reglas validadas hacia Baseline QA/QC del Sistema con alcance explícito"
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Promover Documento a Baseline QA/QC</span>
            </button>
          )}
        </div>

        {/* Handle Resize */}
        <div
          onMouseDown={handleResizeMouseDown}
          style={{ cursor: 'nwse-resize' }}
          className="absolute bottom-1 right-1 p-1 text-slate-500 hover:text-slate-300 transition-colors select-none"
          title="Arrastrar para redimensionar panel"
        >
          <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M8 2L2 8M8 5L5 8M8 8L8 8" strokeLinecap="round" />
          </svg>
        </div>
      </div>
    </div>

    {/* Modal de Selección y Confirmación de Alcance (Disciplina + Tópico) */}
    {showScopeModal && ruleDocumentId && (
      <PromoteDocumentScopeModal
        isOpen={showScopeModal}
        onClose={() => setShowScopeModal(false)}
        mode={scopeModalMode}
        documentId={ruleDocumentId}
        documentTitle={doc?.title || 'Documento Normativo'}
        documentDiscipline={doc?.discipline}
        rulesCount={items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length || doc?.rules_count || 0}
        onSuccess={handleScopeSuccess}
      />
    )}

    {/* Estudio de Curación HITL para Símbolos */}
    {isStudioOpen && (
      <SymbolCurationStudioModal
        isOpen={isStudioOpen}
        extractionId={doc?.source_extraction_id || null}
        ruleDocumentId={ruleDocumentId}
        onClose={() => {
          setIsStudioOpen(false);
          if (ruleDocumentId) {
            loadDocumentDetails(ruleDocumentId);
          }
        }}
      />
    )}

    {/* Lightbox de Zoom para Recorte Visual de Símbolo */}
    {zoomImage && (
      <div
        onClick={() => setZoomImage(null)}
        className="fixed inset-0 z-[100] flex items-center justify-center bg-black/85 backdrop-blur-md p-4 animate-in fade-in duration-150"
      >
        <div
          onClick={(e) => e.stopPropagation()}
          className="relative max-w-xl max-h-[85vh] bg-slate-900 border border-purple-500/50 rounded-2xl p-5 shadow-2xl flex flex-col items-center gap-3"
        >
          <button
            onClick={() => setZoomImage(null)}
            className="absolute top-3 right-3 p-1.5 rounded-full bg-slate-800 text-slate-300 hover:text-white hover:bg-slate-700 transition-all"
            title="Cerrar vista previa"
          >
            <X className="w-5 h-5" />
          </button>
          <h4 className="text-xs font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
            <Eye className="w-4 h-4" /> Inspección de Recorte Visual de Alta Definición
          </h4>
          <div className="bg-white rounded-xl p-4 flex items-center justify-center border border-slate-700 max-w-full overflow-auto">
            <img
              src={zoomImage.startsWith('http') ? zoomImage : zoomImage.startsWith('/') ? zoomImage : `/${zoomImage}`}
              alt="Recorte ampliado"
              className="max-h-[60vh] max-w-full object-contain filter contrast-125"
            />
          </div>
          <p className="text-[11px] text-slate-400 font-mono text-center truncate max-w-full">
            Recorte verificado: {zoomImage}
          </p>
        </div>
      </div>
    )}
  </>
  );
};
