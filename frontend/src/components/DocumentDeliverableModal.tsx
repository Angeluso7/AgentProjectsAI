import React, { useState } from 'react';
import { X, ShieldCheck, FileCheck, AlertTriangle, Layers } from 'lucide-react';
import { apiService } from '../services/api';
import { DeliverableType, EvidenceReadinessStatus, DocumentItem } from '../types';

interface DocumentDeliverableModalProps {
  document: DocumentItem;
  isOpen: boolean;
  currentDeliverableType?: DeliverableType;
  currentReadinessStatus?: EvidenceReadinessStatus;
  currentNotes?: string;
  onClose: () => void;
  onSaved: () => void;
}

const DELIVERABLE_TYPE_OPTIONS: { value: DeliverableType; label: string; discipline: string }[] = [
  { value: 'plano_general', label: 'Plano General / Arquitectura (Plantas, Cortes, Elevaciones)', discipline: 'Arquitectura' },
  { value: 'plano_detalles', label: 'Plano de Detalles Constructivos y Cuadros de Vanos', discipline: 'Arquitectura' },
  { value: 'plano_estructural', label: 'Plano Estructural (Enfierraduras, Fundaciones, Pilares)', discipline: 'Estructuras' },
  { value: 'memoria_calculo', label: 'Memoria de Cálculo Estructural / Criterios Sísmicos', discipline: 'Estructuras' },
  { value: 'especificaciones_tecnicas', label: 'Especificaciones Técnicas (EETT)', discipline: 'General' },
  { value: 'mecanica_suelos', label: 'Informe / Estudio de Mecánica de Suelos', discipline: 'Estructuras' },
  { value: 'cuadro_cargas', label: 'Cuadro de Cargas y Diagramas Eléctricos', discipline: 'Eléctrica' },
  { value: 'plan_seguridad', label: 'Plan de Evacuación y Vías de Escape', discipline: 'Seguridad' },
  { value: 'otro_entregable', label: 'Otro Entregable / Documento Complementario', discipline: 'General' }
];

const READINESS_OPTIONS: { value: EvidenceReadinessStatus; label: string; desc: string; color: string }[] = [
  {
    value: 'uploaded',
    label: '1. Cargado (Uploaded)',
    desc: 'Documento subido recientemente, sin validación técnica.',
    color: 'bg-slate-700 text-slate-300 border-slate-600'
  },
  {
    value: 'classified',
    label: '2. Clasificado (Classified)',
    desc: 'Tipo de entregable asignado pero aún no revisado en detalle.',
    color: 'bg-blue-900/40 text-blue-300 border-blue-600'
  },
  {
    value: 'validated',
    label: '3. Validado (Validated)',
    desc: 'Contenido técnico preliminarmente verificado por el equipo.',
    color: 'bg-indigo-900/40 text-indigo-300 border-indigo-600'
  },
  {
    value: 'eligible_as_evidence',
    label: '4. Apto como Evidencia (Eligible as Evidence)',
    desc: 'Autorizado formalmente para alimentar y desbloquear las reglas QA/QC de la etapa.',
    color: 'bg-emerald-900/50 text-emerald-300 border-emerald-500'
  },
  {
    value: 'rejected',
    label: '5. Rechazado (Rejected)',
    desc: 'Documento ilegible, desactualizado o no válido para la auditoría.',
    color: 'bg-rose-900/40 text-rose-300 border-rose-600'
  }
];

export const DocumentDeliverableModal: React.FC<DocumentDeliverableModalProps> = ({
  document,
  isOpen,
  currentDeliverableType = 'plano_general',
  currentReadinessStatus = 'classified',
  currentNotes = '',
  onClose,
  onSaved
}) => {
  const [deliverableType, setDeliverableType] = useState<DeliverableType>(currentDeliverableType);
  const [readinessStatus, setReadinessStatus] = useState<EvidenceReadinessStatus>(currentReadinessStatus);
  const [notes, setNotes] = useState<string>(currentNotes);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiService.classifyDocumentDeliverable(document.id, {
        deliverable_type: deliverableType,
        readiness_status: readinessStatus,
        validation_notes: notes
      });
      onSaved();
      onClose();
    } catch (err: any) {
      console.error(err);
      setError(err.response?.data?.detail || 'Error al actualizar clasificación del entregable.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="bg-slate-900 border border-slate-700 rounded-xl max-w-xl w-full p-6 shadow-2xl animate-in fade-in zoom-in-95 duration-150">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-4">
          <div className="flex items-center gap-2 text-indigo-400">
            <Layers className="w-5 h-5" />
            <h2 className="text-lg font-semibold text-white">Clasificación de Entregable y Aptitud de Evidencia</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="bg-slate-800/60 rounded-lg p-3 border border-slate-700/50 mb-5 text-sm">
          <div className="font-medium text-slate-200 truncate">{document.filename}</div>
          <div className="text-xs text-slate-400 mt-1">ID: {document.id} | Páginas: {(document as any).total_sheets || document.page_count || document.sheets?.length || 1}</div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-rose-900/30 border border-rose-700/50 rounded-lg flex items-center gap-2 text-rose-300 text-sm">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Tipo de Entregable */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Tipo de Entregable Técnico *
            </label>
            <select
              value={deliverableType}
              onChange={(e) => setDeliverableType(e.target.value as DeliverableType)}
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              {DELIVERABLE_TYPE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  [{opt.discipline}] {opt.label}
                </option>
              ))}
            </select>
            <p className="text-xs text-slate-500 mt-1">
              Permite contrastar este documento contra los requisitos obligatorios de la etapa activa.
            </p>
          </div>

          {/* Estado de Aptitud de Evidencia */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Estado de Aptitud de Evidencia *
            </label>
            <div className="space-y-2">
              {READINESS_OPTIONS.map((opt) => {
                const isSelected = readinessStatus === opt.value;
                return (
                  <label
                    key={opt.value}
                    onClick={() => setReadinessStatus(opt.value)}
                    className={`block p-2.5 rounded-lg border cursor-pointer transition text-xs ${
                      isSelected
                        ? `${opt.color} ring-1 ring-indigo-400 shadow-sm font-medium`
                        : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">{opt.label}</span>
                      {isSelected && <FileCheck className="w-4 h-4 text-emerald-400" />}
                    </div>
                    <p className="text-[11px] text-slate-400 mt-0.5">{opt.desc}</p>
                  </label>
                );
              })}
            </div>
          </div>

          {/* Notas / Observaciones */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Notas de Validación o Justificación Técnica
            </label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              rows={2}
              placeholder="Ej: Documento revisado y firmado por calculista estructural. Contiene láminas completas de fundaciones."
              className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-sm transition"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-medium rounded-lg text-sm flex items-center gap-2 shadow-lg shadow-indigo-600/30 transition"
            >
              {loading ? (
                <span>Guardando...</span>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Guardar Clasificación</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
