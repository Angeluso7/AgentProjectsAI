import React, { useState, useEffect } from 'react';
import { X, ShieldCheck, FileCheck, AlertTriangle, Layers, Loader2, Compass } from 'lucide-react';
import { apiService } from '../services/api';
import { DeliverableType, EvidenceReadinessStatus, DocumentItem, ReviewDisciplineItem } from '../types';

interface DocumentDeliverableModalProps {
  document: DocumentItem;
  isOpen: boolean;
  currentDeliverableType?: DeliverableType;
  currentReadinessStatus?: EvidenceReadinessStatus;
  currentNotes?: string;
  currentDisciplineCode?: string;
  onClose: () => void;
  onSaved: () => void;
}

const DELIVERABLE_TYPE_OPTIONS: { value: DeliverableType; label: string; desc: string }[] = [
  { value: 'pid_diagrama', label: 'Diagrama P&ID (Piping & Instrumentation Diagram)', desc: 'Diagramas de tuberías e instrumentación de procesos' },
  { value: 'isometrico_tuberias', label: 'Isométrico de Tuberías (Piping Isometric)', desc: 'Planos isométricos de spool y trazado de cañerías' },
  { value: 'diagrama_unilineal', label: 'Diagrama Unilineal', desc: 'Esquema eléctrico unilineal de potencia, distribución o control' },
  { value: 'hoja_de_datos', label: 'Hoja de Datos (Data Sheet)', desc: 'Hojas de datos técnicos de equipos, válvulas o instrumentos' },
  { value: 'plano_planta', label: 'Plano de Planta', desc: 'Disposición general o sectorizada en vista de planta' },
  { value: 'plano_corte', label: 'Plano de Corte / Sección', desc: 'Secciones transversales, longitudinales y perfiles' },
  { value: 'plano_elevacion', label: 'Plano de Elevación', desc: 'Elevaciones y vistas verticales de fachadas o equipos' },
  { value: 'plano_general', label: 'Plano General', desc: 'Disposición general de arquitectura, equipos o instalaciones' },
  { value: 'plano_detalles', label: 'Plano de Detalles Constructivos', desc: 'Detalles constructivos, ensambles y cuadros de vanos' },
  { value: 'plano_estructural', label: 'Plano Estructural', desc: 'Enfierraduras, fundaciones, vigas, pilares y perfiles' },
  { value: 'memoria_calculo', label: 'Memoria de Cálculo', desc: 'Memorias de cálculo estructural, hidráulico, mecánico o eléctrico' },
  { value: 'especificaciones_tecnicas', label: 'Especificaciones Técnicas (EETT)', desc: 'Requisitos de materiales, tolerancias y normas aplicables' },
  { value: 'mecanica_suelos', label: 'Estudio de Mecánica de Suelos', desc: 'Ensayos geotécnicos y recomendaciones de fundación' },
  { value: 'cuadro_cargas', label: 'Cuadro de Cargas / Equipos', desc: 'Planillas de cargas eléctricas y listados técnicos' },
  { value: 'plan_seguridad', label: 'Plan de Seguridad y Evacuación', desc: 'Vías de escape, mitigación de riesgos y protección contra incendios' },
  { value: 'otro_entregable', label: 'Otro Entregable / Complementario', desc: 'Documento técnico de respaldo o anexo general' }
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
  currentDisciplineCode,
  onClose,
  onSaved
}) => {
  // RULES OF HOOKS: Todos los hooks declarados incondicionalmente al inicio
  const [disciplines, setDisciplines] = useState<ReviewDisciplineItem[]>([]);
  const [selectedDiscipline, setSelectedDiscipline] = useState<string>(
    currentDisciplineCode || document?.discipline || 'PIPING'
  );
  const [loadingDisciplines, setLoadingDisciplines] = useState<boolean>(false);
  const [deliverableType, setDeliverableType] = useState<DeliverableType>(currentDeliverableType);
  const [readinessStatus, setReadinessStatus] = useState<EvidenceReadinessStatus>(currentReadinessStatus);
  const [notes, setNotes] = useState<string>(currentNotes);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchDisciplines = async () => {
      setLoadingDisciplines(true);
      try {
        const discs = await apiService.getReviewDisciplines(true);
        if (isMounted) {
          setDisciplines(discs);
          if (!currentDisciplineCode && discs.length > 0) {
            const docDisc = (document?.discipline || '').toUpperCase();
            const matched = discs.find(d => d.code === docDisc || d.code === 'PIPING');
            if (matched) {
              setSelectedDiscipline(matched.code);
            } else {
              setSelectedDiscipline(discs[0].code);
            }
          }
        }
      } catch (err) {
        console.error('Error cargando especialidades en DocumentDeliverableModal:', err);
      } finally {
        if (isMounted) setLoadingDisciplines(false);
      }
    };

    if (isOpen) {
      fetchDisciplines();
      setDeliverableType(currentDeliverableType);
      setReadinessStatus(currentReadinessStatus);
      setNotes(currentNotes);
      setSelectedDiscipline(currentDisciplineCode || document?.discipline || 'PIPING');
      setError(null);
    }

    return () => {
      isMounted = false;
    };
  }, [isOpen, document?.id, currentDeliverableType, currentReadinessStatus, currentNotes, currentDisciplineCode, document?.discipline]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!document) return;
    setLoading(true);
    setError(null);
    try {
      await apiService.classifyDocumentDeliverable(document.id, {
        deliverable_type: deliverableType,
        discipline_code: selectedDiscipline,
        readiness_status: readinessStatus,
        validation_notes: notes
      });
      onSaved();
      onClose();
    } catch (err: any) {
      console.error(err);
      setError(err?.response?.data?.detail || 'Error al actualizar clasificación del entregable.');
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen || !document) return null;

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
          {/* Especialidad / Disciplina Técnica */}
          <div>
            <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1 flex items-center gap-1.5">
              <Compass className="w-3.5 h-3.5 text-indigo-400" />
              <span>Especialidad / Disciplina Técnica *</span>
            </label>
            <div className="relative">
              <select
                value={selectedDiscipline}
                onChange={(e) => setSelectedDiscipline(e.target.value)}
                disabled={loadingDisciplines}
                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-indigo-500 disabled:opacity-50"
              >
                {disciplines.length === 0 ? (
                  <option value={selectedDiscipline}>{selectedDiscipline}</option>
                ) : (
                  disciplines.map((d) => (
                    <option key={d.code} value={d.code}>
                      {d.name} ({d.code})
                    </option>
                  ))
                )}
              </select>
              {loadingDisciplines && (
                <Loader2 className="w-4 h-4 text-indigo-400 animate-spin absolute right-3 top-2.5 pointer-events-none" />
              )}
            </div>
            <p className="text-xs text-slate-500 mt-1">
              Asocia el documento a su disciplina técnica de ingeniería (Piping, Procesos, Electricidad, etc.) de forma desacoplada.
            </p>
          </div>

          {/* Tipo de Entregable Técnico */}
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
                  {opt.label}
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
              placeholder="Ej: Diagrama P&ID aprobado para construcción. Contiene especificación completa de tags y simbología."
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
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Guardando...</span>
                </>
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
