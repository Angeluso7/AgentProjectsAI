import React, { useState, useEffect, useRef } from 'react';
import {
  Tag,
  Type,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Save,
  Shapes,
  Table as TableIcon,
  LayoutGrid,
  FileText,
  BookmarkPlus,
  Layers,
  Sparkles,
  GripHorizontal,
  ScanText,
  Crosshair,
  RotateCcw
} from 'lucide-react';
import { apiService } from '../services/api';
import { ManualAnnotation } from '../types';

export type AnnotationElementType =
  | 'symbol'
  | 'table'
  | 'layout_region'
  | 'text_note'
  | 'title_block'
  | 'legend'
  | 'view_elevation_plan'
  | 'stamp_signature'
  | 'diagram_sketch'
  | 'other';

export interface DisciplineOption {
  id: string;
  label: string;
}

const DEFAULT_DISCIPLINES: DisciplineOption[] = [
  { id: 'general', label: 'General' },
  { id: 'architecture', label: 'Arquitectura' },
  { id: 'structural', label: 'Estructura' },
  { id: 'electrical', label: 'Electricidad' },
  { id: 'plumbing', label: 'Sanitario' },
  { id: 'hvac', label: 'Climatización' },
];

const DISCIPLINE_STORAGE_KEY = 'custom_annotation_disciplines';

export const normalizeDisciplineSlug = (text: string): string => {
  return text
    .toLowerCase()
    .trim()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '');
};

const DEFAULT_NAMES_LIST = [
  'Nuevo Símbolo',
  'Cuadro Técnico',
  'Zona de Dibujo',
  'Nota General',
  'Viñeta Principal',
  'Leyenda de Símbolos',
  'Planta / Elevación',
  'Sello de Aprobación',
  'Croquis de Ubicación',
  'Elemento Extraído',
];

interface AnnotationClassifyModalProps {
  isOpen: boolean;
  cropImageBase64: string | null;
  bboxNormalized: [number, number, number, number];
  bboxPixels?: [number, number, number, number];
  sheetId: string;
  projectId: string;
  documentId: string;
  initialData?: Partial<ManualAnnotation> | null;
  onClose: () => void;
  onSaved: (annotation: any) => void;
  onAddToList?: (item: any) => void;
  // OCR desde Plano General (Visor Principal)
  onRequestPlanTextCapture?: () => void;
  isCapturingPlanText?: boolean;
  externalCapturedText?: string | { text: string; timestamp?: number } | null;
}

export const AnnotationClassifyModal: React.FC<AnnotationClassifyModalProps> = ({
  isOpen,
  cropImageBase64,
  bboxNormalized,
  bboxPixels,
  sheetId,
  projectId,
  documentId,
  initialData,
  onClose,
  onSaved,
  onAddToList,
  onRequestPlanTextCapture,
  isCapturingPlanText = false,
  externalCapturedText = null,
}) => {
  const [elementType, setElementType] = useState<AnnotationElementType>('symbol');
  const [name, setName] = useState<string>('');
  const [description, setDescription] = useState<string>('');
  const [discipline, setDiscipline] = useState<string>('general');
  const [tagsInput, setTagsInput] = useState<string>('');
  const [ocrText, setOcrText] = useState<string>('');
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [ocrEngine, setOcrEngine] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Estados para Disciplinas Dinámicas y Persistentes
  const [availableDisciplines, setAvailableDisciplines] = useState<DisciplineOption[]>(() => {
    try {
      const stored = localStorage.getItem(DISCIPLINE_STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          const merged = [...DEFAULT_DISCIPLINES];
          parsed.forEach((p: DisciplineOption) => {
            if (p?.id && !merged.some((m) => m.id.toLowerCase() === p.id.toLowerCase())) {
              merged.push(p);
            }
          });
          return merged;
        }
      }
    } catch (e) {
      console.warn('Error reading stored disciplines:', e);
    }
    return DEFAULT_DISCIPLINES;
  });

  const [isAddingDiscipline, setIsAddingDiscipline] = useState<boolean>(false);
  const [newDisciplineInput, setNewDisciplineInput] = useState<string>('');
  const [newDisciplineError, setNewDisciplineError] = useState<string | null>(null);

  // Estados para OCR enfocado en "Nombre o Descripción"
  const [pendingOcrPrompt, setPendingOcrPrompt] = useState<{ detectedText: string; previousText: string } | null>(null);
  const [quickOcrSuccessMsg, setQuickOcrSuccessMsg] = useState<string | null>(null);

  // Estado para panel flotante movible (Draggable Floating Panel)
  const [position, setPosition] = useState<{ x: number; y: number }>(() => {
    const defaultWidth = 560;
    const initialX = Math.max(20, typeof window !== 'undefined' ? window.innerWidth - defaultWidth - 30 : 600);
    const initialY = 70;
    return { x: initialX, y: initialY };
  });
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({
    startX: 0,
    startY: 0,
    posX: 0,
    posY: 0,
  });

  // Cargar disciplinas remotas al abrir
  useEffect(() => {
    if (isOpen) {
      apiService.getAnnotationDisciplines().then((remoteList) => {
        if (Array.isArray(remoteList) && remoteList.length > 0) {
          setAvailableDisciplines((prev) => {
            const merged = [...prev];
            remoteList.forEach((r) => {
              const slug = normalizeDisciplineSlug(r);
              if (slug && !merged.some((m) => m.id.toLowerCase() === slug.toLowerCase())) {
                const label = r.charAt(0).toUpperCase() + r.slice(1).replace(/_/g, ' ');
                merged.push({ id: slug, label });
              }
            });
            return merged;
          });
        }
      }).catch((e) => console.warn('Could not load remote disciplines:', e));
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      setPendingOcrPrompt(null);
      setQuickOcrSuccessMsg(null);
      setIsAddingDiscipline(false);
      setNewDisciplineInput('');
      setNewDisciplineError(null);

      if (initialData) {
        const initialDisc = initialData.discipline || 'general';
        setElementType((initialData.element_type as AnnotationElementType) || 'symbol');
        setName(initialData.name || '');
        setDescription(initialData.description || '');
        setDiscipline(initialDisc);
        setTagsInput(initialData.tags ? initialData.tags.join(', ') : '');
        setOcrText(initialData.ocr_text || '');

        // Asegurar que la disciplina inicial esté en la lista disponible
        const dSlug = normalizeDisciplineSlug(initialDisc);
        setAvailableDisciplines((prev) => {
          if (!prev.some((p) => p.id.toLowerCase() === dSlug.toLowerCase())) {
            const label = initialDisc.charAt(0).toUpperCase() + initialDisc.slice(1).replace(/_/g, ' ');
            return [...prev, { id: dSlug, label }];
          }
          return prev;
        });
      } else {
        setElementType('symbol');
        setName(getDefaultName('symbol'));
        setDescription('');
        setDiscipline('general');
        setTagsInput('');
        setOcrText('');
      }
    }
  }, [isOpen, initialData]);

  // Al recibir texto capturado desde el plano general del visor
  useEffect(() => {
    if (externalCapturedText) {
      const textToApply = typeof externalCapturedText === 'string'
        ? externalCapturedText
        : externalCapturedText.text;
      if (textToApply) {
        applyQuickOcrText(textToApply);
      }
    }
  }, [externalCapturedText]);

  // Manejo de arrastre suave del panel flotante
  const handleHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input')) return;
    e.preventDefault();
    setIsDragging(true);
    dragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: position.x,
      posY: position.y,
    };
  };

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      const dx = e.clientX - dragRef.current.startX;
      const dy = e.clientY - dragRef.current.startY;
      const newX = Math.min(
        Math.max(10, dragRef.current.posX + dx),
        window.innerWidth - 320
      );
      const newY = Math.min(
        Math.max(10, dragRef.current.posY + dy),
        window.innerHeight - 100
      );
      setPosition({ x: newX, y: newY });
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  if (!isOpen) return null;

  function getDefaultName(type: AnnotationElementType): string {
    switch (type) {
      case 'symbol': return 'Nuevo Símbolo';
      case 'table': return 'Cuadro Técnico';
      case 'layout_region': return 'Zona de Dibujo';
      case 'text_note': return 'Nota General';
      case 'title_block': return 'Viñeta Principal';
      case 'legend': return 'Leyenda de Símbolos';
      case 'view_elevation_plan': return 'Planta / Elevación';
      case 'stamp_signature': return 'Sello de Aprobación';
      case 'diagram_sketch': return 'Croquis de Ubicación';
      default: return 'Elemento Extraído';
    }
  }

  const handleRunOcr = async () => {
    if (!cropImageBase64) return;
    setOcrLoading(true);
    setError(null);
    try {
      const res = await apiService.runCropOcr(cropImageBase64, sheetId);
      setOcrText(res.text || '');
      setOcrEngine(res.engine_used);
    } catch (err: any) {
      console.error('Error ejecutando OCR en recorte:', err);
      setError('No se pudo ejecutar OCR automático. Puedes ingresar el texto manualmente.');
    } finally {
      setOcrLoading(false);
    }
  };

  // Aplica el texto reconocido hacia el campo "Nombre o Descripción"
  const applyQuickOcrText = (detectedText: string) => {
    const trimmed = detectedText.trim();
    if (!trimmed) return;
    const isCurrentDefault = !name.trim() || DEFAULT_NAMES_LIST.includes(name.trim());
    if (isCurrentDefault) {
      setName(trimmed);
      setPendingOcrPrompt(null);
      setQuickOcrSuccessMsg(`Texto insertado desde el plano: "${trimmed}"`);
      setTimeout(() => setQuickOcrSuccessMsg(null), 3500);
    } else {
      setPendingOcrPrompt({
        detectedText: trimmed,
        previousText: name.trim(),
      });
    }
  };

  const handleConfirmNewDiscipline = () => {
    const trimmed = newDisciplineInput.trim();
    if (!trimmed) {
      setNewDisciplineError('Ingrese el nombre de la disciplina');
      return;
    }
    const slug = normalizeDisciplineSlug(trimmed);
    if (!slug) {
      setNewDisciplineError('Nombre no válido');
      return;
    }

    const existing = availableDisciplines.find(
      (d) => d.id.toLowerCase() === slug.toLowerCase() || d.label.toLowerCase() === trimmed.toLowerCase()
    );

    if (existing) {
      setDiscipline(existing.id);
      setIsAddingDiscipline(false);
      setNewDisciplineInput('');
      setNewDisciplineError(null);
      return;
    }

    const newOpt: DisciplineOption = {
      id: slug,
      label: trimmed.charAt(0).toUpperCase() + trimmed.slice(1),
    };

    const updated = [...availableDisciplines, newOpt];
    setAvailableDisciplines(updated);
    try {
      localStorage.setItem(DISCIPLINE_STORAGE_KEY, JSON.stringify(updated));
    } catch (e) {
      console.warn('Error saving custom discipline to storage:', e);
    }

    setDiscipline(newOpt.id);
    setIsAddingDiscipline(false);
    setNewDisciplineInput('');
    setNewDisciplineError(null);
  };

  const getPayload = () => {
    const tags = tagsInput
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

    return {
      project_id: projectId,
      document_id: documentId,
      sheet_id: sheetId,
      bbox_normalized: bboxNormalized,
      bbox_pixels: bboxPixels || [],
      crop_image_base64: cropImageBase64 || undefined,
      element_type: elementType,
      name: name.trim() || getDefaultName(elementType),
      description: description.trim() || undefined,
      ocr_text: ocrText.trim() || undefined,
      discipline: discipline,
      tags: tags,
      status: 'confirmed',
    };
  };

  const handleSaveDirect = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = getPayload();
      let result;
      if (initialData?.id) {
        result = await apiService.updateManualAnnotation(initialData.id, payload);
      } else {
        result = await apiService.createManualAnnotation(payload);
      }
      onSaved(result);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al guardar la anotación.');
    } finally {
      setSaving(false);
    }
  };

  const handleAddToList = () => {
    if (onAddToList) {
      const payload = getPayload();
      onAddToList(payload);
      onClose();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        zIndex: 90,
        width: '560px',
        maxWidth: 'calc(100vw - 24px)',
        maxHeight: 'calc(100vh - 40px)',
        display: 'flex',
        flexDirection: 'column',
        backgroundColor: '#0f172a',
        color: '#f8fafc',
        border: '1px solid #334155',
        borderRadius: '1rem',
        boxShadow: '0 25px 60px -10px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
        userSelect: isDragging ? 'none' : 'auto',
      }}
      className="overflow-hidden animate-in fade-in duration-150"
    >
      {/* Encabezado Arrastrable (Draggable Header) */}
      <div
        onMouseDown={handleHeaderMouseDown}
        style={{
          cursor: isDragging ? 'grabbing' : 'grab',
          backgroundColor: '#020617',
          borderBottom: '1px solid #1e293b',
        }}
        className="px-5 py-3.5 flex items-center justify-between select-none"
        title="Haz clic y arrastra para mover el panel por la pantalla"
      >
        <div className="flex items-center space-x-2.5">
          <GripHorizontal className="w-4 h-4 text-slate-500 hover:text-slate-300 transition-colors" />
          <div className="p-1.5 rounded-lg bg-teal-500/10 text-teal-400">
            <BookmarkPlus className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xs font-bold text-slate-100 uppercase tracking-wide">
                {initialData?.id ? 'Editar Selección de Elemento' : 'Clasificación de Elemento Seleccionado'}
              </h2>
              {isCapturingPlanText && (
                <span className="text-[9px] font-bold text-amber-300 bg-amber-950/80 px-1.5 py-0.5 rounded border border-amber-700 animate-pulse flex items-center gap-1">
                  <Crosshair className="w-2.5 h-2.5" />
                  <span>Seleccionando en Plano...</span>
                </span>
              )}
            </div>
            <p className="text-[10px] text-slate-400">
              Panel flotante movible • Sólido oscuro
            </p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          title="Cerrar panel"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Cuerpo Desplazable del Panel */}
      <div className="p-5 overflow-y-auto space-y-3.5 max-h-[calc(100vh-160px)]">
        {error && (
          <div className="p-2.5 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {/* Grid: Preview del Recorte a la izquierda, Clasificación a la derecha */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
          {/* Preview Recorte */}
          <div className="space-y-1.5">
            <label className="block text-xs font-semibold text-slate-300">
              Vista Previa del Recorte
            </label>
            <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-center min-h-[140px] max-h-[180px] overflow-hidden">
              {cropImageBase64 ? (
                <img
                  src={cropImageBase64}
                  alt="Recorte seleccionado"
                  className="max-h-[160px] max-w-full object-contain rounded border border-slate-700/50 shadow"
                />
              ) : initialData?.crop_image_path ? (
                <img
                  src={`http://localhost:8000/${initialData.crop_image_path.replace(/^\.\//, '')}`}
                  alt="Recorte persistido"
                  className="max-h-[160px] max-w-full object-contain rounded border border-slate-700/50 shadow"
                  onError={(e) => {
                    e.currentTarget.style.display = 'none';
                  }}
                />
              ) : (
                <div className="text-slate-500 text-xs text-center">
                  Sin imagen directa de recorte
                </div>
              )}
            </div>
            <p className="text-[10px] font-mono text-slate-400 text-center">
              BBox: [{(Array.isArray(bboxNormalized) ? bboxNormalized : [0, 0, 0, 0]).map((n) => typeof n === 'number' ? n.toFixed(3) : n).join(', ')}]
            </p>
          </div>

          {/* Clasificación Principal */}
          <div className="space-y-2.5">
            <div>
              <label className="block text-xs font-semibold text-slate-300 mb-1">
                Tipo de Elemento (Taxonomía)
              </label>
              <select
                value={elementType}
                onChange={(e) => setElementType(e.target.value as AnnotationElementType)}
                className="w-full px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500 font-medium"
              >
                <option value="symbol">🔘 Símbolo (Simbología técnica)</option>
                <option value="table">📊 Tabla / Cuadro de Datos</option>
                <option value="layout_region">📐 Región / Formato de Lámina</option>
                <option value="text_note">📝 Texto / Nota / Observación</option>
                <option value="title_block">🏷️ Viñeta / Title Block / Rótulo</option>
                <option value="legend">📑 Leyenda / Simbología Agrupada</option>
                <option value="view_elevation_plan">🏢 Vista / Planta / Elevación / Sección</option>
                <option value="stamp_signature">✍️ Sello / Firma / Timbre Municipal</option>
                <option value="diagram_sketch">🗺️ Imagen / Croquis / Esquema</option>
                <option value="other">📦 Otro elemento no clasificado</option>
              </select>
            </div>

            {/* Campo "Nombre o Descripción" con Botón de OCR desde Plano General */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="block text-xs font-semibold text-slate-300">
                  Nombre o Descripción
                </label>
                {onRequestPlanTextCapture && (
                  <button
                    type="button"
                    onClick={onRequestPlanTextCapture}
                    className={`px-2 py-0.5 text-[10px] font-semibold rounded-lg border transition-all flex items-center gap-1 ${
                      isCapturingPlanText
                        ? 'bg-amber-500/20 text-amber-300 border-amber-500 shadow-sm shadow-amber-950/40 animate-pulse'
                        : 'bg-slate-900 hover:bg-slate-800 text-sky-400 border-sky-600/40 hover:border-sky-500'
                    }`}
                    title="Activa el cursor sobre el visor del plano general para trazar un recuadro de texto y extraerlo por OCR hacia este campo"
                  >
                    {isCapturingPlanText ? (
                      <Loader2 className="w-2.5 h-2.5 animate-spin text-amber-400" />
                    ) : (
                      <ScanText className="w-2.5 h-2.5 text-sky-400" />
                    )}
                    <span>{isCapturingPlanText ? 'Seleccionando en Plano...' : '⚡ OCR desde Plano'}</span>
                  </button>
                )}
              </div>

              <div className="relative">
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (pendingOcrPrompt) setPendingOcrPrompt(null);
                  }}
                  placeholder="Ej: Enchufe Doble 220V..."
                  className="w-full px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500 pr-8"
                />
                {name && (
                  <button
                    type="button"
                    onClick={() => setName('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 p-0.5"
                    title="Limpiar campo"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </div>

              {/* Mensaje de Éxito Inserción Directa */}
              {quickOcrSuccessMsg && (
                <p className="text-[10px] text-teal-400 mt-1 flex items-center gap-1 animate-in fade-in duration-150">
                  <CheckCircle2 className="w-3 h-3 text-teal-400 shrink-0" />
                  <span>{quickOcrSuccessMsg}</span>
                </p>
              )}

              {/* Banner de Confirmación / Reemplazo si el campo ya tenía contenido */}
              {pendingOcrPrompt && (
                <div className="mt-1.5 p-2 rounded-xl bg-slate-950 border border-sky-600/60 text-xs text-sky-200 space-y-1.5 animate-in fade-in duration-150 shadow-md">
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-semibold text-[10px] text-sky-300 flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-sky-400" />
                      Texto detectado en plano:
                    </span>
                    <span className="font-mono text-[10px] font-bold text-white bg-slate-900 px-1.5 py-0.5 rounded border border-sky-800 max-w-[170px] truncate">
                      «{pendingOcrPrompt.detectedText}»
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5 justify-end pt-0.5">
                    <button
                      type="button"
                      onClick={() => {
                        setName(pendingOcrPrompt.detectedText);
                        setPendingOcrPrompt(null);
                        setQuickOcrSuccessMsg(`Reemplazado por: "${pendingOcrPrompt.detectedText}"`);
                        setTimeout(() => setQuickOcrSuccessMsg(null), 3000);
                      }}
                      className="px-2 py-0.5 text-[10px] font-bold text-white bg-sky-600 hover:bg-sky-500 rounded-md transition-colors shadow-sm"
                    >
                      Reemplazar
                    </button>
                    <button
                      type="button"
                      onClick={() => {
                        const combined = `${name} - ${pendingOcrPrompt.detectedText}`;
                        setName(combined);
                        setPendingOcrPrompt(null);
                        setQuickOcrSuccessMsg(`Concatenado: "${combined}"`);
                        setTimeout(() => setQuickOcrSuccessMsg(null), 3000);
                      }}
                      className="px-2 py-0.5 text-[10px] font-bold text-sky-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-md transition-colors"
                    >
                      Concatenar
                    </button>
                    <button
                      type="button"
                      onClick={() => setPendingOcrPrompt(null)}
                      className="px-1.5 py-0.5 text-[10px] text-slate-400 hover:text-slate-200"
                    >
                      Descartar
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-xs font-semibold text-slate-300">
                    Disciplina
                  </label>
                  {!isAddingDiscipline && (
                    <button
                      type="button"
                      onClick={() => {
                        setIsAddingDiscipline(true);
                        setNewDisciplineInput('');
                        setNewDisciplineError(null);
                      }}
                      className="text-[10px] font-semibold text-teal-400 hover:text-teal-300 hover:underline flex items-center gap-0.5"
                      title="Agregar una nueva disciplina"
                    >
                      <span>+ Nueva</span>
                    </button>
                  )}
                </div>

                {isAddingDiscipline ? (
                  <div className="p-2 rounded-xl bg-slate-950 border border-teal-500/50 space-y-1.5 animate-in fade-in duration-150">
                    <input
                      type="text"
                      autoFocus
                      placeholder="Ej: Telecomunicaciones..."
                      value={newDisciplineInput}
                      onChange={(e) => {
                        setNewDisciplineInput(e.target.value);
                        if (newDisciplineError) setNewDisciplineError(null);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          handleConfirmNewDiscipline();
                        } else if (e.key === 'Escape') {
                          setIsAddingDiscipline(false);
                          setNewDisciplineError(null);
                        }
                      }}
                      className={`w-full px-2 py-1 text-xs rounded-lg bg-slate-900 border text-slate-200 focus:outline-none ${
                        newDisciplineError ? 'border-rose-500' : 'border-teal-600 focus:border-teal-400'
                      }`}
                    />
                    {newDisciplineError && (
                      <p className="text-[10px] text-rose-400">{newDisciplineError}</p>
                    )}
                    <div className="flex items-center justify-end gap-1.5 pt-0.5">
                      <button
                        type="button"
                        onClick={() => {
                          setIsAddingDiscipline(false);
                          setNewDisciplineError(null);
                        }}
                        className="px-2 py-0.5 text-[10px] text-slate-400 hover:text-slate-200"
                      >
                        Cancelar
                      </button>
                      <button
                        type="button"
                        onClick={handleConfirmNewDiscipline}
                        className="px-2 py-0.5 text-[10px] font-bold text-white bg-teal-600 hover:bg-teal-500 rounded-md transition-colors shadow-sm"
                      >
                        Agregar
                      </button>
                    </div>
                  </div>
                ) : (
                  <select
                    value={discipline}
                    onChange={(e) => {
                      if (e.target.value === '__ADD_NEW__') {
                        setIsAddingDiscipline(true);
                        setNewDisciplineInput('');
                        setNewDisciplineError(null);
                      } else {
                        setDiscipline(e.target.value);
                      }
                    }}
                    className="w-full px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                  >
                    {availableDisciplines.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.label}
                      </option>
                    ))}
                    <option value="__ADD_NEW__">+ Otra disciplina...</option>
                  </select>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">
                  Etiquetas
                </label>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="fuerza, 220v"
                  className="w-full px-2 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Sección OCR Integrado */}
        <div className="p-3 rounded-xl bg-slate-950/70 border border-slate-800 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
              <Type className="w-3.5 h-3.5 text-teal-400" />
              <span>Extracción OCR sobre el Recorte</span>
            </span>

            {cropImageBase64 && (
              <button
                type="button"
                onClick={handleRunOcr}
                disabled={ocrLoading}
                className="px-2.5 py-1 text-[11px] font-medium text-teal-300 bg-teal-950/80 hover:bg-teal-900 border border-teal-800 rounded-lg transition-all flex items-center gap-1.5 disabled:opacity-50"
              >
                {ocrLoading ? (
                  <Loader2 className="w-3 h-3 animate-spin" />
                ) : (
                  <Sparkles className="w-3 h-3" />
                )}
                <span>{ocrLoading ? 'Procesando...' : 'Ejecutar OCR'}</span>
              </button>
            )}
          </div>

          <textarea
            rows={2}
            value={ocrText}
            onChange={(e) => setOcrText(e.target.value)}
            placeholder="Texto detectado por OCR. Puedes corregirlo directamente."
            className="w-full p-2 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500 font-mono"
          />
          {ocrEngine && (
            <p className="text-[10px] text-teal-400">
              Motor: {ocrEngine}
            </p>
          )}
        </div>

        {/* Observaciones */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-1">
            Observaciones (Opcional)
          </label>
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Notas técnicas, norma o ubicación..."
            className="w-full px-2.5 py-1.5 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
          />
        </div>
      </div>

      {/* Footer con Acciones */}
      <div className="px-5 py-3 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
        <button
          type="button"
          onClick={onClose}
          className="px-3 py-1.5 text-xs font-medium text-slate-400 hover:text-slate-200 rounded-xl"
        >
          Cancelar
        </button>

        <div className="flex items-center space-x-2">
          {!initialData?.id && onAddToList && (
            <button
              type="button"
              onClick={handleAddToList}
              className="px-3 py-1.5 text-xs font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 rounded-xl border border-slate-700 transition-all flex items-center space-x-1.5"
            >
              <Layers className="w-3.5 h-3.5 text-sky-400" />
              <span>Añadir a Lote</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleSaveDirect}
            disabled={saving}
            className="px-4 py-1.5 text-xs font-semibold text-white bg-teal-600 hover:bg-teal-500 rounded-xl transition-all shadow-lg shadow-teal-950/50 flex items-center space-x-1.5 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
            <span>{initialData?.id ? 'Actualizar' : 'Guardar'}</span>
          </button>
        </div>
      </div>
    </div>
  );
};
