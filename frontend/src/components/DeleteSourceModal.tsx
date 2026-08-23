import React, { useEffect, useState } from 'react';
import {
  AlertTriangle, Trash2, Archive, X, FileText, CheckCircle2,
  HardDrive, Layers, ShieldAlert, RefreshCw, AlertCircle
} from 'lucide-react';
import { apiService } from '../services/api';
import { SourceAssetItem, SourceDependenciesInfo } from '../types';

interface DeleteSourceModalProps {
  source: SourceAssetItem;
  onClose: () => void;
  onSuccess: (message: string) => void;
}

export const DeleteSourceModal: React.FC<DeleteSourceModalProps> = ({
  source,
  onClose,
  onSuccess
}) => {
  const [dependencies, setDependencies] = useState<SourceDependenciesInfo | null>(null);
  const [loadingDeps, setLoadingDeps] = useState(true);
  const [hardDelete, setHardDelete] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    loadDependencies();
  }, [source.id]);

  const loadDependencies = async () => {
    try {
      setLoadingDeps(true);
      setErrorMsg(null);
      const data = await apiService.getSourceDependencies(source.id);
      setDependencies(data);
      // Si no tiene dependencias, por defecto puede ser hard delete seguro
      if (data.can_hard_delete) {
        setHardDelete(true);
      } else {
        setHardDelete(false);
      }
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error al consultar dependencias de la fuente.');
    } finally {
      setLoadingDeps(false);
    }
  };

  const handleConfirmDelete = async () => {
    try {
      setIsDeleting(true);
      setErrorMsg(null);
      const res = await apiService.deleteSource(source.id, hardDelete);
      onSuccess(res.message);
      onClose();
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Error al procesar la eliminación de la fuente.');
    } finally {
      setIsDeleting(false);
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const hasDependencies = (dependencies?.extractions_count || 0) > 0 || (dependencies?.rule_documents_count || 0) > 0;

  return (
    <div className="modal-backdrop" style={{
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.75)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1100,
      backdropFilter: 'blur(4px)'
    }}>
      <div className="card" style={{
        width: '560px',
        maxWidth: '92vw',
        maxHeight: '90vh',
        overflowY: 'auto',
        border: '1px solid rgba(239, 68, 68, 0.4)',
        boxShadow: '0 20px 40px rgba(0,0,0,0.6)',
        padding: '24px'
      }}>
        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              background: 'rgba(239, 68, 68, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              border: '1px solid rgba(239, 68, 68, 0.3)'
            }}>
              <Trash2 size={22} style={{ color: '#ef4444' }} />
            </div>
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-main)' }}>
                Eliminar Fuente de Intake
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Gestión de higiene documental, persistencia en disco y base de datos
              </p>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            style={{ padding: '4px', borderRadius: '50%' }}
            onClick={onClose}
            disabled={isDeleting}
          >
            <X size={18} />
          </button>
        </div>

        {/* Info del Documento */}
        <div style={{
          background: 'var(--bg-sidebar)',
          border: '1px solid var(--border-subtle)',
          borderRadius: '8px',
          padding: '14px',
          marginBottom: '16px'
        }}>
          <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
            {source.title}
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
            <span>Disciplina: <strong>{source.discipline}</strong></span>
            <span>•</span>
            <span>Tipo: <strong>{source.source_type}</strong></span>
            <span>•</span>
            <span>Origen: <strong>{source.source_origin}</strong></span>
          </div>

          {/* Archivo adjunto */}
          {source.file_path && (
            <div style={{
              marginTop: '10px',
              padding: '8px 10px',
              background: 'rgba(59, 130, 246, 0.08)',
              border: '1px solid rgba(59, 130, 246, 0.25)',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '12px'
            }}>
              <HardDrive size={15} style={{ color: '#60a5fa' }} />
              <div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                <span style={{ color: '#93c5fd', fontWeight: 500 }}>
                  {source.original_filename || 'Archivo en volumen'}
                </span>
                <span style={{ color: 'var(--text-dim)', marginLeft: '6px' }}>
                  ({formatBytes(source.file_size_bytes)})
                </span>
              </div>
            </div>
          )}
        </div>

        {/* Estado de Dependencias */}
        {loadingDeps ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-muted)' }}>
            <RefreshCw size={20} className="animate-spin" style={{ margin: '0 auto 8px auto' }} />
            <div style={{ fontSize: '12px' }}>Analizando dependencias en extracciones y reglas...</div>
          </div>
        ) : (
          <div style={{ marginBottom: '18px' }}>
            {hasDependencies ? (
              <div style={{
                background: 'rgba(245, 158, 11, 0.1)',
                border: '1px solid rgba(245, 158, 11, 0.3)',
                borderRadius: '8px',
                padding: '12px 14px',
                marginBottom: '14px'
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#fbbf24', fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>
                  <AlertTriangle size={16} />
                  <span>Atención: Fuente con dependencias vinculadas</span>
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', lineHeight: '1.5' }}>
                  Esta fuente ya ha sido procesada previamente:
                  <ul style={{ margin: '4px 0 0 16px', padding: 0 }}>
                    {dependencies?.extractions_count ? (
                      <li>{dependencies.extractions_count} sesión(es) de extracción estructurada</li>
                    ) : null}
                    {dependencies?.rule_documents_count ? (
                      <li>{dependencies.rule_documents_count} documento(s) en el Motor de Reglas QA/QC</li>
                    ) : null}
                  </ul>
                </div>
              </div>
            ) : (
              <div style={{
                background: 'rgba(16, 185, 129, 0.1)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                borderRadius: '8px',
                padding: '10px 14px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: '#34d399',
                fontSize: '12px',
                marginBottom: '14px'
              }}>
                <CheckCircle2 size={16} />
                <span>Sin procesamiento ni reglas dependientes. Eliminación segura.</span>
              </div>
            )}

            {/* Selector de Modo de Eliminación */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <label style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '10px 12px',
                borderRadius: '8px',
                background: !hardDelete ? 'rgba(59, 130, 246, 0.1)' : 'var(--bg-sidebar)',
                border: `1px solid ${!hardDelete ? 'rgba(59, 130, 246, 0.4)' : 'var(--border-subtle)'}`,
                cursor: 'pointer'
              }}>
                <input
                  type="radio"
                  name="deleteMode"
                  checked={!hardDelete}
                  onChange={() => setHardDelete(false)}
                  style={{ marginTop: '3px' }}
                />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Archive size={14} style={{ color: '#60a5fa' }} />
                    <span>Archivar / Soft-Delete (Recomendado)</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Oculta la fuente del listado operativo pero preserva la trazabilidad de extracciones y reglas ya aprobadas.
                  </div>
                </div>
              </label>

              <label style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: '10px',
                padding: '10px 12px',
                borderRadius: '8px',
                background: hardDelete ? 'rgba(239, 68, 68, 0.1)' : 'var(--bg-sidebar)',
                border: `1px solid ${hardDelete ? 'rgba(239, 68, 68, 0.4)' : 'var(--border-subtle)'}`,
                cursor: 'pointer'
              }}>
                <input
                  type="radio"
                  name="deleteMode"
                  checked={hardDelete}
                  onChange={() => setHardDelete(true)}
                  style={{ marginTop: '3px' }}
                />
                <div>
                  <div style={{ fontSize: '13px', fontWeight: 600, color: '#f87171', display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Trash2 size={14} style={{ color: '#f87171' }} />
                    <span>Eliminar permanentemente (Hard-Delete)</span>
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    Elimina completamente el registro de la base de datos y borra físicamente el archivo del disco y volumen.
                  </div>
                </div>
              </label>
            </div>
          </div>
        )}

        {/* Error Alert */}
        {errorMsg && (
          <div style={{
            padding: '10px 12px',
            background: 'rgba(239, 68, 68, 0.15)',
            border: '1px solid rgba(239, 68, 68, 0.4)',
            borderRadius: '6px',
            color: '#f87171',
            fontSize: '12px',
            marginBottom: '16px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}>
            <AlertCircle size={15} />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Action Buttons */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '8px' }}>
          <button
            className="btn btn-secondary"
            onClick={onClose}
            disabled={isDeleting}
            style={{ padding: '8px 16px', fontSize: '13px' }}
          >
            Cancelar
          </button>
          <button
            className="btn btn-primary"
            onClick={handleConfirmDelete}
            disabled={isDeleting || loadingDeps}
            style={{
              padding: '8px 18px',
              fontSize: '13px',
              background: hardDelete ? 'var(--danger, #ef4444)' : '#3b82f6',
              borderColor: hardDelete ? '#dc2626' : '#2563eb'
            }}
          >
            {isDeleting ? (
              <>
                <RefreshCw size={14} className="animate-spin" />
                <span>Eliminando...</span>
              </>
            ) : hardDelete ? (
              <>
                <Trash2 size={14} />
                <span>Eliminar Definitivamente</span>
              </>
            ) : (
              <>
                <Archive size={14} />
                <span>Archivar Fuente</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};
