import React, { useState } from 'react';
import {
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Layers,
  Trash2,
  Edit3,
  BookmarkPlus,
  Sparkles,
  BookOpen,
  ArrowRight,
  Database
} from 'lucide-react';
import { apiService } from '../services/api';
import { ManualAnnotation } from '../types';

interface AnnotationConfirmModalProps {
  isOpen: boolean;
  pendingItems: any[];
  onClose: () => void;
  onRemoveItem: (index: number) => void;
  onEditItem: (index: number) => void;
  onCompleteSave: () => void;
}

export const AnnotationConfirmModal: React.FC<AnnotationConfirmModalProps> = ({
  isOpen,
  pendingItems,
  onClose,
  onRemoveItem,
  onEditItem,
  onCompleteSave,
}) => {
  const [saving, setSaving] = useState<boolean>(false);
  const [saveToKnowledge, setSaveToKnowledge] = useState<boolean>(true);
  const [promoteToAl, setPromoteToAl] = useState<boolean>(false);
  const [alEngine, setAlEngine] = useState<string>('symbol_detector');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleConfirmAll = async () => {
    if (pendingItems.length === 0) return;
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      for (const item of pendingItems) {
        // 1. Guardar Anotación Manual
        const createdAnn = await apiService.createManualAnnotation(item);

        // 2. Nivel 1: Guardar en Base de Conocimiento Guía & Plantillas
        if (saveToKnowledge) {
          await apiService.addToKnowledgeLibrary({
            source_annotation_id: createdAnn.id,
            entry_type: `${createdAnn.element_type}_template`,
            name: createdAnn.name,
            description: createdAnn.description,
            discipline: createdAnn.discipline,
            crop_image_path: createdAnn.crop_image_path,
            canonical_text: createdAnn.ocr_text,
            tags: createdAnn.tags || [],
          });
        }

        // 3. Nivel 2: Promover a Active Learning si el usuario lo marcó
        if (promoteToAl) {
          await apiService.promoteToActiveLearning({
            manual_annotation_id: createdAnn.id,
            target_engine: alEngine,
            dataset_split: 'few_shot_pool',
            label: createdAnn.name.toLowerCase().replace(/\s+/g, '_'),
            ground_truth_text: createdAnn.ocr_text,
            ground_truth_bbox: createdAnn.bbox_normalized,
            notes: `Promovido desde visor interactivo por auditor QA`,
          });
        }
      }

      setSuccess(`Se guardaron exitosamente ${pendingItems.length} elemento(s).`);
      setTimeout(() => {
        onCompleteSave();
        onClose();
      }, 1200);
    } catch (err: any) {
      console.error('Error guardando lote de anotaciones:', err);
      setError(err.response?.data?.detail || 'Error al procesar el guardado del lote.');
    } finally {
      setSaving(false);
    }
  };

  const getBadgeColor = (type: string) => {
    switch (type) {
      case 'symbol': return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40';
      case 'table': return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40';
      case 'layout_region': return 'bg-purple-500/20 text-purple-300 border-purple-500/40';
      case 'text_note': return 'bg-amber-500/20 text-amber-300 border-amber-500/40';
      case 'title_block': return 'bg-blue-500/20 text-blue-300 border-blue-500/40';
      default: return 'bg-slate-700 text-slate-300 border-slate-600';
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-3xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100">
                Confirmación de Lote de Anotaciones ({pendingItems.length})
              </h2>
              <p className="text-xs text-slate-400">
                Revisa y aprueba los elementos capturados para su incorporación al conocimiento
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cuerpo */}
        <div className="p-6 overflow-y-auto space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {success && (
            <div className="p-3 rounded-xl bg-emerald-950/50 border border-emerald-800 text-xs text-emerald-300 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{success}</span>
            </div>
          )}

          {pendingItems.length === 0 ? (
            <div className="py-12 text-center text-slate-500 text-xs">
              No hay elementos pendientes en la lista de confirmación.
            </div>
          ) : (
            <div className="space-y-3">
              {pendingItems.map((item, idx) => (
                <div
                  key={idx}
                  className="p-3.5 rounded-xl bg-slate-950/80 border border-slate-800 flex items-start justify-between gap-4 hover:border-slate-700 transition-all"
                >
                  <div className="flex items-start space-x-3.5 flex-1 min-w-0">
                    {/* Thumbnail */}
                    {item.crop_image_base64 && (
                      <div className="w-16 h-16 rounded-lg bg-slate-900 border border-slate-800 flex items-center justify-center overflow-hidden shrink-0">
                        <img
                          src={item.crop_image_base64}
                          alt={item.name}
                          className="max-h-full max-w-full object-contain"
                        />
                      </div>
                    )}

                    <div className="space-y-1 flex-1 min-w-0">
                      <div className="flex items-center space-x-2">
                        <span className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded border ${getBadgeColor(item.element_type)}`}>
                          {item.element_type}
                        </span>
                        <span className="text-xs font-semibold text-slate-100 truncate">
                          {item.name}
                        </span>
                        <span className="text-[10px] text-slate-400 bg-slate-900 px-1.5 py-0.5 rounded border border-slate-800 font-mono">
                          {item.discipline}
                        </span>
                      </div>

                      {item.ocr_text && (
                        <p className="text-xs text-slate-300 font-mono line-clamp-2 bg-slate-900/60 p-1.5 rounded border border-slate-800/80">
                          {item.ocr_text}
                        </p>
                      )}

                      {item.description && (
                        <p className="text-[11px] text-slate-400 line-clamp-1 italic">
                          {item.description}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Acciones individuales */}
                  <div className="flex items-center space-x-1 shrink-0">
                    <button
                      type="button"
                      onClick={() => onEditItem(idx)}
                      title="Editar anotación"
                      className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
                    >
                      <Edit3 className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onRemoveItem(idx)}
                      title="Eliminar de la lista"
                      className="p-1.5 text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 rounded-lg transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Opciones de Destino de Conocimiento (Flujo de 2 Niveles) */}
          <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
            <h3 className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
              <Database className="w-4 h-4 text-blue-400" />
              <span>Destino y Flujo de Conocimiento</span>
            </h3>

            <div className="space-y-2 text-xs">
              <label className="flex items-start space-x-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={saveToKnowledge}
                  onChange={(e) => setSaveToKnowledge(e.target.checked)}
                  className="mt-0.5 rounded bg-slate-900 border-slate-700 text-blue-500 focus:ring-0"
                />
                <div>
                  <span className="font-semibold text-slate-200">
                    Nivel 1: Guardar en Base de Conocimiento Guía & Plantillas Curadas
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Quedará disponible en la biblioteca de referencia operativa (catálogo de símbolos, formatos, notas y esquemas de tablas).
                  </p>
                </div>
              </label>

              <label className="flex items-start space-x-2.5 cursor-pointer">
                <input
                  type="checkbox"
                  checked={promoteToAl}
                  onChange={(e) => setPromoteToAl(e.target.checked)}
                  className="mt-0.5 rounded bg-slate-900 border-slate-700 text-teal-500 focus:ring-0"
                />
                <div>
                  <span className="font-semibold text-slate-200">
                    Nivel 2: Promover hacia Pool de Active Learning & MLOps
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Etiquetado y calibración controlada para alimentar futuros modelos y prompts de IA.
                  </p>
                </div>
              </label>

              {promoteToAl && (
                <div className="pt-2 pl-6 flex items-center space-x-2">
                  <span className="text-[11px] text-slate-400">Motor IA Objetivo:</span>
                  <select
                    value={alEngine}
                    onChange={(e) => setAlEngine(e.target.value)}
                    className="px-2.5 py-1 text-xs rounded bg-slate-900 border border-slate-700 text-slate-200"
                  >
                    <option value="symbol_detector">Detector de Símbolos (YOLO/SAHI)</option>
                    <option value="table_extractor">Extractor de Tablas Estructuradas</option>
                    <option value="layout_parser">Segmentador de Layout & Regiones</option>
                    <option value="ocr">Motor de OCR Especializado</option>
                    <option value="qa_rules">Reglas Lógicas QA/QC</option>
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3.5 border-t border-slate-800 bg-slate-900/60 flex items-center justify-between">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 rounded-xl"
          >
            Cancelar
          </button>

          <button
            type="button"
            onClick={handleConfirmAll}
            disabled={saving || pendingItems.length === 0}
            className="px-5 py-2 text-xs font-semibold text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-all shadow-lg shadow-blue-950/50 flex items-center space-x-2 disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <CheckCircle2 className="w-3.5 h-3.5" />}
            <span>Aprobar y Guardar ({pendingItems.length})</span>
          </button>
        </div>
      </div>
    </div>
  );
};
