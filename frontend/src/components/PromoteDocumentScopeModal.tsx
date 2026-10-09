import React, { useState, useEffect } from 'react';
import { apiService } from '../services/api';
import { ReviewDisciplineItem, ReviewTopicItem } from '../types';
import { ShieldCheck, RefreshCw, X, AlertCircle, CheckCircle2, Layers, Tag, Loader2 } from 'lucide-react';

export interface PromoteDocumentScopeModalProps {
  isOpen: boolean;
  onClose: () => void;
  mode: 'promote' | 'resync';
  documentId: string;
  documentTitle: string;
  documentDiscipline?: string;
  rulesCount: number;
  onSuccess: (result: any) => void;
}

export const PromoteDocumentScopeModal: React.FC<PromoteDocumentScopeModalProps> = ({
  isOpen,
  onClose,
  mode,
  documentId,
  documentTitle,
  documentDiscipline,
  rulesCount,
  onSuccess
}) => {
  // RULE OF HOOKS: All hooks unconditionally declared at the top
  const [disciplines, setDisciplines] = useState<ReviewDisciplineItem[]>([]);
  const [topics, setTopics] = useState<ReviewTopicItem[]>([]);
  const [selectedDiscipline, setSelectedDiscipline] = useState<string>('PIPING');
  const [selectedTopic, setSelectedTopic] = useState<string>('');
  const [loadingTaxonomy, setLoadingTaxonomy] = useState<boolean>(false);
  const [loadingTopics, setLoadingTopics] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Normalizar disciplina del documento para sugerencia inicial
  const normalizeInitialDiscipline = (rawDisc?: string, availableDiscs: ReviewDisciplineItem[] = []): string => {
    if (!rawDisc) return 'PIPING';
    const clean = rawDisc.trim().toUpperCase();
    const aliasMap: Record<string, string> = {
      'PIPING': 'PIPING',
      'TUBERIAS': 'PIPING',
      'CANERIAS': 'PIPING',
      'CAÑERIAS': 'PIPING',
      'PROCESS': 'PIPING',
      'PROCESO': 'PIPING',
      'PROCESOS': 'PIPING',
      'GENERAL': 'GENERAL',
      'GEN': 'GENERAL',
      'ARCHITECTURE': 'ARCHITECTURE',
      'ARQUITECTURA': 'ARCHITECTURE',
      'STRUCTURES': 'STRUCTURES',
      'ESTRUCTURAS': 'STRUCTURES',
      'ELECTRICAL': 'ELECTRICAL',
      'ELECTRICIDAD': 'ELECTRICAL',
      'INSTRUMENTATION': 'INSTRUMENTATION_CONTROL',
      'INSTRUMENTACION': 'INSTRUMENTATION_CONTROL',
      'HVAC': 'HVAC',
      'CLIMATIZACION': 'HVAC',
      'CIVIL': 'CIVIL',
      'SANITARY': 'SANITARY',
      'SANITARIO': 'SANITARY',
      'FIRE_PROTECTION': 'FIRE_PROTECTION',
      'INCENDIO': 'FIRE_PROTECTION'
    };
    const mapped = aliasMap[clean] || clean;
    const exists = availableDiscs.some(d => d.code === mapped && d.is_active);
    if (exists) return mapped;
    if (availableDiscs.some(d => d.code === 'PIPING')) return 'PIPING';
    return availableDiscs[0]?.code || 'GENERAL';
  };

  // Cargar disciplinas al abrir el modal
  useEffect(() => {
    if (!isOpen) return;

    let isMounted = true;
    const fetchDisciplines = async () => {
      setLoadingTaxonomy(true);
      setError(null);
      try {
        const discs = await apiService.getReviewDisciplines(true);
        if (isMounted) {
          setDisciplines(discs);
          const initialDisc = normalizeInitialDiscipline(documentDiscipline, discs);
          setSelectedDiscipline(initialDisc);
        }
      } catch (err: any) {
        if (isMounted) {
          console.error('Error cargando disciplinas:', err);
          setError('No fue posible cargar las especialidades del catálogo.');
        }
      } finally {
        if (isMounted) {
          setLoadingTaxonomy(false);
        }
      }
    };

    fetchDisciplines();

    return () => {
      isMounted = false;
    };
  }, [isOpen, documentDiscipline]);

  // Cargar tópicos cuando cambia la disciplina seleccionada
  useEffect(() => {
    if (!isOpen || !selectedDiscipline) return;

    let isMounted = true;
    const fetchTopics = async () => {
      setLoadingTopics(true);
      setError(null);
      try {
        const tops = await apiService.getReviewTopics(selectedDiscipline, true);
        if (isMounted) {
          setTopics(tops);
          if (tops.length > 0) {
            // Priorizar PID_SYMBOLS si está presente, de lo contrario el primer tópico
            const pidSymbols = tops.find(t => t.code === 'PID_SYMBOLS');
            setSelectedTopic(pidSymbols ? pidSymbols.code : tops[0].code);
          } else {
            setSelectedTopic('');
          }
        }
      } catch (err: any) {
        if (isMounted) {
          console.error('Error cargando tópicos para disciplina:', err);
          setError('No fue posible cargar los puntos de revisión para la disciplina seleccionada.');
        }
      } finally {
        if (isMounted) {
          setLoadingTopics(false);
        }
      }
    };

    fetchTopics();

    return () => {
      isMounted = false;
    };
  }, [isOpen, selectedDiscipline]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDiscipline || !selectedTopic) {
      setError('Por favor selecciona una Disciplina y un Punto de Revisión.');
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      if (mode === 'promote') {
        const res = await apiService.promoteRuleDocumentToBaseline(documentId, {
          discipline_code: selectedDiscipline,
          topic_code: selectedTopic
        });
        onSuccess(res);
      } else {
        const res = await apiService.resyncRuleDocumentApplicability(documentId, {
          discipline_code: selectedDiscipline,
          topic_code: selectedTopic
        });
        onSuccess(res);
      }
      onClose();
    } catch (err: any) {
      console.error('Error en promoción/resincronización:', err);
      const msg = err?.response?.data?.detail || (mode === 'promote' ? 'Error al promover reglas.' : 'Error al re-sincronizar aplicabilidad.');
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  // Render condicional seguro DESPUÉS de todos los hooks
  if (!isOpen) return null;

  return (
    <div
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.85)', backdropFilter: 'blur(4px)' }}
      className="fixed inset-0 z-[120] flex items-center justify-center p-4 animate-in fade-in duration-150"
    >
      <div
        style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
        className="w-full max-w-lg p-6 border rounded-2xl shadow-2xl space-y-5 text-xs text-slate-200"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className={`p-2 rounded-xl ${mode === 'promote' ? 'bg-indigo-950/80 border border-indigo-700 text-indigo-300' : 'bg-emerald-950/80 border border-emerald-700 text-emerald-300'}`}>
              {mode === 'promote' ? <ShieldCheck className="w-5 h-5" /> : <RefreshCw className="w-5 h-5" />}
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-100">
                {mode === 'promote' ? 'Promover a Baseline QA/QC' : 'Re-sincronizar Alcance de Evaluación'}
              </h3>
              <p className="text-[11px] text-slate-400">
                {mode === 'promote'
                  ? 'Vincular reglas al catálogo activo y definir su alcance de revisión One-Click.'
                  : 'Corregir la especialidad y punto de revisión de las reglas ya promovidas.'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={submitting}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-slate-800 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Resumen del Documento */}
        <div style={{ backgroundColor: '#1e293b' }} className="p-3.5 rounded-xl border border-slate-700/60 space-y-1.5">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-slate-200 truncate pr-2">{documentTitle}</span>
            <span className="px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800 text-[10px] font-bold shrink-0">
              {rulesCount} reglas
            </span>
          </div>
          <div className="flex items-center gap-2 text-[11px] text-slate-400">
            <Tag className="w-3.5 h-3.5 text-slate-500" />
            <span>Disciplina original del documento:</span>
            <span className="font-semibold text-slate-300">{documentDiscipline || 'No especificada'}</span>
          </div>
        </div>

        {error && (
          <div className="p-3 rounded-xl bg-rose-950/40 border border-rose-800 text-rose-300 flex items-start gap-2 text-[11px]">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Selector de Disciplina */}
          <div>
            <label className="block font-semibold text-slate-300 mb-1.5">
              1. Disciplina / Especialidad de Evaluación *
            </label>
            {loadingTaxonomy ? (
              <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-2 text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span>Cargando especialidades...</span>
              </div>
            ) : (
              <select
                value={selectedDiscipline}
                onChange={(e) => setSelectedDiscipline(e.target.value)}
                disabled={submitting}
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full px-3 py-2 rounded-xl border text-slate-100 font-semibold focus:outline-none focus:border-indigo-500"
              >
                {disciplines.map((d) => (
                  <option key={d.id} value={d.code}>
                    {d.code} — {d.name}
                  </option>
                ))}
              </select>
            )}
            <p className="text-[10px] text-slate-400 mt-1">
              Las reglas se indexarán para las auditorías One-Click Review de esta especialidad.
            </p>
          </div>

          {/* Selector de Punto de Revisión */}
          <div>
            <label className="block font-semibold text-slate-300 mb-1.5">
              2. Punto de Revisión / Tópico *
            </label>
            {loadingTopics ? (
              <div className="p-2.5 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-2 text-slate-400">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                <span>Cargando puntos de revisión...</span>
              </div>
            ) : (
              <select
                value={selectedTopic}
                onChange={(e) => setSelectedTopic(e.target.value)}
                disabled={submitting || topics.length === 0}
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full px-3 py-2 rounded-xl border text-slate-100 font-semibold focus:outline-none focus:border-indigo-500"
              >
                {topics.map((t) => (
                  <option key={t.id} value={t.code}>
                    {t.code} — {t.name} {t.is_transversal ? '(Transversal)' : ''}
                  </option>
                ))}
              </select>
            )}
            <p className="text-[10px] text-slate-400 mt-1">
              Ejemplo: para planos P&ID seleccione <strong>PID_SYMBOLS (Simbología de Válvulas y Equipos P&ID)</strong>.
            </p>
          </div>

          {/* Banner explicativo */}
          <div style={{ backgroundColor: '#091e3a', borderColor: '#1d4ed8' }} className="p-3 rounded-xl border text-[11px] text-sky-200 flex items-start gap-2">
            <Layers className="w-4 h-4 shrink-0 mt-0.5 text-sky-400" />
            <p>
              {mode === 'promote'
                ? 'Al confirmar, el sistema resolverá de forma determinística la aplicabilidad de las reglas hacia el alcance seleccionado, haciéndolas inmediatamente visibles y ejecutables en One-Click Review.'
                : 'Esta acción repara de forma atómica la aplicabilidad de todas las reglas de este documento en el motor, sin generar duplicados.'}
            </p>
          </div>

          {/* Botones de acción */}
          <div className="flex items-center justify-end gap-2.5 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-3.5 py-2 text-slate-400 hover:text-white rounded-xl transition-colors font-medium"
            >
              Cancelar
            </button>
            <button
              type="submit"
              disabled={submitting || !selectedDiscipline || !selectedTopic}
              className={`px-4 py-2 font-bold rounded-xl text-white shadow-lg flex items-center gap-1.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                mode === 'promote'
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500'
                  : 'bg-emerald-600 hover:bg-emerald-500'
              }`}
            >
              {submitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>{mode === 'promote' ? 'Promoviendo...' : 'Re-sincronizando...'}</span>
                </>
              ) : mode === 'promote' ? (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Confirmar y Promover ({rulesCount} reglas)</span>
                </>
              ) : (
                <>
                  <RefreshCw className="w-4 h-4" />
                  <span>Actualizar Alcance ({rulesCount} reglas)</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
