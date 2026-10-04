import React, { useState, useEffect } from 'react';
import { Project, ProjectDeletionImpact } from '../types';
import { apiService } from '../services/api';
import {
  Trash2, AlertTriangle, X, ShieldAlert, Eraser, FileText,
  HardDrive, Layers, Search, CheckCircle2, AlertCircle, RefreshCw
} from 'lucide-react';

interface ProjectDeleteModalProps {
  isOpen: boolean;
  project: Project | null;
  initialMode?: 'clear_content' | 'delete';
  isActiveProject?: boolean;
  onClose: () => void;
  onClearContent: (projectId: string, confirmationCode: string, reason?: string) => Promise<void>;
  onDeleteConfirmed: (
    projectId: string,
    confirmationCode: string,
    mode: 'hard_delete' | 'anonymize',
    reason?: string
  ) => Promise<void>;
}

export const ProjectDeleteModal: React.FC<ProjectDeleteModalProps> = ({
  isOpen,
  project,
  initialMode = 'delete',
  isActiveProject = false,
  onClose,
  onClearContent,
  onDeleteConfirmed,
}) => {
  const [activeTab, setActiveTab] = useState<'clear_content' | 'delete'>(initialMode);
  const [confirmInput, setConfirmInput] = useState('');
  const [reasonInput, setReasonInput] = useState('');
  const [deleteMode, setDeleteMode] = useState<'hard_delete' | 'anonymize'>('hard_delete');
  const [acknowledgeLoss, setAcknowledgeLoss] = useState(false);
  const [impact, setImpact] = useState<ProjectDeletionImpact | null>(null);
  const [loadingImpact, setLoadingImpact] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialMode);
      setConfirmInput('');
      setReasonInput('');
      setAcknowledgeLoss(false);
      setError(null);
      if (project?.id) {
        fetchImpact(project.id);
      }
    }
  }, [isOpen, project, initialMode]);

  const fetchImpact = async (projectId: string) => {
    try {
      setLoadingImpact(true);
      const data = await apiService.getProjectDeletionImpact(projectId);
      setImpact(data);
    } catch (err: any) {
      console.error('Error al cargar impacto de eliminación:', err);
      // Fallback a contadores básicos del proyecto
      setImpact({
        project_id: projectId,
        project_code: project?.code || '',
        documents: project?.documents_count ?? 0,
        stored_files: project?.documents_count ?? 0,
        extractions: 0,
        evaluation_runs: 0,
        findings: project?.findings_count ?? 0,
        reports: 0,
        symbol_occurrences: project?.sheets_count ?? 0,
        can_hard_delete: true,
        blocking_reasons: []
      });
    } finally {
      setLoadingImpact(false);
    }
  };

  const normalizeCode = (str?: string | null): string => {
    if (!str) return '';
    return str.replace(/\s+/g, ' ').trim().toUpperCase();
  };

  if (!isOpen || !project) return null;

  const expectedCode = normalizeCode(project.code);
  const normalizedInput = normalizeCode(confirmInput);
  const isCodeMatch = normalizedInput === expectedCode && expectedCode.length > 0;
  
  const isHardDeleteBlocked =
    activeTab === 'delete' &&
    deleteMode === 'hard_delete' &&
    impact?.can_hard_delete === false &&
    (impact.blocking_reasons?.length ?? 0) > 0;

  const isHardDeleteConfirmationValid =
    activeTab === 'delete' &&
    deleteMode === 'hard_delete' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isHardDeleteBlocked &&
    !isProcessing;

  const isAnonymizeConfirmationValid =
    activeTab === 'delete' &&
    deleteMode === 'anonymize' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isProcessing;

  const isClearContentValid =
    activeTab === 'clear_content' &&
    isCodeMatch &&
    acknowledgeLoss &&
    !isProcessing;

  const canSubmit = isHardDeleteConfirmationValid || isAnonymizeConfirmationValid || isClearContentValid;

  // Diagnóstico de depuración en consola para auditar condiciones del botón
  if (isOpen) {
    console.debug('[ProjectDeleteModal Diagnostic]', {
      projectCode: project.code,
      expectedCode,
      inputRaw: confirmInput,
      normalizedInput,
      isCodeMatch,
      acknowledgeLoss,
      activeTab,
      deleteMode,
      can_hard_delete: impact?.can_hard_delete,
      blocking_reasons: impact?.blocking_reasons,
      isHardDeleteBlocked,
      isProcessing,
      canSubmit
    });
  }

  const handleAction = async () => {
    if (!isCodeMatch) {
      setError(`Debes escribir exactamente el código «${project.code}» para confirmar.`);
      return;
    }
    if (!acknowledgeLoss) {
      setError('Debes confirmar que comprendes la pérdida irreversible de los datos.');
      return;
    }
    if (isHardDeleteBlocked) {
      setError(`Eliminación bloqueada: ${impact?.blocking_reasons.join(', ')}`);
      return;
    }

    try {
      setIsProcessing(true);
      setError(null);

      if (activeTab === 'clear_content') {
        await onClearContent(project.id, normalizedInput, reasonInput.trim() || undefined);
      } else {
        await onDeleteConfirmed(project.id, normalizedInput, deleteMode, reasonInput.trim() || undefined);
      }
      onClose();
    } catch (err: any) {
      console.error('Error ejecutando ciclo de vida:', err);
      setError(err.response?.data?.detail || err.message || 'Error al ejecutar la operación.');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.88)',
        backdropFilter: 'blur(5px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1100,
        padding: '16px',
        animation: 'fade-in 0.15s ease-out',
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: '#020617',
          borderColor: activeTab === 'delete' ? '#7f1d1d' : '#854d0e',
          borderWidth: '1px',
          borderStyle: 'solid',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.95)',
          borderRadius: '20px',
          width: '100%',
          maxWidth: '560px',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Encabezado */}
        <div className={`px-6 py-4 border-b flex items-center justify-between ${
          activeTab === 'delete'
            ? 'border-rose-900/60 bg-rose-950/40'
            : 'border-amber-900/60 bg-amber-950/40'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl border ${
              activeTab === 'delete'
                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
            }`}>
              {activeTab === 'delete' ? <ShieldAlert className="w-5 h-5" /> : <Eraser className="w-5 h-5" />}
            </div>
            <div>
              <h2 className={`text-base font-bold ${activeTab === 'delete' ? 'text-rose-200' : 'text-amber-200'}`}>
                {activeTab === 'delete' ? 'Eliminación Protegida de Proyecto' : 'Vaciar Contenido del Proyecto'}
              </h2>
              <p className="text-xs text-slate-400">
                {activeTab === 'delete'
                  ? 'Acción destructiva con purga de almacenamiento y registros'
                  : 'Purga de documentos y resultados conservando la ficha del proyecto'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Pestañas de Modo */}
        <div className="flex border-b border-slate-800 bg-slate-950/60">
          <button
            type="button"
            onClick={() => { setActiveTab('clear_content'); setError(null); }}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === 'clear_content'
                ? 'border-amber-500 text-amber-300 bg-amber-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Eraser className="w-3.5 h-3.5" />
            <span>Vaciar Contenido</span>
          </button>
          <button
            type="button"
            onClick={() => { setActiveTab('delete'); setError(null); }}
            className={`flex-1 py-2.5 text-xs font-semibold flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === 'delete'
                ? 'border-rose-500 text-rose-300 bg-rose-950/20'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Eliminar Proyecto</span>
          </button>
        </div>

        {/* Cuerpo */}
        <div className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/80 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <strong>Error:</strong> {error}
              </div>
            </div>
          )}

          {/* Aviso si es el proyecto activo */}
          {isActiveProject && (
            <div className="p-3 rounded-xl bg-amber-950/40 border border-amber-800/80 flex items-start gap-2 text-xs text-amber-300">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong>Proyecto Activo en Sesión:</strong> Al {activeTab === 'delete' ? 'eliminar' : 'vaciar'} este proyecto, el selector global se desvinculará y quedará en <em>«Sin proyecto activo»</em>.
              </div>
            </div>
          )}

          {/* Ficha resumida del proyecto */}
          <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400">Proyecto objetivo:</span>
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-slate-950 text-blue-300 border border-slate-700 rounded">
                {project.code}
              </span>
            </div>
            <p className="text-sm font-bold text-slate-100">{project.name}</p>
            {project.client_name && (
              <p className="text-xs text-slate-400">Cliente: <strong className="text-slate-200">{project.client_name}</strong></p>
            )}
          </div>

          {/* Matriz de Impacto */}
          <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2.5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-300 flex items-center gap-1.5">
                <HardDrive className="w-3.5 h-3.5 text-blue-400" />
                Impacto Calculado sobre Almacenamiento y BD:
              </span>
              {loadingImpact && (
                <span className="text-[11px] text-slate-500 flex items-center gap-1">
                  <RefreshCw className="w-3 h-3 animate-spin" /> Calculando...
                </span>
              )}
            </div>

            <div className="grid grid-cols-4 gap-2 text-center">
              <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                <div className="text-base font-bold font-mono text-slate-100">{impact?.documents ?? project.documents_count ?? 0}</div>
                <div className="text-[10px] text-slate-400">Documentos</div>
              </div>
              <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                <div className="text-base font-bold font-mono text-blue-300">{impact?.stored_files ?? 0}</div>
                <div className="text-[10px] text-slate-400">Archivos Disco</div>
              </div>
              <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                <div className="text-base font-bold font-mono text-amber-300">{impact?.findings ?? project.findings_count ?? 0}</div>
                <div className="text-[10px] text-slate-400">Hallazgos</div>
              </div>
              <div className="p-2 rounded-lg bg-slate-900 border border-slate-800">
                <div className="text-base font-bold font-mono text-purple-300">{impact?.reports ?? 0}</div>
                <div className="text-[10px] text-slate-400">Reportes</div>
              </div>
            </div>

            {impact?.blocking_reasons && impact.blocking_reasons.length > 0 && (
              <div className="p-2.5 rounded-lg bg-rose-950/60 border border-rose-800 text-[11px] text-rose-300 space-y-1">
                <div className="font-bold flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400" />
                  Operaciones bloqueantes en curso:
                </div>
                {impact.blocking_reasons.map((reason, idx) => (
                  <div key={idx}>• {reason}</div>
                ))}
              </div>
            )}
          </div>

          {/* Opciones de modo para Eliminación Definitiva */}
          {activeTab === 'delete' && (
            <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
              <span className="text-xs font-semibold text-slate-300 block">Modo de Eliminación:</span>
              <div className="grid grid-cols-2 gap-2">
                <label className={`p-2.5 rounded-xl border cursor-pointer flex flex-col gap-1 transition-all ${
                  deleteMode === 'hard_delete'
                    ? 'bg-rose-950/40 border-rose-700 text-rose-200'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}>
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <input
                      type="radio"
                      name="deleteMode"
                      checked={deleteMode === 'hard_delete'}
                      onChange={() => setDeleteMode('hard_delete')}
                      className="text-rose-600 focus:ring-rose-500"
                    />
                    <span>Hard Delete</span>
                  </div>
                  <span className="text-[10px] opacity-80 leading-tight">
                    Elimina completamente el registro de la BD y purga todos los archivos en disco.
                  </span>
                </label>

                <label className={`p-2.5 rounded-xl border cursor-pointer flex flex-col gap-1 transition-all ${
                  deleteMode === 'anonymize'
                    ? 'bg-amber-950/40 border-amber-700 text-amber-200'
                    : 'bg-slate-950 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}>
                  <div className="flex items-center gap-2 font-bold text-xs">
                    <input
                      type="radio"
                      name="deleteMode"
                      checked={deleteMode === 'anonymize'}
                      onChange={() => setDeleteMode('anonymize')}
                      className="text-amber-600 focus:ring-amber-500"
                    />
                    <span>Anonimizar</span>
                  </div>
                  <span className="text-[10px] opacity-80 leading-tight">
                    Purga archivos y anonimiza nombres, manteniendo el histórico para retención legal.
                  </span>
                </label>
              </div>
            </div>
          )}

          {/* Motivo opcional */}
          <div>
            <label className="block text-xs font-medium text-slate-400 mb-1">
              Motivo o justificación de auditoría (opcional):
            </label>
            <input
              type="text"
              value={reasonInput}
              onChange={(e) => setReasonInput(e.target.value)}
              placeholder={activeTab === 'delete' ? 'Ej: Fin de ciclo de vida / Proyecto de prueba' : 'Ej: Re-ingesta completa de la disciplina'}
              className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Confirmación por código */}
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-medium text-slate-300 leading-relaxed">
                Para confirmar, escribe el código exacto <strong className="text-rose-400 font-mono select-all bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-900">{project.code}</strong>:
              </label>
              <button
                type="button"
                onClick={() => setConfirmInput(project.code)}
                className="text-[11px] text-blue-400 hover:text-blue-300 underline font-mono cursor-pointer shrink-0 ml-2"
                title="Copiar y autocompletar código exacto del proyecto"
              >
                Auto-rellenar
              </button>
            </div>
            <input
              type="text"
              autoFocus
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              placeholder={project.code}
              className={`w-full px-3 py-2 text-xs font-mono font-bold rounded-xl bg-slate-950 border text-slate-100 focus:outline-none tracking-wider transition-colors ${
                isCodeMatch
                  ? 'border-emerald-500 focus:border-emerald-400'
                  : confirmInput.trim() !== ''
                  ? 'border-rose-700 focus:border-rose-500'
                  : 'border-slate-800 focus:border-blue-500'
              }`}
            />
            {/* Mensajes de validación en tiempo real del código */}
            <div className="mt-1.5 text-[11px]">
              {confirmInput.trim() === '' ? (
                <span className="text-slate-500 flex items-center gap-1">
                  <Search className="w-3 h-3" /> Escribe el código exacto del proyecto para habilitar la confirmación.
                </span>
              ) : isCodeMatch ? (
                <span className="text-emerald-400 font-semibold flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" /> Código confirmado ({expectedCode})
                </span>
              ) : (
                <span className="text-rose-400 font-semibold flex items-center gap-1">
                  <AlertCircle className="w-3.5 h-3.5 text-rose-400" /> Código no coincide (ingresado: «{normalizedInput}», esperado: «{expectedCode}»)
                </span>
              )}
            </div>
          </div>

          {/* Checkbox de Reconocimiento de Pérdida de Datos */}
          <div className="space-y-1.5">
            <div className={`p-3 rounded-xl bg-slate-950 border flex items-start gap-2.5 transition-colors ${
              acknowledgeLoss ? 'border-emerald-800/80 bg-emerald-950/10' : 'border-slate-800'
            }`}>
              <input
                type="checkbox"
                id="acknowledgeDataLossCheck"
                checked={acknowledgeLoss}
                onChange={(e) => setAcknowledgeLoss(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 text-rose-600 focus:ring-rose-500 bg-slate-900 cursor-pointer mt-0.5"
              />
              <label htmlFor="acknowledgeDataLossCheck" className="text-xs text-slate-300 cursor-pointer select-none leading-relaxed">
                Confirmo que comprendo la pérdida irreversible de los archivos, documentos, extracciones y resultados asociados.
              </label>
            </div>
            {!acknowledgeLoss && (
              <p className="text-[11px] text-amber-400/90 pl-1 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3 text-amber-400" /> Debes marcar esta casilla para habilitar el botón de confirmación.
              </p>
            )}
          </div>

          {/* Banner de resumen de condiciones antes del botón */}
          {!canSubmit && !isProcessing && (
            <div className="p-2.5 rounded-xl bg-slate-900/90 border border-slate-800 text-[11px] text-slate-400 flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-slate-300">Pendiente para habilitar: </strong>
                {!isCodeMatch ? (
                  <span>Falta escribir el código exacto «{project.code}».</span>
                ) : !acknowledgeLoss ? (
                  <span>Falta marcar la casilla de confirmación de pérdida de datos.</span>
                ) : isHardDeleteBlocked ? (
                  <span>
                    Eliminación física bloqueada por tareas activas. Selecciona el modo <em>«Anonimizar»</em> o espera a que finalicen.
                  </span>
                ) : (
                  <span>Completa los pasos requeridos arriba.</span>
                )}
              </div>
            </div>
          )}

          {/* Botones de acción */}
          <div className="pt-2 flex items-center justify-between">
            <span className="text-[10px] font-mono text-slate-500">
              Build: fix/project-lifecycle (v0.2.2)
            </span>
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={onClose}
                disabled={isProcessing}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleAction}
                disabled={!canSubmit}
                id="btn-confirm-project-lifecycle"
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl shadow-lg flex items-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
                  activeTab === 'delete'
                    ? 'bg-rose-600 hover:bg-rose-500 active:bg-rose-700 shadow-rose-600/30'
                    : 'bg-amber-600 hover:bg-amber-500 active:bg-amber-700 shadow-amber-600/30'
                }`}
              >
                {isProcessing ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Procesando...</span>
                  </>
                ) : activeTab === 'delete' ? (
                  <>
                    <Trash2 className="w-4 h-4" />
                    <span>Confirmar Eliminación Permanente</span>
                  </>
                ) : (
                  <>
                    <Eraser className="w-4 h-4" />
                    <span>Confirmar Vaciado de Contenido</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
