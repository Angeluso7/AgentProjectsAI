import React, { useState, useEffect, useRef } from 'react';
import {
  X, Check, Trash2, Edit3, Search, Filter, Layers, BookOpen,
  CheckCircle2, AlertCircle, Clock, Eye, BookmarkPlus, ArrowRight,
  Database, HelpCircle, GripHorizontal, Crop, Shapes, Table as TableIcon,
  FileText, ShieldCheck, Loader2, Sparkles, Building2, Tag, ChevronRight
} from 'lucide-react';
import { ManualAnnotation, DocumentSheet } from '../types';
import { TAXONOMY_COLORS, getAnnotationColor } from '../pages/PlanViewerPage';
import { apiService } from '../services/api';

interface PlanSelectionsModalProps {
  isOpen: boolean;
  projectId: string;
  projectName: string;
  projectCode: string;
  selections: ManualAnnotation[];
  availableSheets: DocumentSheet[];
  onClose: () => void;
  onEdit: (selection: ManualAnnotation) => void;
  onDelete: (selectionId: string) => void;
  onValidate: (selectionId: string) => void;
  onIncorporateSuccess: (result: any) => void;
}

export const PlanSelectionsModal: React.FC<PlanSelectionsModalProps> = ({
  isOpen,
  projectId,
  projectName,
  projectCode,
  selections,
  availableSheets,
  onClose,
  onEdit,
  onDelete,
  onValidate,
  onIncorporateSuccess,
}) => {
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterSheetId, setFilterSheetId] = useState<string>('all');
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [incorporating, setIncorporating] = useState<boolean>(false);
  const [savingKbId, setSavingKbId] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Panel Flotante Arrastrable y Redimensionable
  const [panelPos, setPanelPos] = useState<{ x: number; y: number }>({ x: 90, y: 60 });
  const [panelSize, setPanelSize] = useState<{ width: number; height: number }>({ width: 880, height: 680 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 90, posY: 60 });
  const resizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 880, height: 680 });

  // Manejo de drag
  const handleHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select')) return;
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

  // Manejo de Incorporación Documental
  const handleIncorporateValidated = async () => {
    const validated = selections.filter((s) => s.status === 'validada' || s.status === 'confirmed');
    if (validated.length === 0) {
      setErrorMsg('No hay selecciones validadas para incorporar. Haz clic en "Validar" en las selecciones deseadas.');
      return;
    }

    setIncorporating(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      const res = await apiService.incorporateSelectionsToProjectDocument({
        project_id: projectId,
        annotation_ids: validated.map((v) => v.id),
      });

      setSuccessMsg(res.message);
      onIncorporateSuccess(res);
      setTimeout(() => {
        setSuccessMsg(null);
      }, 3500);
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Error al incorporar selecciones al proyecto.');
    } finally {
      setIncorporating(false);
    }
  };

  // Estado para Deduplicación y Normalización Visual
  const [dedupModalOpen, setDedupModalOpen] = useState(false);
  const [selectedForKb, setSelectedForKb] = useState<ManualAnnotation | null>(null);
  const [dedupCheckResult, setDedupCheckResult] = useState<any | null>(null);
  const [customCategory, setCustomCategory] = useState('');
  const [customAliases, setCustomAliases] = useState('');
  const [relatedRuleCode, setRelatedRuleCode] = useState('');

  const handleStartSaveToKb = async (sel: ManualAnnotation) => {
    try {
      setSavingKbId(sel.id);
      setErrorMsg(null);
      setSelectedForKb(sel);
      setCustomCategory(sel.name.toLowerCase().replace(/\s+/g, '_').slice(0, 30));
      setCustomAliases(sel.name);

      // Check deduplication
      const dedupRes = await apiService.checkVisualDeduplication({
        name: sel.name,
        discipline: sel.discipline || 'general',
        element_type: sel.element_type || 'symbol'
      });

      if (dedupRes.has_potential_duplicates && dedupRes.matches.length > 0) {
        setDedupCheckResult(dedupRes);
        setDedupModalOpen(true);
      } else {
        // Direct save as new item
        await executeSaveToKb(sel, 'create_new', undefined);
      }
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Error verificando duplicados en catálogo.');
    } finally {
      setSavingKbId(null);
    }
  };

  const executeSaveToKb = async (
    sel: ManualAnnotation,
    mode: 'create_new' | 'link_occurrence' | 'new_version',
    targetItemId?: string
  ) => {
    try {
      setSavingKbId(sel.id);
      setErrorMsg(null);
      const sheet = availableSheets.find(s => s.id === sel.sheet_id);
      
      const aliasesList = customAliases
        ? customAliases.split(',').map(a => a.trim()).filter(Boolean)
        : [sel.name];

      await apiService.captureFromViewerToKnowledge({
        project_id: projectId,
        document_id: sel.document_id,
        sheet_id: sel.sheet_id,
        sheet_code: sheet?.sheet_code || (sheet ? `LAM-#${sheet.sheet_number}` : undefined),
        page_number: sheet?.sheet_number || 1,
        bbox_normalized: sel.bbox_normalized,
        element_type: (sel.element_type as any) || 'symbol',
        name: sel.name,
        normalized_category: customCategory || undefined,
        aliases: aliasesList,
        description: sel.description,
        discipline: sel.discipline || 'general',
        domain: sel.element_type === 'symbol' ? 'symbol_knowledge' : (sel.element_type === 'table' ? 'template_knowledge' : 'symbol_knowledge'),
        legend_text: sel.ocr_text || sel.description,
        related_rule_code: relatedRuleCode || undefined,
        auto_approve: true, // Guardar y habilitar inmediatamente para el asistente
        deduplication_mode: mode,
        target_existing_item_id: targetItemId
      });

      setDedupModalOpen(false);
      setDedupCheckResult(null);
      setSelectedForKb(null);

      if (mode === 'link_occurrence') {
        setSuccessMsg(`✓ Ocurrencia de «${sel.name}» vinculada exitosamente al conocimiento existente.`);
      } else {
        setSuccessMsg(`✓ «${sel.name}» guardado y normalizado en la Base de Conocimiento Operacional.`);
      }
      setTimeout(() => setSuccessMsg(null), 4000);
    } catch (err: any) {
      setErrorMsg(err?.response?.data?.detail || 'Error guardando en Base de Conocimiento.');
    } finally {
      setSavingKbId(null);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'validada':
      case 'confirmed':
        return (
          <span className="px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[10px] font-bold flex items-center gap-1">
            🟢 Validada (Proyecto)
          </span>
        );
      case 'editada':
        return (
          <span className="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700 text-[10px] font-bold flex items-center gap-1">
            🔵 Editada
          </span>
        );
      case 'draft':
      case 'capturada':
      default:
        return (
          <span className="px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-700 text-[10px] font-bold flex items-center gap-1">
            🟡 Capturada / Draft
          </span>
        );
    }
  };

  const getSheetLabel = (sheetId: string) => {
    const sheet = availableSheets.find((s) => s.id === sheetId);
    if (!sheet) return `Lámina ${sheetId.slice(0, 6)}`;
    return `Lámina #${sheet.sheet_number} (${sheet.sheet_code || 'S/C'})`;
  };

  const filteredSelections = selections.filter((s) => {
    if (filterSheetId !== 'all' && s.sheet_id !== filterSheetId) return false;
    if (filterStatus === 'validada' && s.status !== 'validada' && s.status !== 'confirmed') return false;
    if (filterStatus === 'draft' && s.status !== 'draft' && s.status !== 'capturada') return false;
    if (filterStatus === 'editada' && s.status !== 'editada') return false;

    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase();
      const matchName = s.name.toLowerCase().includes(q);
      const matchType = s.element_type.toLowerCase().includes(q);
      const matchDesc = s.description?.toLowerCase().includes(q) || s.ocr_text?.toLowerCase().includes(q);
      return matchName || matchType || matchDesc;
    }
    return true;
  });

  const validatedCount = selections.filter((s) => s.status === 'validada' || s.status === 'confirmed').length;

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: 'fixed',
        left: `${panelPos.x}px`,
        top: `${panelPos.y}px`,
        width: `${panelSize.width}px`,
        height: `${panelSize.height}px`,
        zIndex: 85,
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
        <div className="flex items-center gap-2.5 text-sky-400">
          <GripHorizontal className="w-4 h-4 text-slate-500" />
          <div className="p-1.5 rounded-xl bg-sky-950 text-sky-400 border border-sky-800">
            <Crop className="w-4 h-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
              <span>Selecciones Documentadas del Visor de Planos</span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                {selections.length} elementos
              </span>
            </h3>
            <p className="text-[11px] text-slate-400 flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-sky-400" />
              <span>Proyecto: <strong className="text-slate-200">{projectName}</strong> ({projectCode})</span>
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Panel Flotante</span>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
            title="Cerrar panel de selecciones"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Barra de Filtros, Selector de Lámina y Búsqueda */}
      <div
        style={{ backgroundColor: '#020617', borderBottom: '1px solid #1e293b' }}
        className="px-5 py-2.5 flex items-center justify-between gap-3 flex-wrap text-xs"
      >
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-slate-400 font-medium">Filtrar:</span>
          <button
            onClick={() => setFilterStatus('all')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'all'
                ? 'bg-slate-800 text-white'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Todos ({selections.length})
          </button>
          <button
            onClick={() => setFilterStatus('validada')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'validada'
                ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🟢 Validadas ({validatedCount})
          </button>
          <button
            onClick={() => setFilterStatus('draft')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'draft'
                ? 'bg-amber-950 text-amber-300 border border-amber-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🟡 Capturadas ({selections.filter((s) => s.status === 'draft' || s.status === 'capturada').length})
          </button>
          <button
            onClick={() => setFilterStatus('editada')}
            className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
              filterStatus === 'editada'
                ? 'bg-indigo-950 text-indigo-300 border border-indigo-800'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            🔵 Editadas ({selections.filter((s) => s.status === 'editada').length})
          </button>
        </div>

        <div className="flex items-center gap-2">
          {/* Selector de Lámina */}
          {availableSheets.length > 0 && (
            <select
              value={filterSheetId}
              onChange={(e) => setFilterSheetId(e.target.value)}
              style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
              className="px-2.5 py-1 rounded-lg text-slate-300 border text-xs focus:outline-none focus:border-sky-500"
            >
              <option value="all">Todas las Láminas</option>
              {availableSheets.map((s) => (
                <option key={s.id} value={s.id}>
                  Lámina #{s.sheet_number} ({s.sheet_code || 'S/C'})
                </option>
              ))}
            </select>
          )}

          {/* Búsqueda rápida */}
          <div className="relative w-48">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
            <input
              type="text"
              placeholder="Buscar selección..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
              className="w-full pl-8 pr-3 py-1 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-sky-500 border"
            />
          </div>
        </div>
      </div>

      {/* Cuerpo Principal: Lista de Elementos Seleccionados */}
      <div style={{ backgroundColor: '#0f172a' }} className="p-5 flex-1 overflow-y-auto space-y-3">
        {/* Mensajes de Notificación */}
        {successMsg && (
          <div style={{ backgroundColor: '#064e3b', borderColor: '#047857' }} className="p-3.5 border rounded-xl text-center space-y-1 text-xs text-emerald-200 flex items-center justify-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
            <span className="font-bold">{successMsg}</span>
          </div>
        )}

        {errorMsg && (
          <div style={{ backgroundColor: '#881337', borderColor: '#be123c' }} className="p-3.5 border rounded-xl text-center space-y-1 text-xs text-rose-200 flex items-center justify-center gap-2">
            <AlertCircle className="w-5 h-5 text-rose-400 shrink-0" />
            <span className="font-bold">{errorMsg}</span>
          </div>
        )}

        {filteredSelections.length === 0 ? (
          <div className="p-12 text-center text-slate-500 space-y-2">
            <Crop className="w-10 h-10 mx-auto text-slate-600 opacity-60" />
            <p className="text-sm font-semibold text-slate-300">No hay selecciones documentadas en esta vista</p>
            <p className="text-xs text-slate-500 max-w-md mx-auto">
              Activa la herramienta <strong>"Selección"</strong> en el visor de planos y arrastra un marco sobre cualquier símbolo, tabla, viñeta o nota técnica para documentarla.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredSelections.map((sel) => {
              const color = getAnnotationColor(sel.element_type);
              const isValidated = sel.status === 'validada' || sel.status === 'confirmed';

              return (
                <div
                  key={sel.id}
                  style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                  className="p-4 rounded-xl border hover:border-slate-600 flex items-start justify-between gap-4 transition-all"
                >
                  {/* Thumbnail si existe */}
                  {sel.crop_image_path && (
                    <div style={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }} className="w-20 h-20 rounded-lg border overflow-hidden shrink-0 flex items-center justify-center p-1">
                      <img
                        src={`http://localhost:8000/${sel.crop_image_path.replace(/^\.\//, '')}`}
                        alt={sel.name}
                        className="max-w-full max-h-full object-contain"
                        onError={(e) => {
                          e.currentTarget.style.display = 'none';
                        }}
                      />
                    </div>
                  )}

                  {/* Metadatos y Enunciado */}
                  <div className="space-y-1.5 flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span
                        style={{
                          backgroundColor: `${color}20`,
                          color: color,
                          borderColor: `${color}60`,
                        }}
                        className="px-2 py-0.5 rounded text-[10px] font-bold border uppercase tracking-wider"
                      >
                        {TAXONOMY_COLORS[sel.element_type]?.label || sel.element_type}
                      </span>
                      <strong className="text-xs font-bold text-slate-100">{sel.name}</strong>
                      <span style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="text-[10px] font-mono px-2 py-0.5 rounded text-slate-400 border">
                        {getSheetLabel(sel.sheet_id)}
                      </span>
                    </div>

                    {sel.description && (
                      <p className="text-xs text-slate-300 leading-relaxed font-sans">
                        {sel.description}
                      </p>
                    )}

                    {sel.ocr_text && sel.ocr_text !== sel.description && (
                      <div style={{ backgroundColor: '#0f172a', borderColor: '#1e293b' }} className="p-2 border rounded-lg text-[11px] font-mono text-slate-400">
                        <span className="text-[10px] uppercase font-bold text-slate-500 block">Texto / OCR Extraído:</span>
                        <p className="line-clamp-2">{sel.ocr_text}</p>
                      </div>
                    )}
                  </div>

                  {/* Acciones por Elemento: Editar, Eliminar, Validar */}
                  <div className="flex flex-col items-end gap-2.5 shrink-0">
                    <div>{getStatusBadge(sel.status)}</div>

                    <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="flex items-center gap-1.5 p-1 rounded-xl border">
                      
                      {/* 1. EDITAR */}
                      <button
                        onClick={() => onEdit(sel)}
                        className="px-2.5 py-1 text-[11px] font-semibold text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg flex items-center gap-1 transition-all"
                        title="Reabrir ventana original para corregir datos"
                      >
                        <Edit3 className="w-3 h-3 text-sky-400" />
                        <span>Editar</span>
                      </button>

                      {/* 2. VALIDAR */}
                      <button
                        onClick={() => onValidate(sel.id)}
                        className={`px-2.5 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                          isValidated
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'
                            : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                        }`}
                        title="Validar elemento para pasar a Información basada en proyecto"
                      >
                        <Check className="w-3 h-3 text-emerald-400" />
                        <span>{isValidated ? '✓ Validada' : 'Validar'}</span>
                      </button>

                      {/* 3. GUARDAR EN BASE DE CONOCIMIENTO (VISUAL INGESTION CON DEDUPLICACIÓN) */}
                      <button
                        onClick={() => handleStartSaveToKb(sel)}
                        disabled={savingKbId === sel.id}
                        className="px-2.5 py-1 text-[11px] font-semibold text-purple-300 hover:text-purple-100 hover:bg-purple-950/70 border border-purple-800/60 rounded-lg flex items-center gap-1 transition-all"
                        title="Convertir y guardar como Conocimiento de Símbolo / Detalle reutilizable por el Asistente"
                      >
                        <Sparkles className="w-3 h-3 text-purple-400" />
                        <span>{savingKbId === sel.id ? 'Comprobando...' : 'Guardar en Base Conocimiento'}</span>
                      </button>

                      {/* 4. ELIMINAR */}
                      <button
                        onClick={() => onDelete(sel.id)}
                        className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950 rounded-lg transition-all"
                        title="Eliminar selección del visor y de la lista"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* MODAL DE DEDUPLICACIÓN & NORMALIZACIÓN VISUAL */}
      {dedupModalOpen && selectedForKb && dedupCheckResult && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-slate-900 border border-purple-500/50 rounded-2xl p-5 space-y-4 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-purple-400" />
                <h3 className="text-sm font-bold text-slate-100">
                  Deduplicación & Normalización de Símbolo
                </h3>
              </div>
              <button
                onClick={() => setDedupModalOpen(false)}
                className="p-1 text-slate-400 hover:text-white rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3.5 rounded-xl bg-purple-950/40 border border-purple-800/60 text-xs space-y-2">
              <p className="text-purple-200 font-semibold">
                ⚠ Se detectaron elementos coincidentes en el catálogo visual:
              </p>
              {dedupCheckResult.matches.map((match: any) => (
                <div key={match.item_id} className="p-2.5 rounded-lg bg-black/50 border border-purple-900/60 flex items-center justify-between gap-3">
                  <div>
                    <strong className="text-slate-100 block">{match.title}</strong>
                    <span className="text-[10px] text-slate-400 font-mono">
                      Categoría: {match.normalized_category} • {match.total_occurrences} ocurrencias previas
                    </span>
                  </div>
                  <div className="text-right">
                    <span className="px-2 py-0.5 rounded bg-purple-900/80 text-purple-300 font-bold text-[10px]">
                      {(match.similarity_score * 100).toFixed(0)}% similitud
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="space-y-2 text-xs">
              <p className="text-slate-300 font-semibold">¿Cómo deseas procesar este elemento?</p>
              <div className="space-y-2">
                <button
                  onClick={() => executeSaveToKb(selectedForKb, 'link_occurrence', dedupCheckResult.matches[0]?.item_id)}
                  className="w-full p-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold text-xs flex items-center justify-between transition shadow"
                >
                  <div className="text-left">
                    <span className="block">🔗 Vincular Ocurrencia a «{dedupCheckResult.matches[0]?.title}»</span>
                    <span className="text-[10px] font-normal text-purple-200">Recomendado: No duplica la entidad; añade la lámina actual como nueva ocurrencia.</span>
                  </div>
                  <ChevronRight className="w-4 h-4" />
                </button>

                <button
                  onClick={() => executeSaveToKb(selectedForKb, 'new_version', dedupCheckResult.matches[0]?.item_id)}
                  className="w-full p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs flex items-center justify-between border border-slate-700 transition"
                >
                  <div className="text-left">
                    <span className="block">🔀 Crear Variante / Nueva Versión (v2)</span>
                    <span className="text-[10px] font-normal text-slate-400">Si el símbolo tiene cambios de geometría o especificación técnica.</span>
                  </div>
                  <ChevronRight className="w-4 h-4" />
                </button>

                <button
                  onClick={() => executeSaveToKb(selectedForKb, 'create_new', undefined)}
                  className="w-full p-2.5 rounded-xl bg-slate-900 hover:bg-slate-800 text-slate-400 hover:text-slate-200 text-xs flex items-center justify-between border border-slate-800 transition"
                >
                  <div className="text-left">
                    <span className="block">➕ Crear como Nuevo Ítem Independiente</span>
                    <span className="text-[10px] font-normal text-slate-500">Si es un elemento completamente distinto.</span>
                  </div>
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Footer de la Ventana Selecciones */}
      <div
        style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
        className="px-5 py-3.5 flex items-center justify-between relative flex-wrap gap-3"
      >
        <div className="text-xs text-slate-400 max-w-lg leading-relaxed">
          Las selecciones validadas se incorporarán como <strong>«Información basada en proyecto {projectName}»</strong> dentro de <strong>Documentos Nativos & Fuentes Incorporados</strong>.
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 rounded-xl"
          >
            Cerrar
          </button>

          <button
            onClick={handleIncorporateValidated}
            disabled={incorporating || validatedCount === 0}
            className="px-5 py-2 text-xs font-bold text-white bg-gradient-to-r from-sky-600 to-teal-600 hover:from-sky-500 hover:to-teal-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg flex items-center gap-2"
          >
            {incorporating ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
            <span>
              Incorporar a Documentos del Proyecto ({validatedCount} Validadas)
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
  );
};
