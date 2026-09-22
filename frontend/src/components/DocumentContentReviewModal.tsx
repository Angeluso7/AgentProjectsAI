import React, { useState, useEffect, useRef } from 'react';
import {
  X, Check, Trash2, Edit3, ShieldAlert, Sparkles, BookOpen,
  Filter, Layers, CheckCircle2, AlertCircle, Clock, Eye,
  Table as TableIcon, Shapes, FileText, BookmarkPlus, ArrowRight,
  Database, HelpCircle, Globe, ExternalLink, ShieldCheck, Link2,
  Search, RefreshCw, GripHorizontal, SquareCheck, Loader2, Save
} from 'lucide-react';
import { apiService } from '../services/api';
import { RuleDocument, RuleDocumentItem } from '../types';
import { SymbolCurationStudioModal } from './SymbolCurationStudioModal';

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
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Filtros y Búsqueda
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [categoryFilter, setCategoryFilter] = useState<'all' | 'rules' | 'symbols' | 'tables' | 'figures'>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [isStudioOpen, setIsStudioOpen] = useState(false);
  const [zoomImage, setZoomImage] = useState<string | null>(null);

  // Estado de Edición de Regla Individual
  const [editingItem, setEditingItem] = useState<RuleDocumentItem | null>(null);
  const [editTitle, setEditTitle] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editType, setEditType] = useState('rule');

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
      const data = await apiService.getRuleDocumentDetail(id);
      setDoc(data);
      setItems(data.items || []);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Error al cargar el contenido del documento.');
    } finally {
      setLoading(false);
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

  const totalCount = items.length;
  const symbolCount = items.filter((i) => ['symbol', 'simbolo', 'symbol_candidate'].includes((i.item_type || '').toLowerCase())).length;
  const tableCount = items.filter((i) => ['table', 'tabla'].includes((i.item_type || '').toLowerCase())).length;
  const figureCount = items.filter((i) => ['figure', 'figura', 'image', 'sello', 'foto'].includes((i.item_type || '').toLowerCase())).length;
  const ruleCount = items.filter((i) => !['symbol', 'simbolo', 'symbol_candidate', 'table', 'tabla', 'figure', 'figura', 'image', 'sello', 'foto'].includes((i.item_type || '').toLowerCase())).length;

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
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
              <span>Contenido Documental: {doc?.title || 'Cargando...'}</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {items.length} items
              </span>
              {(symbolCount > 0 || (doc?.symbols_count || 0) > 0) && (
                <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-purple-950 text-purple-300 border border-purple-800">
                  🔘 {symbolCount || doc?.symbols_count} símb.
                </span>
              )}
            </h3>
            <p className="text-[11px] text-slate-400">
              Autoridad: {doc?.authority || 'N/A'} • Disciplina: {doc?.discipline || 'General'} • v{doc?.version || '1.0'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
          <div style={{ backgroundColor: '#881337', borderColor: '#be123c' }} className="p-4 border rounded-xl text-center space-y-1 text-xs text-rose-200">
            <AlertCircle className="w-6 h-6 text-rose-400 mx-auto" />
            <p className="font-bold">{error}</p>
          </div>
        )}

        {loading ? (
          <div className="flex flex-col items-center justify-center h-48 gap-2 text-slate-400">
            <Loader2 className="w-6 h-6 animate-spin text-teal-400" />
            <p className="text-xs">Cargando reglas y contenido del documento...</p>
          </div>
        ) : filteredItems.length === 0 ? (
          <div className="p-10 text-center text-slate-500 space-y-2">
            <AlertCircle className="w-8 h-8 mx-auto text-slate-600" />
            <p className="text-sm font-semibold text-slate-400">No hay reglas en este filtro</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredItems.map((item) => (
              <div
                key={item.id}
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="p-4 rounded-xl border hover:border-slate-600 flex items-start justify-between gap-4 transition-all"
              >
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
                  <div>{getStatusBadge(item.status)}</div>

                  <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="flex items-center gap-1.5 p-1 rounded-xl border">
                    
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

                    {/* 3. VALIDADA */}
                    <button
                      onClick={() => handleUpdateItemStatus(item, 'validada')}
                      className={`px-2 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                        item.status === 'validada' || item.status === 'accepted' || item.status === 'active'
                          ? 'bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'
                          : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                      title="Marcar como confirmada en este documento"
                    >
                      <Check className="w-3 h-3 text-emerald-400" />
                      <span>Validada</span>
                    </button>

                    {/* 4. ELIMINAR */}
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
      </div>

      {/* Footer de la Ventana Contenido */}
      <div
        style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
        className="px-5 py-3.5 flex items-center justify-between relative"
      >
        <div className="text-xs text-slate-400 max-w-lg">
          Al hacer clic en <strong>«Aceptar y Confirmar Contenido»</strong> se validan las reglas vigentes en este documento normativo. Para promoverlas al <strong>Baseline QA/QC Global</strong>, usa el botón «Aceptar» en el renglón del documento.
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 rounded-xl"
          >
            Cancelar
          </button>

          <button
            onClick={handleConfirmDocumentContent}
            disabled={saving || items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length === 0}
            className="px-5 py-2 text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg flex items-center gap-2"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
            <span>
              Aceptar y Confirmar Contenido ({items.filter((i) => i.status === 'validada' || i.status === 'accepted' || i.status === 'active').length} Validadas)
            </span>
          </button>
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
