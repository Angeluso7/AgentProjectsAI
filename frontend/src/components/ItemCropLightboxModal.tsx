import React, { useState, useEffect } from 'react';
import {
  X, ZoomIn, ZoomOut, RotateCcw, Maximize2, FileText,
  MapPin, BookOpen, Layers, ExternalLink, Sparkles, CheckCircle2, AlertTriangle, HelpCircle
} from 'lucide-react';
import { ExtractedItem } from '../types';

interface ItemCropLightboxModalProps {
  isOpen: boolean;
  item: ExtractedItem | null;
  documentTitle?: string;
  onClose: () => void;
  onOpenContext?: (item: ExtractedItem) => void;
}

export const ItemCropLightboxModal: React.FC<ItemCropLightboxModalProps> = ({
  isOpen,
  item,
  documentTitle,
  onClose,
  onOpenContext,
}) => {
  const [zoom, setZoom] = useState<number>(1);
  const [rotation, setRotation] = useState<number>(0);

  useEffect(() => {
    if (isOpen) {
      setZoom(1);
      setRotation(0);
    }
  }, [isOpen, item]);

  // Keyboard navigation & close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !item) return null;

  const handleZoomIn = () => setZoom((prev) => Math.min(prev + 0.3, 4));
  const handleZoomOut = () => setZoom((prev) => Math.max(prev - 0.3, 0.5));
  const handleResetZoom = () => {
    setZoom(1);
    setRotation(0);
  };
  const handleRotate = () => setRotation((prev) => (prev + 90) % 360);

  const getCompletenessBadge = () => {
    const status = item.completeness_status || 'missing_data';
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
            <Sparkles className="w-3.5 h-3.5" /> Sugerencia Web ({Math.round((item.match_confidence || 0) * 100)}%)
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

  const getItemTypeBadge = () => {
    const type = item.item_type || 'element';
    const cand = item.candidate_type || '';
    const label = cand.replace('_candidate', '').replace(/_/g, ' ') || type;
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-medium rounded-md bg-slate-800 text-slate-200 border border-slate-700 uppercase tracking-wider">
        <Layers className="w-3.5 h-3.5 text-cyan-400" />
        {label}
      </span>
    );
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/90 backdrop-blur-md p-3 sm:p-6 animate-in fade-in duration-200">
      <div 
        className="relative flex flex-col w-full max-w-5xl h-[92vh] bg-slate-900/95 border border-slate-700/80 rounded-2xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Top Header Bar */}
        <div className="flex items-center justify-between px-5 py-3.5 bg-slate-950/90 border-b border-slate-800">
          <div className="flex items-center gap-3 min-w-0">
            {getItemTypeBadge()}
            {getCompletenessBadge()}
            <div className="flex items-center gap-1.5 text-xs text-slate-400 truncate">
              <MapPin className="w-3.5 h-3.5 text-cyan-400 shrink-0" />
              <span>Página {item.page_number}</span>
              {documentTitle && (
                <>
                  <span className="text-slate-600">•</span>
                  <span className="truncate max-w-[280px]">{documentTitle}</span>
                </>
              )}
            </div>
          </div>

          {/* Controls & Close */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-800/80 border border-slate-700 rounded-lg p-1">
              <button
                type="button"
                onClick={handleZoomOut}
                disabled={zoom <= 0.5}
                title="Reducir zoom (-)"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded disabled:opacity-40 transition-colors"
              >
                <ZoomOut className="w-4 h-4" />
              </button>
              <span className="text-xs font-mono px-1.5 text-slate-300 select-none">
                {Math.round(zoom * 100)}%
              </span>
              <button
                type="button"
                onClick={handleZoomIn}
                disabled={zoom >= 4}
                title="Aumentar zoom (+)"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded disabled:opacity-40 transition-colors"
              >
                <ZoomIn className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleRotate}
                title="Rotar 90°"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded transition-colors"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={handleResetZoom}
                title="Restablecer vista"
                className="p-1.5 text-slate-300 hover:text-white hover:bg-slate-700/60 rounded transition-colors"
              >
                <Maximize2 className="w-4 h-4" />
              </button>
            </div>

            {onOpenContext && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenContext(item);
                }}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-cyan-300 bg-cyan-950/80 hover:bg-cyan-900 border border-cyan-700/80 rounded-lg shadow-sm transition-all"
              >
                <ExternalLink className="w-3.5 h-3.5" />
                Ver en lámina completa
              </button>
            )}

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

        {/* Main Crop Display Canvas */}
        <div className="flex-1 relative overflow-auto bg-slate-950/70 flex items-center justify-center p-6 select-none">
          {item.crop_image_path ? (
            <div 
              className="transition-transform duration-150 ease-out shadow-2xl rounded-lg overflow-hidden border border-slate-800 bg-slate-900"
              style={{
                transform: `scale(${zoom}) rotate(${rotation}deg)`,
                transformOrigin: 'center center',
              }}
            >
              <img
                src={item.crop_image_path}
                alt={item.title || 'Recorte de elemento'}
                className="max-w-[75vw] max-h-[60vh] object-contain rounded-lg pointer-events-auto"
                draggable={false}
              />
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center text-slate-500 gap-3 py-12">
              <FileText className="w-16 h-16 text-slate-700 stroke-1" />
              <p className="text-sm font-medium">Este elemento no dispone de archivo de recorte PNG.</p>
              <p className="text-xs text-slate-600 max-w-sm text-center">
                Puedes abrir la vista de contexto para inspeccionar la página y capturar la región correspondiente.
              </p>
            </div>
          )}
        </div>

        {/* Bottom Details Footer Bar */}
        <div className="px-6 py-4 bg-slate-950/95 border-t border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-3 text-xs text-slate-300">
          <div className="space-y-1 max-w-2xl">
            <h4 className="font-semibold text-sm text-white flex items-center gap-2">
              <span>{item.title || 'Elemento sin título'}</span>
              {item.code_or_number && (
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-800 text-cyan-300 border border-slate-700">
                  {item.code_or_number}
                </span>
              )}
            </h4>
            {item.description ? (
              <p className="text-slate-400 line-clamp-2 leading-relaxed">{item.description}</p>
            ) : item.caption_or_context ? (
              <p className="text-slate-400 line-clamp-2 italic leading-relaxed">«{item.caption_or_context}»</p>
            ) : (
              <p className="text-rose-400/90 font-medium">Sin descripción detallada. Completa los campos en el modo de edición.</p>
            )}
          </div>

          <div className="flex items-center gap-3 shrink-0">
            {item.source_reference && (
              <div className="flex items-center gap-1.5 text-slate-400 bg-slate-900 px-3 py-1.5 rounded-lg border border-slate-800">
                <BookOpen className="w-3.5 h-3.5 text-cyan-400" />
                <span className="truncate max-w-[200px]">{item.source_reference}</span>
              </div>
            )}
            {onOpenContext && (
              <button
                type="button"
                onClick={() => {
                  onClose();
                  onOpenContext(item);
                }}
                className="px-4 py-2 text-xs font-semibold text-slate-900 bg-gradient-to-r from-cyan-400 to-blue-500 hover:from-cyan-300 hover:to-blue-400 rounded-lg shadow-lg shadow-cyan-500/20 transition-all active:scale-95"
              >
                Abrir Contexto en Plano
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
