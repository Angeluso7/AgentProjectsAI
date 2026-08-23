import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { ReviewPipelineRunItem, PipelineStageRunItem, DocumentItem } from '../types';
import {
  Play, RefreshCw, XCircle, CheckCircle2, AlertTriangle, Clock,
  FileText, ShieldCheck, Layers, Sparkles, FileArchive, Hash, ChevronRight
} from 'lucide-react';

const STAGE_LABELS: Record<string, { label: string; icon: any }> = {
  ingest: { label: '1. Ingesta & Raster', icon: Layers },
  ocr: { label: '2. OCR Espacial', icon: FileText },
  layout: { label: '3. Layout Macro', icon: Layers },
  title_block: { label: '4. Viñeta / Title Block', icon: Sparkles },
  tables: { label: '5. Extracción Tablas', icon: FileText },
  symbols: { label: '6. Detección Símbolos', icon: Sparkles },
  rules: { label: '7. Reglas QA/QC', icon: ShieldCheck },
  reports: { label: '8. Reporte & Bundle', icon: FileArchive }
};

export const PipelinePage: React.FC = () => {
  const [pipelines, setPipelines] = useState<ReviewPipelineRunItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedPipeline, setSelectedPipeline] = useState<ReviewPipelineRunItem | null>(null);
  const [stages, setStages] = useState<PipelineStageRunItem[]>([]);
  
  const [targetDocId, setTargetDocId] = useState<string>('');
  const [forceReprocess, setForceReprocess] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(true);
  const [triggering, setTriggering] = useState<boolean>(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [pipes, docs] = await Promise.all([
        apiService.getPipelines(),
        apiService.getDocuments()
      ]);
      setPipelines(pipes);
      setDocuments(docs);
      if (docs.length > 0) {
        setTargetDocId(docs[0].id);
      }
      if (pipes.length > 0) {
        handleSelectPipeline(pipes[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectPipeline = async (pipe: ReviewPipelineRunItem) => {
    setSelectedPipeline(pipe);
    try {
      const stgs = await apiService.getPipelineStages(pipe.id);
      setStages(stgs);
    } catch (e) {
      console.error(e);
      setStages([]);
    }
  };

  const handleRunPipeline = async () => {
    if (!targetDocId) return;
    try {
      setTriggering(true);
      await apiService.runDocumentPipelineAsync(targetDocId, forceReprocess, 'auditor_lead');
      await loadData();
      alert('Pipeline One-Click Review iniciado con éxito en modo asíncrono.');
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al iniciar pipeline.');
    } finally {
      setTriggering(false);
    }
  };

  const handleRetry = async (pipelineId: string) => {
    try {
      await apiService.retryPipeline(pipelineId);
      await loadData();
      alert('Reintento del pipeline ejecutado.');
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al reintentar pipeline.');
    }
  };

  const handleCancel = async (pipelineId: string) => {
    try {
      await apiService.cancelPipeline(pipelineId);
      await loadData();
      alert('Pipeline cancelado.');
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al cancelar pipeline.');
    }
  };

  return (
    <div className="page-container">
      {/* Header & Acción Principal One-Click */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={26} style={{ color: 'var(--primary)' }} />
            One-Click Project Review (Pipeline End-to-End)
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Orquestación integral y auditable: Ingesta → OCR → Layout → Viñeta → Tablas → Símbolos → Reglas QA/QC → Reporte & Bundle.
          </p>
        </div>

        {/* Formulario de Lanzamiento One-Click */}
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', background: 'var(--bg-card)', padding: '10px 14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
          <select
            value={targetDocId}
            onChange={(e) => setTargetDocId(e.target.value)}
            style={{
              background: 'var(--bg-sidebar)',
              color: 'var(--text-main)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '8px',
              padding: '6px 12px',
              fontSize: '13px'
            }}
          >
            {documents.map((doc) => (
              <option key={doc.id} value={doc.id}>
                {doc.filename} ({(doc as any).total_pages || doc.page_count || doc.sheets?.length || 1} pág)
              </option>
            ))}
          </select>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', cursor: 'pointer', color: 'var(--text-muted)' }}>
            <input
              type="checkbox"
              checked={forceReprocess}
              onChange={(e) => setForceReprocess(e.target.checked)}
            />
            Forzar reproceso
          </label>

          <button
            className="btn btn-primary"
            onClick={handleRunPipeline}
            disabled={triggering || !targetDocId}
            style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px', fontWeight: 700 }}
          >
            <Play size={15} className={triggering ? 'animate-spin' : ''} />
            <span>{triggering ? 'Iniciando...' : 'Iniciar One-Click Review'}</span>
          </button>
        </div>
      </div>

      {/* Grid Principal */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 500px', gap: '20px' }}>
        
        {/* Historial de Pipeline Runs */}
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700 }}>
              Corridas de Auditoría Integral ({pipelines.length})
            </h2>
            <button className="btn btn-secondary" onClick={loadData} style={{ padding: '4px 8px', fontSize: '11px' }}>
              <RefreshCw size={12} /> Refrescar
            </button>
          </div>

          {pipelines.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
              <Sparkles size={36} style={{ margin: '0 auto 10px', opacity: 0.4 }} />
              <div>No hay corridas de pipeline registradas. Inicie una arriba.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {pipelines.map((p) => {
                const isSelected = selectedPipeline?.id === p.id;
                let badgeClass = 'badge-neutral';
                if (p.status === 'completed') badgeClass = 'badge-success';
                else if (p.status === 'running') badgeClass = 'badge-info';
                else if (p.status === 'failed') badgeClass = 'badge-danger';
                else if (p.status === 'awaiting_review') badgeClass = 'badge-warning';

                return (
                  <div
                    key={p.id}
                    onClick={() => handleSelectPipeline(p)}
                    style={{
                      border: `1px solid ${isSelected ? 'var(--primary)' : 'var(--border-subtle)'}`,
                      background: isSelected ? 'rgba(56, 189, 248, 0.05)' : 'var(--bg-sidebar)',
                      padding: '12px',
                      borderRadius: '8px',
                      cursor: 'pointer',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px'
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontWeight: 700, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <span>Pipeline {p.scope_type.toUpperCase()}</span>
                        <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                          ID: {p.id.substring(0, 8)}...
                        </span>
                      </div>
                      <span className={`badge ${badgeClass}`} style={{ textTransform: 'uppercase', fontSize: '10px' }}>
                        {p.status}
                      </span>
                    </div>

                    {/* Barra de Progreso */}
                    <div style={{ background: 'rgba(255,255,255,0.05)', borderRadius: '4px', height: '6px', overflow: 'hidden' }}>
                      <div
                        style={{
                          width: `${p.progress_percent}%`,
                          height: '100%',
                          background: p.status === 'failed' ? 'var(--danger)' : 'var(--primary)',
                          transition: 'width 0.3s ease'
                        }}
                      />
                    </div>

                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-dim)' }}>
                      <span>Etapa: <strong>{p.current_stage}</strong> ({p.progress_percent}%)</span>
                      <span>{p.created_at ? new Date(p.created_at).toLocaleTimeString() : ''}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Panel Detallado: Stepper de las 8 Etapas */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Layers size={16} style={{ color: 'var(--primary)' }} />
            Progreso de Etapas del Pipeline
          </h2>

          {selectedPipeline ? (
            <div>
              {/* Acciones de Control */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', background: 'var(--bg-sidebar)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ fontSize: '12px' }}>
                  <strong>Estado:</strong> <span style={{ textTransform: 'uppercase' }}>{selectedPipeline.status}</span>
                </div>
                <div style={{ display: 'flex', gap: '6px' }}>
                  {selectedPipeline.status === 'running' && (
                    <button className="btn btn-secondary" onClick={() => handleCancel(selectedPipeline.id)} style={{ padding: '4px 8px', fontSize: '11px' }}>
                      <XCircle size={12} /> Cancelar
                    </button>
                  )}
                  {selectedPipeline.status !== 'running' && (
                    <button className="btn btn-secondary" onClick={() => handleRetry(selectedPipeline.id)} style={{ padding: '4px 8px', fontSize: '11px' }}>
                      <RefreshCw size={12} /> Reintentar
                    </button>
                  )}
                  {selectedPipeline.final_report_id && (
                    <a
                      href={apiService.getReportDownloadPdfUrl(selectedPipeline.final_report_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="btn btn-primary"
                      style={{ padding: '4px 8px', fontSize: '11px' }}
                    >
                      <FileText size={12} /> Ver Reporte PDF
                    </a>
                  )}
                </div>
              </div>

              {/* Stepper de 8 Etapas */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {stages.map((stg) => {
                  const meta = STAGE_LABELS[stg.stage_name] || { label: stg.stage_name, icon: Layers };
                  const Icon = meta.icon;
                  let stgColor = 'var(--text-dim)';
                  if (stg.status === 'completed') stgColor = 'var(--success)';
                  else if (stg.status === 'running') stgColor = 'var(--primary)';
                  else if (stg.status === 'failed') stgColor = 'var(--danger)';

                  return (
                    <div
                      key={stg.id}
                      style={{
                        background: 'var(--bg-sidebar)',
                        padding: '10px 12px',
                        borderRadius: '6px',
                        border: '1px solid var(--border-subtle)',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        fontSize: '12px'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <Icon size={16} style={{ color: stgColor }} />
                        <span style={{ fontWeight: 600, color: 'var(--text-main)' }}>{meta.label}</span>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span className="badge badge-neutral" style={{ fontSize: '10px', textTransform: 'uppercase' }}>
                          {stg.status}
                        </span>
                        {stg.status === 'completed' && <CheckCircle2 size={14} style={{ color: 'var(--success)' }} />}
                        {stg.status === 'failed' && <AlertTriangle size={14} style={{ color: 'var(--danger)' }} />}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ color: 'var(--text-dim)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>
              Seleccione una corrida para ver el detalle de sus etapas.
            </div>
          )}
        </div>

      </div>
    </div>
  );
};
