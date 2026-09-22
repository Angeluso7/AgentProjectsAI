import React, { useState, useEffect, useRef } from 'react';
import {
  X, ZoomIn, ZoomOut, RotateCcw, Maximize2, Sparkles, Search,
  Eye, Check, Save, AlertTriangle, CheckCircle2, HelpCircle,
  ExternalLink, Layers, MapPin, BookOpen, Loader2, ArrowDownToLine,
  Crop, Crosshair, ChevronRight, RefreshCw, Compass, Globe,
  Scissors
} from 'lucide-react';
import { apiService } from '../services/api';
import { ExtractedItem, ItemContextResponse, CandidateEnrichmentResponse } from '../types';
import { deduplicateText, stripTitleFromDescription } from '../utils/translationResolver';

interface ItemContextViewerModalProps {
  isOpen: boolean;
  extractionId: string | null;
  item: ExtractedItem | null;
  onClose: () => void;
  onItemUpdated?: (updatedItem: ExtractedItem) => void;
}

type OcrTargetField = 'title' | 'description' | 'function' | 'properties' | null;
type ViewerSelectionMode = 'none' | 'ocr' | 'split' | 'crop';

export const ItemContextViewerModal: React.FC<ItemContextViewerModalProps> = ({
  isOpen,
  extractionId,
  item,
  onClose,
  onItemUpdated,
}) => {
  const [currentItem, setCurrentItem] = useState<ExtractedItem | null>(item);
  const [contextData, setContextData] = useState<ItemContextResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [enriching, setEnriching] = useState<boolean>(false);
  const [ocrLoading, setOcrLoading] = useState<boolean>(false);
  const [isSplitting, setIsSplitting] = useState<boolean>(false);
  const [isCropping, setIsCropping] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Form Fields
  const [formTitle, setFormTitle] = useState('');
  const [formCode, setFormCode] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [formFunction, setFormFunction] = useState('');
  const [formProperties, setFormProperties] = useState('');
  const [formCompleteness, setFormCompleteness] = useState<string>('missing_data');
  const [formEnrichmentStatus, setFormEnrichmentStatus] = useState<string>('not_enriched');

  // Suggestion State
  const [suggestion, setSuggestion] = useState<CandidateEnrichmentResponse | null>(null);

  // Canvas / Viewer State (Zoom & Pan)
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [startPan, setStartPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Visual Selection Modes: 'none' | 'ocr' | 'split' | 'crop'
  const [selectionMode, setSelectionMode] = useState<ViewerSelectionMode>('none');
  const [ocrTargetField, setOcrTargetField] = useState<OcrTargetField>(null);
  const [isDrawingBox, setIsDrawingBox] = useState<boolean>(false);
  const [selectionBox, setSelectionBox] = useState<{ startX: number; startY: number; currentX: number; currentY: number } | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);

  useEffect(() => {
    if (isOpen && item) {
      setCurrentItem(item);
      const eff = item.effective_fields || (item.metadata_payload as any)?.effective_fields;
      setFormTitle(eff?.title || item.title || '');
      setFormCode(item.code_or_number || '');
      const rawDesc = eff?.description || item.description || item.content_text || '';
      const cleanDesc = stripTitleFromDescription(rawDesc, eff?.title || item.title);
      setFormDescription(cleanDesc);
      setFormFunction(eff?.function || '');
      if (extractionId) {
        loadContext(extractionId, item.id, item.page_number, item.bbox_normalized);
      }
    }
  }, [isOpen, extractionId, item]);

  // Keyboard navigation & close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        if (selectionMode !== 'none') {
          setSelectionMode('none');
          setOcrTargetField(null);
          setSelectionBox(null);
          setIsDrawingBox(false);
        } else {
          onClose();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, selectionMode, onClose]);

  const loadContext = async (extId: string, itemId: string, pageNum?: number, bboxNorm?: number[]) => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    setZoom(1);
    setPan({ x: 0, y: 0 });
    setSelectionMode('none');
    setSelectionBox(null);
    try {
      const data: ItemContextResponse = await apiService.getItemContext(extId, itemId, pageNum, bboxNorm);
      setContextData(data);
      const eff = data.effective_fields;
      setFormTitle(eff?.title || data.title || '');
      setFormCode(data.code_or_number || '');
      const rawDesc = eff?.description || data.description || '';
      const cleanDesc = stripTitleFromDescription(rawDesc, eff?.title || data.title);
      setFormDescription(cleanDesc);
      setFormFunction(eff?.function || data.technical_parameters?.function_or_role || '');
      setFormProperties(
        data.technical_parameters
          ? JSON.stringify(data.technical_parameters, null, 2)
          : ''
      );
      setFormCompleteness(data.completeness_status || 'missing_data');
      setFormEnrichmentStatus(data.enrichment_status || 'not_enriched');

      if (data.suggested_title || data.suggested_description) {
        setSuggestion({
          item_id: data.item_id,
          enrichment_status: data.enrichment_status,
          completeness_status: data.completeness_status,
          match_confidence: data.match_confidence,
          suggested_title: data.suggested_title,
          suggested_description: data.suggested_description,
          suggested_function: data.suggested_function,
          suggested_source_label: data.suggested_source_label,
          suggested_source_url: data.suggested_source_url,
          enrichment_method: data.enrichment_method || 'web_reference_lookup',
          requires_validation: data.requires_validation,
          enriched_from_web: data.enriched_from_web,
          technical_properties: data.technical_parameters?.suggested_properties || {},
          message: data.suggested_source_label
            ? `Sugerencia encontrada basada en ${data.suggested_source_label}`
            : 'Sugerencia disponible para este elemento.'
        });
      } else {
        setSuggestion(null);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al cargar el contexto de página exacta.');
    } finally {
      setLoading(false);
    }
  };

  const handleEnrich = async () => {
    if (!extractionId || !currentItem) return;
    setEnriching(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const eff = currentItem.effective_fields || {
        title: formTitle || currentItem.title,
        description: formDescription || currentItem.description || currentItem.content_text,
        function: formFunction,
      };
      const res: CandidateEnrichmentResponse = await apiService.enrichExtractedItem(
        extractionId,
        currentItem.id,
        {
          presentation_language: 'es',
          source_fields: currentItem.source_fields,
          translated_fields: currentItem.translated_fields,
          effective_fields: eff,
          candidate_type: currentItem.candidate_type || currentItem.item_type,
          title: formTitle || eff?.title || currentItem.title,
          caption_or_context: currentItem.caption_or_context,
          ocr_text: currentItem.ocr_text,
          discipline: contextData?.discipline || currentItem.discipline || 'general',
          page_number: currentItem.page_number || 1,
          document_title: contextData?.source_title,
          force_web_search: true,
        }
      );

      setSuggestion(res);
      setFormEnrichmentStatus(res.enrichment_status);
      setFormCompleteness(res.completeness_status);

      if (res.enrichment_status === 'suggestion_found') {
        setSuccessMessage(`Sugerencia encontrada con ${Math.round(res.match_confidence * 100)}% de confianza.`);
      } else {
        setSuccessMessage('No se encontró suficiente evidencia concluyente. Se recomienda completar los datos manualmente.');
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al ejecutar búsqueda asistida de referencia.');
    } finally {
      setEnriching(false);
    }
  };

  const handleApplySuggestion = () => {
    if (!suggestion) return;
    if (suggestion.suggested_title) setFormTitle(suggestion.suggested_title);
    if (suggestion.suggested_description) setFormDescription(suggestion.suggested_description);
    if (suggestion.suggested_function) setFormFunction(suggestion.suggested_function);
    if (suggestion.technical_properties && Object.keys(suggestion.technical_properties).length > 0) {
      try {
        const currentProps = formProperties ? JSON.parse(formProperties) : {};
        const merged = { ...currentProps, ...suggestion.technical_properties };
        setFormProperties(JSON.stringify(merged, null, 2));
      } catch {
        // En caso de que formProperties no sea JSON válido
      }
    }
    setFormCompleteness('web_suggested');
    setSuccessMessage('Sugerencia de catálogo aplicada a los campos del formulario.');
  };

  const handleSave = async () => {
    if (!extractionId || !currentItem) return;
    setSaving(true);
    setError(null);
    setSuccessMessage(null);

    try {
      let parsedParams = {};
      if (formProperties.trim()) {
        try {
          parsedParams = JSON.parse(formProperties);
        } catch {
          parsedParams = { raw_notes: formProperties };
        }
      }
      if (formFunction.trim()) {
        parsedParams = { ...parsedParams, function_or_role: formFunction.trim() };
      }

      // Determinar completitud
      let computedCompleteness = 'missing_data';
      const hasTitle = formTitle.trim().length > 0 && !formTitle.toLowerCase().startsWith('símbolo');
      const hasDesc = formDescription.trim().length >= 15;
      const hasFunc = formFunction.trim().length >= 10;

      if (hasTitle && hasDesc && hasFunc) {
        computedCompleteness = 'complete';
      } else if (hasTitle && (hasDesc || hasFunc)) {
        computedCompleteness = 'partial';
      } else if (formEnrichmentStatus === 'suggestion_found') {
        computedCompleteness = 'web_suggested';
      }

      const updatePayload = {
        title: formTitle.trim() || currentItem.title,
        code_or_number: formCode.trim() || undefined,
        description: formDescription.trim() || undefined,
        technical_parameters: parsedParams,
        completeness_status: computedCompleteness,
        enrichment_status: formEnrichmentStatus === 'suggestion_found' ? 'manual_completed' : formEnrichmentStatus,
        requires_validation: false,
        source_reference: suggestion?.suggested_source_label || currentItem.source_reference,
      };

      const updated = await apiService.updateExtractedItem(extractionId, currentItem.id, updatePayload);
      setCurrentItem(updated);
      setFormCompleteness(computedCompleteness);
      setSuccessMessage('Elemento actualizado y guardado correctamente.');
      if (onItemUpdated) {
        onItemUpdated(updated);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al guardar los cambios en el elemento.');
    } finally {
      setSaving(false);
    }
  };

  // OCR on subregion
  const handleStartOcrSelection = (field: OcrTargetField) => {
    setOcrTargetField(field);
    setSelectionMode('ocr');
    setSelectionBox(null);
  };

  // Separar elemento (Split)
  const handleConfirmSplit = async () => {
    if (!selectionBox || !extractionId || !currentItem) return;
    const x0 = Math.min(selectionBox.startX, selectionBox.currentX);
    const y0 = Math.min(selectionBox.startY, selectionBox.currentY);
    const x1 = Math.max(selectionBox.startX, selectionBox.currentX);
    const y1 = Math.max(selectionBox.startY, selectionBox.currentY);

    if (Math.abs(x1 - x0) < 0.015 || Math.abs(y1 - y0) < 0.015) {
      setError('El área seleccionada es demasiado pequeña para separar. Por favor arrastra un recuadro más amplio.');
      return;
    }

    setIsSplitting(true);
    setError(null);
    try {
      const newItem = await apiService.splitExtractedItem(extractionId, currentItem.id, {
        bbox: [x0, y0, x1, y1],
        discipline: contextData?.discipline || currentItem.discipline || 'general',
      });

      setSelectionMode('none');
      setSelectionBox(null);
      setSuccessMessage(`¡Nueva regla derivada «${newItem.title}» creada con éxito! La regla original se preservó intacta.`);
      
      if (onItemUpdated) {
        onItemUpdated(newItem);
      }

      // Cambiar la vista al nuevo elemento derivado
      setCurrentItem(newItem);
      await loadContext(extractionId, newItem.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al separar elemento visualmente.');
    } finally {
      setIsSplitting(false);
    }
  };

  // Recortar (Crop)
  const handleConfirmCrop = async () => {
    if (!selectionBox || !extractionId || !currentItem) return;
    const x0 = Math.min(selectionBox.startX, selectionBox.currentX);
    const y0 = Math.min(selectionBox.startY, selectionBox.currentY);
    const x1 = Math.max(selectionBox.startX, selectionBox.currentX);
    const y1 = Math.max(selectionBox.startY, selectionBox.currentY);

    if (Math.abs(x1 - x0) < 0.015 || Math.abs(y1 - y0) < 0.015) {
      setError('El área seleccionada es demasiado pequeña para recortar. Por favor arrastra un recuadro más amplio.');
      return;
    }

    setIsCropping(true);
    setError(null);
    try {
      const updated = await apiService.cropExtractedItem(extractionId, currentItem.id, {
        bbox: [x0, y0, x1, y1],
      });

      setSelectionMode('none');
      setSelectionBox(null);
      setSuccessMessage('Imagen de la regla actual recortada y actualizada con éxito.');
      
      if (onItemUpdated) {
        onItemUpdated(updated);
      }

      setCurrentItem(updated);
      await loadContext(extractionId, updated.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al recortar la imagen de la regla actual.');
    } finally {
      setIsCropping(false);
    }
  };

  // Mouse Handlers with Coordinate Mapping
  const handleMouseDownCanvas = (e: React.MouseEvent<HTMLDivElement>) => {
    if (selectionMode !== 'none' && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const clickX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const clickY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      setSelectionBox({
        startX: clickX,
        startY: clickY,
        currentX: clickX,
        currentY: clickY,
      });
      setIsDrawingBox(true);
      return;
    }

    // Default Pan
    setIsPanning(true);
    setStartPan({ x: e.clientX - pan.x, y: e.clientY - pan.y });
  };

  const handleMouseMoveCanvas = (e: React.MouseEvent<HTMLDivElement>) => {
    if (selectionMode !== 'none' && isDrawingBox && selectionBox && imageRef.current) {
      const rect = imageRef.current.getBoundingClientRect();
      const currentX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
      const currentY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));
      setSelectionBox((prev) => (prev ? {
        ...prev,
        currentX,
        currentY,
      } : null));
      return;
    }

    if (isPanning) {
      setPan({
        x: e.clientX - startPan.x,
        y: e.clientY - startPan.y,
      });
    }
  };

  const handleMouseUpCanvas = async () => {
    if (isDrawingBox) {
      setIsDrawingBox(false);

      // Si es modo OCR, ejecutar OCR automáticamente
      if (selectionMode === 'ocr' && selectionBox && extractionId && currentItem && ocrTargetField) {
        const x0 = Math.min(selectionBox.startX, selectionBox.currentX);
        const y0 = Math.min(selectionBox.startY, selectionBox.currentY);
        const x1 = Math.max(selectionBox.startX, selectionBox.currentX);
        const y1 = Math.max(selectionBox.startY, selectionBox.currentY);

        setOcrLoading(true);
        try {
          const ocrRes = await apiService.extractRegionOcr(extractionId, currentItem.id, {
            page_number: currentItem.page_number || 1,
            bbox: [x0, y0, x1, y1],
            target_field: ocrTargetField,
          });

          const extracted = (ocrRes.extracted_text || '').trim();
          if (extracted) {
            if (ocrTargetField === 'title') {
              setFormTitle(extracted);
            } else if (ocrTargetField === 'description') {
              setFormDescription((prev) => (prev ? `${prev} ${extracted}` : extracted));
            } else if (ocrTargetField === 'function') {
              setFormFunction(extracted);
            } else if (ocrTargetField === 'properties') {
              setFormProperties((prev) => (prev ? `${prev}\nOCR: ${extracted}` : `OCR: ${extracted}`));
            }
            setSuccessMessage(`Texto OCR capturado para campo «${ocrTargetField}»: «${extracted.slice(0, 40)}${extracted.length > 40 ? '...' : ''}»`);
          } else {
            setError('No se detectó texto legible en la región seleccionada.');
          }
        } catch (err: any) {
          setError('Error ejecutando OCR en la región seleccionada.');
        } finally {
          setOcrLoading(false);
          setOcrTargetField(null);
          setSelectionMode('none');
          setSelectionBox(null);
        }
        return;
      }
      return;
    }

    setIsPanning(false);
  };

  const getCompletenessBadge = (status: string) => {
    switch (status) {
      case 'complete':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 shadow-sm">
            <CheckCircle2 className="w-3.5 h-3.5" /> Completo
          </span>
        );
      case 'partial':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-amber-950/80 text-amber-300 border border-amber-700/60 shadow-sm">
            <AlertTriangle className="w-3.5 h-3.5" /> Parcial
          </span>
        );
      case 'web_suggested':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-sky-950/80 text-sky-300 border border-sky-700/60 shadow-sm">
            <Sparkles className="w-3.5 h-3.5" /> Sugerencia Web ({Math.round((contextData?.match_confidence || suggestion?.match_confidence || 0) * 100)}%)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold rounded-full bg-rose-950/80 text-rose-300 border border-rose-700/60 shadow-sm">
            <HelpCircle className="w-3.5 h-3.5" /> Datos faltantes
          </span>
        );
    }
  };

  if (!isOpen || !currentItem) return null;

  // Bbox normalized calculations
  const bbox = contextData?.bbox_normalized || currentItem.bbox_normalized || [];
  const hasBbox = Array.isArray(bbox) && bbox.length === 4;
  const [bx0, by0, bx1, by1] = hasBbox ? bbox : [0.1, 0.1, 0.4, 0.4];

  // Selection box values
  const hasActiveSelectionBox = selectionBox !== null && (Math.abs(selectionBox.currentX - selectionBox.startX) > 0.005 || Math.abs(selectionBox.currentY - selectionBox.startY) > 0.005);
  const selX0 = selectionBox ? Math.min(selectionBox.startX, selectionBox.currentX) : 0;
  const selY0 = selectionBox ? Math.min(selectionBox.startY, selectionBox.currentY) : 0;
  const selW = selectionBox ? Math.abs(selectionBox.currentX - selectionBox.startX) : 0;
  const selH = selectionBox ? Math.abs(selectionBox.currentY - selectionBox.startY) : 0;

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 backdrop-blur-md p-2 sm:p-4 animate-in fade-in duration-200">
      <div 
        className="relative flex flex-col w-full max-w-[96vw] h-[95vh] bg-slate-900 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Bar */}
        <div className="flex items-center justify-between px-5 py-3 bg-slate-950 border-b border-slate-800">
          <div className="flex items-center gap-3 min-w-0 flex-wrap">
            {contextData?.source_origin === 'web' ? (
              <div className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-indigo-950/80 text-indigo-300 border border-indigo-700/70 shadow-sm">
                <Globe className="w-4 h-4 text-indigo-400" />
                <span>Contexto Web (HTML / Snapshot)</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-lg bg-cyan-950/80 text-cyan-300 border border-cyan-700/70">
                <Compass className="w-4 h-4 text-cyan-400" />
                <span>Visor de Contexto: Página {contextData?.page_number || currentItem.page_number}</span>
              </div>
            )}

            {/* Badge de Elemento Derivado si aplica */}
            {(currentItem.is_derived || currentItem.parent_item_id) && (
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs font-bold rounded-full bg-purple-950 text-purple-300 border border-purple-600 shadow-sm">
                <Scissors className="w-3.5 h-3.5 text-purple-400" />
                <span>Derivado de Imagen (Madre #{currentItem.parent_item_id?.slice(0, 8) || 'ORIG'})</span>
              </span>
            )}

            {getCompletenessBadge(formCompleteness)}

            {((currentItem?.translation_status === 'completed' || contextData?.translation_status === 'completed') && (contextData?.effective_fields?.title || currentItem?.effective_fields?.title)) && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded-full bg-sky-950 text-sky-300 border border-sky-600 shadow-sm">
                <Sparkles className="w-3.5 h-3.5 text-sky-400" /> IA Traducido (ES)
              </span>
            )}

            {contextData?.duplicate_status === 'duplicate_web_finding' && (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-bold rounded-full bg-amber-950 text-amber-300 border border-amber-600 shadow-sm">
                <AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> Duplicado Web ({contextData.duplicate_reason || 'Similitud alta'})
              </span>
            )}
            <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 truncate">
              <span className="text-slate-600">•</span>
              <span className="truncate font-medium text-slate-300">{contextData?.source_title || 'Documento técnico'}</span>
              <span className="text-slate-600">•</span>
              <span className="capitalize text-slate-400">{contextData?.discipline || 'General'}</span>
            </div>
            {contextData?.web_source_url && (
              <a
                href={contextData.web_source_url}
                target="_blank"
                rel="noreferrer"
                className="hidden lg:inline-flex items-center gap-1 text-[11px] text-cyan-400 hover:text-cyan-300 underline font-medium"
                title="Abrir sitio web original"
              >
                <ExternalLink className="w-3 h-3" />
                Abrir sitio web
              </a>
            )}
          </div>

          <div className="flex items-center gap-2 flex-wrap">
            {/* Action Buttons: Separar elemento & Recortar */}
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg p-1 shadow-sm">
              <button
                type="button"
                onClick={() => {
                  if (selectionMode === 'split') {
                    setSelectionMode('none');
                    setSelectionBox(null);
                  } else {
                    setSelectionMode('split');
                    setOcrTargetField(null);
                    setSelectionBox(null);
                  }
                }}
                className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                  selectionMode === 'split'
                    ? 'bg-purple-600 text-white ring-2 ring-purple-400 shadow-lg shadow-purple-900/50'
                    : 'bg-purple-950/70 hover:bg-purple-900/90 text-purple-200 border border-purple-700/60'
                }`}
                title="Dibuja un área sobre la imagen para crear una NUEVA regla independiente (la regla actual se conserva)"
              >
                <Scissors className="w-3.5 h-3.5 text-purple-300" />
                <span>Separar elemento</span>
              </button>

              <button
                type="button"
                onClick={() => {
                  if (selectionMode === 'crop') {
                    setSelectionMode('none');
                    setSelectionBox(null);
                  } else {
                    setSelectionMode('crop');
                    setOcrTargetField(null);
                    setSelectionBox(null);
                  }
                }}
                className={`inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold rounded-md transition-all ${
                  selectionMode === 'crop'
                    ? 'bg-emerald-600 text-white ring-2 ring-emerald-400 shadow-lg shadow-emerald-900/50'
                    : 'bg-emerald-950/70 hover:bg-emerald-900/90 text-emerald-200 border border-emerald-700/60'
                }`}
                title="Recorta la imagen de la regla actual para conservar solo el área seleccionada (no crea nueva regla)"
              >
                <Crop className="w-3.5 h-3.5 text-emerald-300" />
                <span>Recortar</span>
              </button>
            </div>

            {/* Zoom Controls */}
            <div className="flex items-center gap-1 bg-slate-800/80 border border-slate-700 rounded-lg p-1">
              <button
                type="button"
                onClick={() => setZoom((z) => Math.max(0.5, z - 0.25))}
                disabled={zoom <= 0.5}
                title="Reducir zoom (-)"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded disabled:opacity-40"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono px-1.5 text-slate-300 select-none">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={() => setZoom((z) => Math.min(4, z + 0.25))}
                disabled={zoom >= 4}
                title="Aumentar zoom (+)"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded disabled:opacity-40"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={() => {
                  setZoom(1);
                  setPan({ x: 0, y: 0 });
                }}
                title="Restablecer encuadre"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors ml-1"
              title="Cerrar (Esc)"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Status / Active Selection Mode Bar */}
        {(error || successMessage || selectionMode !== 'none' || ocrLoading || isSplitting || isCropping) && (
          <div className="px-5 py-2.5 text-xs flex items-center justify-between border-b transition-all">
            {ocrLoading && (
              <div className="flex items-center gap-2 text-cyan-300 bg-cyan-950/60 px-3 py-1.5 rounded-md border border-cyan-800 w-full">
                <Loader2 className="w-4 h-4 animate-spin text-cyan-400" />
                <span>Extrayendo texto OCR de la región seleccionada...</span>
              </div>
            )}
            {isSplitting && (
              <div className="flex items-center gap-2 text-purple-300 bg-purple-950/70 px-3 py-1.5 rounded-md border border-purple-800 w-full">
                <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                <span>Separando elemento visualmente, ejecutando OCR y creando nueva regla derivada...</span>
              </div>
            )}
            {isCropping && (
              <div className="flex items-center gap-2 text-emerald-300 bg-emerald-950/70 px-3 py-1.5 rounded-md border border-emerald-800 w-full">
                <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                <span>Recortando imagen de la regla actual y actualizando contexto...</span>
              </div>
            )}

            {/* Banner for Split Mode */}
            {selectionMode === 'split' && !isSplitting && (
              <div className="flex items-center justify-between gap-3 text-purple-200 bg-purple-950/90 px-4 py-2 rounded-lg border border-purple-700/80 w-full shadow-lg">
                <div className="flex items-center gap-2">
                  <Scissors className="w-4 h-4 text-purple-400 animate-pulse" />
                  <span>
                    <strong>Modo Activo: Separar Elemento</strong> • Arrastra el cursor sobre la lámina para enmarcar el área. Al confirmar, se creará una <strong>NUEVA regla</strong> y la regla actual se conservará intacta.
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleConfirmSplit}
                    disabled={!hasActiveSelectionBox}
                    className="px-3 py-1 text-xs font-bold bg-purple-500 hover:bg-purple-400 text-slate-950 rounded shadow disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 transition-all"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Confirmar separación</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectionMode('none');
                      setSelectionBox(null);
                    }}
                    className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-600 transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {/* Banner for Crop Mode */}
            {selectionMode === 'crop' && !isCropping && (
              <div className="flex items-center justify-between gap-3 text-emerald-200 bg-emerald-950/90 px-4 py-2 rounded-lg border border-emerald-700/80 w-full shadow-lg">
                <div className="flex items-center gap-2">
                  <Crop className="w-4 h-4 text-emerald-400 animate-pulse" />
                  <span>
                    <strong>Modo Activo: Recortar Regla Actual</strong> • Arrastra el cursor para definir el nuevo encuadre. Al confirmar, se <strong>reemplazará la imagen</strong> de la regla actual (sin crear nueva regla).
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button
                    type="button"
                    onClick={handleConfirmCrop}
                    disabled={!hasActiveSelectionBox}
                    className="px-3 py-1 text-xs font-bold bg-emerald-400 hover:bg-emerald-300 text-slate-950 rounded shadow disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 transition-all"
                  >
                    <Check className="w-3.5 h-3.5" />
                    <span>Confirmar recorte</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      setSelectionMode('none');
                      setSelectionBox(null);
                    }}
                    className="px-2.5 py-1 text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-600 transition-colors"
                  >
                    Cancelar
                  </button>
                </div>
              </div>
            )}

            {/* Banner for OCR Mode */}
            {selectionMode === 'ocr' && !ocrLoading && (
              <div className="flex items-center justify-between gap-2 text-amber-300 bg-amber-950/60 px-3 py-1.5 rounded-md border border-amber-800 w-full">
                <div className="flex items-center gap-2">
                  <Crosshair className="w-4 h-4 text-amber-400 animate-pulse" />
                  <span>Modo Selección OCR activo: Haz click y arrastra sobre la lámina para capturar el texto hacia «{ocrTargetField}».</span>
                </div>
                <button
                  type="button"
                  onClick={() => {
                    setSelectionMode('none');
                    setOcrTargetField(null);
                    setSelectionBox(null);
                  }}
                  className="px-2 py-0.5 text-[11px] bg-slate-800 hover:bg-slate-700 text-slate-300 rounded border border-slate-600"
                >
                  Cancelar
                </button>
              </div>
            )}

            {error && selectionMode === 'none' && !ocrLoading && !isSplitting && !isCropping && (
              <div className="flex items-center gap-2 text-rose-300 bg-rose-950/60 px-3 py-1.5 rounded-md border border-rose-800 w-full">
                <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{error}</span>
              </div>
            )}
            {successMessage && !error && selectionMode === 'none' && !ocrLoading && !isSplitting && !isCropping && (
              <div className="flex items-center gap-2 text-emerald-300 bg-emerald-950/60 px-3 py-1.5 rounded-md border border-emerald-800 w-full">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{successMessage}</span>
              </div>
            )}
          </div>
        )}

        {/* Main Content Area: Split View (Canvas on Left, Edit & Enrichment Form on Right) */}
        <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
          {/* Left Canvas: Exact Page Rendering with Highlighted Bounding Box */}
          <div 
            ref={containerRef}
            className="flex-1 relative bg-slate-950 overflow-hidden flex items-center justify-center select-none cursor-crosshair border-b lg:border-b-0 lg:border-r border-slate-800"
            onMouseDown={handleMouseDownCanvas}
            onMouseMove={handleMouseMoveCanvas}
            onMouseUp={handleMouseUpCanvas}
          >
            {loading ? (
              <div className="flex flex-col items-center justify-center gap-3 text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin text-cyan-400" />
                <p className="text-xs">Cargando lámina exacta del documento...</p>
              </div>
            ) : contextData?.page_image_url ? (
              <div 
                className="relative transition-transform duration-75 ease-out"
                style={{
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                  transformOrigin: 'center center',
                }}
              >
                <img
                  ref={imageRef}
                  src={contextData.page_image_url}
                  alt={`Página ${contextData.page_number}`}
                  className="max-w-[70vw] max-h-[78vh] object-contain shadow-2xl rounded border border-slate-800 pointer-events-none"
                  draggable={false}
                />

                {/* Highlighted Bounding Box for Detected Element */}
                {hasBbox && selectionMode === 'none' && (
                  <div
                    className="absolute border-2 border-cyan-400 bg-cyan-500/20 rounded shadow-[0_0_15px_rgba(6,182,212,0.6)] animate-pulse pointer-events-none"
                    style={{
                      left: `${Math.min(bx0, bx1) * 100}%`,
                      top: `${Math.min(by0, by1) * 100}%`,
                      width: `${Math.abs(bx1 - bx0) * 100}%`,
                      height: `${Math.abs(by1 - by0) * 100}%`,
                    }}
                  >
                    <span className="absolute -top-6 left-0 px-2 py-0.5 text-[10px] font-bold bg-cyan-500 text-slate-950 rounded shadow-md whitespace-nowrap">
                      Región Actual ({currentItem.item_type})
                    </span>
                  </div>
                )}

                {/* Drag-Selection Box for Split Mode */}
                {selectionMode === 'split' && selectionBox && (
                  <div
                    className="absolute border-2 border-dashed border-purple-400 bg-purple-500/30 rounded pointer-events-none shadow-[0_0_20px_rgba(168,85,247,0.5)]"
                    style={{
                      left: `${selX0 * 100}%`,
                      top: `${selY0 * 100}%`,
                      width: `${selW * 100}%`,
                      height: `${selH * 100}%`,
                    }}
                  >
                    <span className="absolute -top-6 left-0 px-2 py-0.5 text-[10px] font-bold bg-purple-500 text-white rounded shadow-md whitespace-nowrap flex items-center gap-1">
                      <Scissors className="w-3 h-3" />
                      <span>Nueva Regla Derivada [{Math.round(selW * 100)}% x {Math.round(selH * 100)}%]</span>
                    </span>
                  </div>
                )}

                {/* Drag-Selection Box for Crop Mode */}
                {selectionMode === 'crop' && selectionBox && (
                  <div
                    className="absolute border-2 border-dashed border-emerald-400 bg-emerald-500/30 rounded pointer-events-none shadow-[0_0_20px_rgba(52,211,153,0.5)]"
                    style={{
                      left: `${selX0 * 100}%`,
                      top: `${selY0 * 100}%`,
                      width: `${selW * 100}%`,
                      height: `${selH * 100}%`,
                    }}
                  >
                    <span className="absolute -top-6 left-0 px-2 py-0.5 text-[10px] font-bold bg-emerald-400 text-slate-950 rounded shadow-md whitespace-nowrap flex items-center gap-1">
                      <Crop className="w-3 h-3" />
                      <span>Recorte Regla Actual [{Math.round(selW * 100)}% x {Math.round(selH * 100)}%]</span>
                    </span>
                  </div>
                )}

                {/* Drag-Selection Box for Region OCR */}
                {selectionMode === 'ocr' && selectionBox && (
                  <div
                    className="absolute border-2 border-dashed border-amber-400 bg-amber-500/30 rounded pointer-events-none"
                    style={{
                      left: `${selX0 * 100}%`,
                      top: `${selY0 * 100}%`,
                      width: `${selW * 100}%`,
                      height: `${selH * 100}%`,
                    }}
                  >
                    <span className="absolute -top-5 left-0 px-1.5 py-0.5 text-[9px] font-bold bg-amber-400 text-slate-950 rounded shadow whitespace-nowrap">
                      Captura OCR hacia «{ocrTargetField}»
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center gap-3 text-slate-500 py-16">
                <Crop className="w-12 h-12 text-slate-700" />
                <p className="text-sm font-medium">Lámina no disponible directamente como PNG.</p>
                <p className="text-xs text-slate-600 max-w-sm text-center">
                  Usa el recorte individual o abre el visor general del documento.
                </p>
              </div>
            )}

            {/* Helper pill */}
            <div className="absolute bottom-3 left-3 bg-slate-900/90 backdrop-blur border border-slate-800 text-[11px] text-slate-400 px-3 py-1.5 rounded-lg pointer-events-none flex items-center gap-2 shadow-lg">
              <Compass className="w-3.5 h-3.5 text-cyan-400" />
              <span>Arrastra para encuadrar • Rueda o botones para Zoom • Botones superiores para Separar o Recortar</span>
            </div>
          </div>

          {/* Right Panel: Assisted Edit, OCR Buttons, Web Suggestions & Validation */}
          <div className="w-full lg:w-[480px] bg-slate-900/95 flex flex-col justify-between border-t lg:border-t-0 overflow-y-auto">
            <div className="p-5 space-y-4">
              {/* Assisted Web Reference Action Header */}
              <div className="p-3.5 rounded-xl bg-gradient-to-br from-slate-950 to-slate-900 border border-slate-800 shadow-md space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs font-semibold text-white">Enriquecimiento Asistido</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleEnrich}
                    disabled={enriching}
                    className="inline-flex items-center gap-1.5 px-3 py-1 text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-500 rounded-lg shadow-sm disabled:opacity-50 transition-all"
                  >
                    {enriching ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        Buscando...
                      </>
                    ) : (
                      <>
                        <Search className="w-3.5 h-3.5" />
                        Buscar referencia
                      </>
                    )}
                  </button>
                </div>

                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Consulta catálogos normativos (ISA-5.1, ASME, OGUC, SEC, ASHRAE) y referencias web para sugerir nombre, descripción y función técnica.
                </p>

                {/* Suggestion Banner */}
                {suggestion && suggestion.enrichment_status === 'suggestion_found' && (
                  <div className="p-3 rounded-lg bg-sky-950/60 border border-sky-800/80 space-y-2 mt-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-sky-300 flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                        Sugerencia Encontrada ({Math.round(suggestion.match_confidence * 100)}% Confianza)
                      </span>
                      <button
                        type="button"
                        onClick={handleApplySuggestion}
                        className="px-2.5 py-1 text-[11px] font-bold text-slate-950 bg-sky-400 hover:bg-sky-300 rounded shadow transition-all active:scale-95 flex items-center gap-1"
                      >
                        <ArrowDownToLine className="w-3 h-3" />
                        Aplicar sugerencia
                      </button>
                    </div>

                    <div className="text-xs space-y-1 text-slate-200 font-sans">
                      {suggestion.suggested_title && (
                        <div><strong className="text-sky-400 font-mono text-[10px]">TÍTULO:</strong> {suggestion.suggested_title}</div>
                      )}
                      {suggestion.suggested_description && (
                        <div><strong className="text-sky-400 font-mono text-[10px]">DESCRIPCIÓN:</strong> {suggestion.suggested_description}</div>
                      )}
                      {suggestion.suggested_function && (
                        <div><strong className="text-sky-400 font-mono text-[10px]">FUNCIÓN:</strong> {suggestion.suggested_function}</div>
                      )}
                    </div>

                    {suggestion.suggested_source_url && (
                      <a
                        href={suggestion.suggested_source_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 underline font-medium pt-1"
                      >
                        <ExternalLink className="w-3 h-3" />
                        {suggestion.suggested_source_label || 'Fuente de Referencia Web'}
                      </a>
                    )}
                  </div>
                )}

                {suggestion && suggestion.enrichment_status === 'not_enriched' && (
                  <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/60 text-xs text-rose-300 flex items-center gap-2">
                    <HelpCircle className="w-4 h-4 text-rose-400 shrink-0" />
                    <span>{suggestion.message}</span>
                  </div>
                )}
              </div>

              {/* Form Fields with Eye/OCR Capture Button per Field */}
              <div className="space-y-3.5 text-xs">
                {/* Título / Nombre */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-slate-300 flex items-center gap-1.5">
                      <span>Nombre / Título del Elemento</span>
                      <span className="text-rose-400">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => handleStartOcrSelection('title')}
                      title="Seleccionar área en la lámina para capturar el título vía OCR"
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
                        ocrTargetField === 'title'
                          ? 'bg-amber-500 text-slate-950 border-amber-400'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>OCR hacia Título</span>
                    </button>
                  </div>
                  <input
                    type="text"
                    value={formTitle}
                    onChange={(e) => setFormTitle(e.target.value)}
                    placeholder="Ej. Válvula de Control Automática FCV-101"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Código / Tag */}
                <div className="space-y-1">
                  <label className="font-semibold text-slate-300">Código / Tag / Número</label>
                  <input
                    type="text"
                    value={formCode}
                    onChange={(e) => setFormCode(e.target.value)}
                    placeholder="Ej. SYM-MEC-01, V-102, Art. 4.3.7"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Descripción Técnica */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-slate-300 flex items-center gap-1.5">
                      <span>Descripción Técnica</span>
                      <span className="text-rose-400">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => handleStartOcrSelection('description')}
                      title="Seleccionar área en la lámina para capturar descripción vía OCR"
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
                        ocrTargetField === 'description'
                          ? 'bg-amber-500 text-slate-950 border-amber-400'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>OCR hacia Descripción</span>
                    </button>
                  </div>
                  <textarea
                    rows={3}
                    value={formDescription}
                    onChange={(e) => setFormDescription(e.target.value)}
                    placeholder="Descripción detallada de la convención gráfica, equipo o regla técnica..."
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 leading-relaxed"
                  />
                </div>

                {/* Función / Rol Técnico */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-slate-300 flex items-center gap-1.5">
                      <span>Función / Rol Técnico</span>
                    </label>
                    <button
                      type="button"
                      onClick={() => handleStartOcrSelection('function')}
                      title="Seleccionar área en la lámina para capturar función técnica vía OCR"
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
                        ocrTargetField === 'function'
                          ? 'bg-amber-500 text-slate-950 border-amber-400'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>OCR hacia Función</span>
                    </button>
                  </div>
                  <input
                    type="text"
                    value={formFunction}
                    onChange={(e) => setFormFunction(e.target.value)}
                    placeholder="Ej. Regulación continua de caudal en línea de recirculación"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>

                {/* Propiedades Técnicas (JSON / Notas) */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <label className="font-semibold text-slate-300">Propiedades Técnicas / Parámetros (JSON)</label>
                    <button
                      type="button"
                      onClick={() => handleStartOcrSelection('properties')}
                      title="Seleccionar área para volcar notas técnicas vía OCR"
                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium border transition-colors ${
                        ocrTargetField === 'properties'
                          ? 'bg-amber-500 text-slate-950 border-amber-400'
                          : 'bg-slate-800 text-slate-300 border-slate-700 hover:text-white hover:bg-slate-700'
                      }`}
                    >
                      <Eye className="w-3 h-3" />
                      <span>OCR hacia Notas</span>
                    </button>
                  </div>
                  <textarea
                    rows={2}
                    value={formProperties}
                    onChange={(e) => setFormProperties(e.target.value)}
                    placeholder="{\n  &quot;standard&quot;: &quot;ISA-5.1&quot;,\n  &quot;category&quot;: &quot;Control Valves&quot;\n}"
                    className="w-full px-3 py-2 bg-slate-950 border border-slate-700 rounded-lg text-slate-200 font-mono text-[11px] placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                  />
                </div>
              </div>
            </div>

            {/* Bottom Actions Bar */}
            <div className="p-4 bg-slate-950 border-t border-slate-800 flex items-center justify-between gap-3">
              <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                <span>Estado de completitud:</span>
                {getCompletenessBadge(formCompleteness)}
              </div>

              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3.5 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
                >
                  Cerrar
                </button>
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-slate-950 bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 rounded-lg shadow-md disabled:opacity-50 transition-all active:scale-95"
                >
                  {saving ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      Guardando...
                    </>
                  ) : (
                    <>
                      <Save className="w-3.5 h-3.5" />
                      Guardar en elemento
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
