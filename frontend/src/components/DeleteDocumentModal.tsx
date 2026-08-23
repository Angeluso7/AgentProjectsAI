import React, { useState, useEffect } from 'react';
import {
  AlertTriangle,
  Trash2,
  Archive,
  FileText,
  Layers,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  HardDrive,
  Database
} from 'lucide-react';
import { DocumentItem, DocumentImpact } from '../types';
import { apiService } from '../services/api';

interface DeleteDocumentModalProps {
  isOpen: boolean;
  document: DocumentItem | null;
  onClose: () => void;
  onDeleted: (documentId: string, deleteType: 'soft_delete' | 'hard_delete') => void;
}

export const DeleteDocumentModal: React.FC<DeleteDocumentModalProps> = ({
  isOpen,
  document,
  onClose,
  onDeleted,
}) => {
  const [impact, setImpact] = useState<DocumentImpact | null>(null);
  const [loadingImpact, setLoadingImpact] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [hardDelete, setHardDelete] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const activeRole = localStorage.getItem('active_role') || 'viewer';
  const isAdmin = activeRole === 'admin';

  useEffect(() => {
    if (isOpen && document) {
      setLoadingImpact(true);
      setError(null);
      setHardDelete(false);
      apiService
        .getDocumentImpact(document.id)
        .then((data) => {
          setImpact(data);
        })
        .catch((err) => {
          console.error('Error cargando impacto de documento:', err);
          setError(err.response?.data?.detail || 'No se pudo cargar el análisis de impacto del documento.');
        })
        .finally(() => {
          setLoadingImpact(false);
        });
    } else {
      setImpact(null);
      setError(null);
      setIsDeleting(false);
    }
  }, [isOpen, document]);

  if (!isOpen || !document) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    setError(null);
    try {
      await apiService.deleteDocument(document.id, hardDelete);
      onDeleted(document.id, hardDelete ? 'hard_delete' : 'soft_delete');
      onClose();
    } catch (err: any) {
      console.error('Error eliminando documento:', err);
      setError(err.response?.data?.detail || 'Error durante la eliminación del documento.');
      setIsDeleting(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-labelledby="delete-doc-title"
    >
      <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${hardDelete ? 'bg-red-500/10 text-red-400' : 'bg-amber-500/10 text-amber-400'}`}>
              {hardDelete ? <Trash2 className="w-5 h-5" /> : <Archive className="w-5 h-5" />}
            </div>
            <div>
              <h2 id="delete-doc-title" className="text-lg font-semibold text-slate-100">
                {hardDelete ? 'Eliminar Documento Definitivamente' : 'Archivar / Eliminar Documento'}
              </h2>
              <p className="text-xs text-slate-400">
                Gestión de ciclo de vida e impacto de datos
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            disabled={isDeleting}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Cerrar modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto space-y-5">
          {/* Document Summary Card */}
          <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 flex items-start space-x-3">
            <FileText className="w-5 h-5 text-blue-400 mt-0.5 shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-slate-200 truncate">{document.filename}</p>
                <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 ml-2">
                  {document.page_count} {document.page_count === 1 ? 'lámina' : 'láminas'}
                </span>
              </div>
              <p className="text-xs text-slate-500 mt-1">
                ID: <span className="font-mono text-slate-400">{document.id}</span>
                {document.file_size_bytes && (
                  <span className="ml-2">({(document.file_size_bytes / (1024 * 1024)).toFixed(2)} MB)</span>
                )}
              </p>
            </div>
          </div>

          {/* Impact Analysis Section */}
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2.5 flex items-center space-x-2">
              <Layers className="w-4 h-4 text-slate-500" />
              <span>Impacto en Entidades Dependientes</span>
            </h4>

            {loadingImpact ? (
              <div className="p-6 rounded-xl bg-slate-950/40 border border-slate-800/50 flex flex-col items-center justify-center space-y-2">
                <Loader2 className="w-6 h-6 text-blue-500 animate-spin" />
                <p className="text-xs text-slate-400">Analizando dependencias y artefactos en base de datos...</p>
              </div>
            ) : impact ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Láminas Raster</span>
                  <span className="text-sm font-semibold text-slate-200">{impact.sheets_count}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Bloques OCR</span>
                  <span className="text-sm font-semibold text-slate-200">{impact.ocr_count}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Regiones Layout</span>
                  <span className="text-sm font-semibold text-slate-200">{impact.region_count}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800">
                  <span className="text-[11px] text-slate-400 block">Tablas & Símbolos</span>
                  <span className="text-sm font-semibold text-slate-200">{impact.table_count + impact.symbol_count}</span>
                </div>
                <div className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800 col-span-2 sm:col-span-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-400 block">Hallazgos QA/QC</span>
                    <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${impact.findings_count > 0 ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'}`}>
                      {impact.findings_count} hallazgos
                    </span>
                  </div>
                  {impact.findings_count > 0 && (
                    <div className="flex space-x-2 mt-1 text-[10px]">
                      {impact.severity_breakdown.critical > 0 && (
                        <span className="text-red-400 font-medium">{impact.severity_breakdown.critical} críticos</span>
                      )}
                      {impact.severity_breakdown.high > 0 && (
                        <span className="text-orange-400 font-medium">{impact.severity_breakdown.high} altos</span>
                      )}
                      {impact.severity_breakdown.medium > 0 && (
                        <span className="text-amber-400 font-medium">{impact.severity_breakdown.medium} medios</span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="p-3 rounded-lg bg-slate-950/40 border border-slate-800 text-xs text-slate-400">
                Información de dependencias no disponible.
              </div>
            )}
          </div>

          {/* Delete Type Selection */}
          <div className="space-y-2 pt-1">
            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">
              Tipo de Operación
            </h4>

            {/* Option 1: Soft Delete (Default) */}
            <label
              className={`flex items-start p-3 rounded-xl border cursor-pointer transition-all ${
                !hardDelete
                  ? 'bg-amber-500/10 border-amber-500/40 text-slate-200'
                  : 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700'
              }`}
            >
              <input
                type="radio"
                name="delete_type"
                checked={!hardDelete}
                onChange={() => setHardDelete(false)}
                className="mt-1 text-amber-500 focus:ring-amber-500 h-4 w-4 bg-slate-900 border-slate-700"
              />
              <div className="ml-3 text-xs">
                <span className="font-semibold text-amber-300 flex items-center space-x-1.5">
                  <Archive className="w-3.5 h-3.5 inline" />
                  <span>Archivar Documento (Recomendado)</span>
                </span>
                <p className="text-slate-400 mt-0.5">
                  Retira el plano del visor interactivo y oculta sus hallazgos, pero conserva el registro histórico en base de datos para trazabilidad de auditoría.
                </p>
              </div>
            </label>

            {/* Option 2: Hard Delete (Admin Only) */}
            {isAdmin ? (
              <label
                className={`flex items-start p-3 rounded-xl border cursor-pointer transition-all ${
                  hardDelete
                    ? 'bg-red-500/10 border-red-500/40 text-slate-200'
                    : 'bg-slate-950/40 border-slate-800 text-slate-400 hover:border-slate-700'
                }`}
              >
                <input
                  type="radio"
                  name="delete_type"
                  checked={hardDelete}
                  onChange={() => setHardDelete(true)}
                  className="mt-1 text-red-500 focus:ring-red-500 h-4 w-4 bg-slate-900 border-slate-700"
                />
                <div className="ml-3 text-xs">
                  <span className="font-semibold text-red-400 flex items-center space-x-1.5">
                    <Trash2 className="w-3.5 h-3.5 inline" />
                    <span>Eliminación Definitiva (Hard-Delete - Solo Admin)</span>
                  </span>
                  <p className="text-slate-400 mt-0.5">
                    Purga permanente de todas las entidades en base de datos y borrado físico de archivos PDF y PNGs del disco. Esta acción no se puede deshacer.
                  </p>
                </div>
              </label>
            ) : (
              <div className="p-2.5 rounded-lg bg-slate-950/20 border border-slate-800/40 text-[11px] text-slate-500 flex items-center space-x-2">
                <Database className="w-3.5 h-3.5 text-slate-600 shrink-0" />
                <span>La eliminación definitiva de bajo nivel está restringida a administradores.</span>
              </div>
            )}
          </div>

          {/* Warning Banner */}
          <div className={`p-3 rounded-xl border flex items-start space-x-2.5 text-xs ${
            hardDelete
              ? 'bg-red-950/30 border-red-800/50 text-red-300'
              : 'bg-amber-950/30 border-amber-800/50 text-amber-300'
          }`}>
            <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
            <p>
              {hardDelete
                ? 'Atención: Se eliminarán todos los análisis OCR, recortes, detecciones y archivos físicos asociados a este documento.'
                : 'Al archivar, la lámina dejará de estar disponible para revisión activa en el visor.'}
            </p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="p-3 rounded-xl bg-red-950/40 border border-red-800 text-xs text-red-300 flex items-start space-x-2">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/80 flex items-center justify-end space-x-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isDeleting}
            className="px-4 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-xl transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>
          <button
            type="button"
            onClick={handleDelete}
            disabled={isDeleting || loadingImpact}
            className={`px-4 py-2 text-xs font-medium text-white rounded-xl transition-all flex items-center space-x-2 shadow-lg disabled:opacity-50 ${
              hardDelete
                ? 'bg-red-600 hover:bg-red-500 shadow-red-950/50'
                : 'bg-amber-600 hover:bg-amber-500 shadow-amber-950/50'
            }`}
          >
            {isDeleting ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Procesando...</span>
              </>
            ) : (
              <>
                {hardDelete ? <Trash2 className="w-4 h-4" /> : <Archive className="w-4 h-4" />}
                <span>{hardDelete ? 'Eliminar Definitivamente' : 'Confirmar Archivado'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
