import React, { useState } from 'react';
import { Project } from '../types';
import { Trash2, AlertTriangle, X, ShieldAlert } from 'lucide-react';

interface ProjectDeleteModalProps {
  isOpen: boolean;
  project: Project | null;
  onClose: () => void;
  onConfirm: (projectId: string, hardDelete: boolean) => Promise<void>;
}

export const ProjectDeleteModal: React.FC<ProjectDeleteModalProps> = ({
  isOpen,
  project,
  onClose,
  onConfirm
}) => {
  const [confirmInput, setConfirmInput] = useState('');
  const [hardDelete, setHardDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !project) return null;

  const expectedCode = project.code.trim().toUpperCase();
  const isMatch = confirmInput.trim().toUpperCase() === expectedCode;

  const handleDelete = async () => {
    if (!isMatch) {
      setError(`Debes escribir exactamente el código «${project.code}» para confirmar.`);
      return;
    }

    try {
      setDeleting(true);
      setError(null);
      await onConfirm(project.id, hardDelete);
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al eliminar el proyecto.');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        backgroundColor: 'rgba(2, 6, 23, 0.85)',
        backdropFilter: 'blur(4px)',
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
          borderColor: '#450a0a',
          boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.9), 0 0 0 1px #7f1d1d',
          borderRadius: '16px',
          width: '100%',
          maxWidth: '520px',
          overflow: 'hidden',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Encabezado Rojo de Advertencia */}
        <div className="px-6 py-4 border-b border-rose-900/50 flex items-center justify-between bg-rose-950/40">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-rose-200">
                Eliminación Protegida de Proyecto
              </h2>
              <p className="text-xs text-rose-400/80">
                Esta acción retirará el proyecto del sistema
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

        {/* Cuerpo */}
        <div className="p-6 space-y-4">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/80 border border-rose-800 text-xs text-rose-300">
              {error}
            </div>
          )}

          <div className="p-3.5 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-300">Proyecto a eliminar:</span>
              <span className="px-2 py-0.5 text-xs font-mono font-bold bg-rose-950 text-rose-300 border border-rose-800 rounded">
                {project.code}
              </span>
            </div>
            <p className="text-sm font-bold text-slate-100">{project.name}</p>
            <div className="flex items-center gap-3 text-[11px] text-slate-400 pt-1 border-t border-slate-800">
              <span>Etapa: <strong>{project.stage || 'Ingeniería de Detalle'}</strong></span>
              <span>•</span>
              <span>Documentos: <strong>{project.documents_count ?? 0}</strong></span>
              <span>•</span>
              <span>Láminas: <strong>{project.sheets_count ?? 0}</strong></span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-300 mb-1.5 leading-relaxed">
              Para confirmar, escribe el código exacto <strong className="text-rose-400 font-mono select-all">{project.code}</strong> a continuación:
            </label>
            <input
              type="text"
              autoFocus
              value={confirmInput}
              onChange={(e) => setConfirmInput(e.target.value)}
              placeholder={project.code}
              className="w-full px-3 py-2 text-xs font-mono font-bold rounded-xl bg-slate-950 border border-slate-800 text-slate-100 focus:outline-none focus:border-rose-500 tracking-wider"
            />
          </div>

          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <input
                type="checkbox"
                id="hardDeleteCheck"
                checked={hardDelete}
                onChange={(e) => setHardDelete(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 text-rose-600 focus:ring-rose-500 bg-slate-900 cursor-pointer"
              />
              <label htmlFor="hardDeleteCheck" className="text-xs text-slate-300 cursor-pointer">
                Borrado físico definitivo (elimina datos relacionados)
              </label>
            </div>
            <span className="text-[10px] text-slate-500">
              {hardDelete ? '⚠️ Irreversible' : '🛡️ Soft Delete (Seguro)'}
            </span>
          </div>

          {/* Acciones */}
          <div className="pt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              disabled={deleting}
              className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors"
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={!isMatch || deleting}
              className="px-5 py-2 text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 active:bg-rose-700 rounded-xl shadow-lg shadow-rose-600/30 flex items-center gap-2 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {deleting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Eliminando...</span>
                </>
              ) : (
                <>
                  <Trash2 className="w-4 h-4" />
                  <span>Confirmar Eliminación</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
