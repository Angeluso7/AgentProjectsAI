import React, { useEffect, useState } from 'react';
import {
  Play, RefreshCw, XCircle, AlertCircle, Clock, CheckCircle2,
  Filter, Layers, Terminal, ChevronRight, Activity
} from 'lucide-react';
import { apiService } from '../services/api';
import { ProcessingJobItem, JobEventItem, JobStatus } from '../types';

export const JobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<ProcessingJobItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [selectedJob, setSelectedJob] = useState<ProcessingJobItem | null>(null);
  const [events, setEvents] = useState<JobEventItem[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(false);

  useEffect(() => {
    loadJobs();
  }, [statusFilter, typeFilter]);

  const loadJobs = async () => {
    try {
      setLoading(true);
      const data = await apiService.getJobs({
        status: statusFilter || undefined,
        job_type: typeFilter || undefined,
      });
      setJobs(data);
      if (selectedJob) {
        const updated = data.find((j) => j.id === selectedJob.id);
        if (updated) setSelectedJob(updated);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectJob = async (job: ProcessingJobItem) => {
    setSelectedJob(job);
    try {
      setLoadingEvents(true);
      const evList = await apiService.getJobEvents(job.id);
      setEvents(evList);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingEvents(false);
    }
  };

  const handleRetry = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiService.retryJob(jobId);
      alert('Reintento de job solicitado exitosamente.');
      loadJobs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al reintentar job.');
    }
  };

  const handleCancel = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await apiService.cancelJob(jobId);
      alert('Cancelación solicitada exitosamente.');
      loadJobs();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al cancelar job.');
    }
  };

  const getStatusBadge = (st: JobStatus) => {
    switch (st) {
      case 'completed':
        return <span className="badge badge-success">✓ Completed</span>;
      case 'failed':
        return <span className="badge badge-critical">✕ Failed</span>;
      case 'running':
        return <span className="badge badge-info">● Running ({st})</span>;
      case 'retrying':
        return <span className="badge badge-medium">⟳ Retrying</span>;
      case 'cancelled':
        return <span className="badge badge-low">⊘ Cancelled</span>;
      default:
        return <span className="badge badge-medium">⏳ Queued</span>;
    }
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Jobs & Procesos Asíncronos</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Monitoreo, trazabilidad de eventos, reintentos con backoff y auditoría de pipelines pesados.
          </p>
        </div>

        <button className="btn btn-secondary" onClick={loadJobs}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Actualizar</span>
        </button>
      </div>

      {/* Barra de Filtros */}
      <div className="card" style={{ marginBottom: '20px', display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Filter size={16} color="var(--text-dim)" />
          <span style={{ fontSize: '13px', fontWeight: 600 }}>Filtros:</span>
        </div>

        <div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
          >
            <option value="">Todos los estados</option>
            <option value="queued">Queued</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="retrying">Retrying</option>
            <option value="cancelled">Cancelled</option>
          </select>
        </div>

        <div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
          >
            <option value="">Todos los tipos</option>
            <option value="sheet_ocr">sheet_ocr</option>
            <option value="document_ocr">document_ocr</option>
            <option value="sheet_layout">sheet_layout</option>
            <option value="document_layout">document_layout</option>
            <option value="title_block_match">title_block_match</option>
            <option value="source_ingest">source_ingest</option>
          </select>
        </div>
      </div>

      {/* Grid Principal: Lista de Jobs + Detalle de Eventos */}
      <div style={{ display: 'grid', gridTemplateColumns: selectedJob ? '1.8fr 1.2fr' : '1fr', gap: '20px' }}>
        {/* Tabla de Jobs */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px 16px' }}>Job ID / Tipo</th>
                <th style={{ padding: '12px 16px' }}>Target</th>
                <th style={{ padding: '12px 16px' }}>Estado</th>
                <th style={{ padding: '12px 16px' }}>Progreso</th>
                <th style={{ padding: '12px 16px' }}>Reintentos</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {jobs.length > 0 ? (
                jobs.map((j) => {
                  const isSelected = selectedJob?.id === j.id;
                  return (
                    <tr
                      key={j.id}
                      onClick={() => handleSelectJob(j)}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                    >
                      <td style={{ padding: '12px 16px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{j.job_type}</div>
                        <div className="font-mono" style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                          {j.id.slice(0, 8)}...
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        <span className="badge badge-medium">{j.target_type}</span>
                        <div className="font-mono" style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                          {j.target_id.slice(0, 8)}...
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px' }}>
                        {getStatusBadge(j.status)}
                      </td>
                      <td style={{ padding: '12px 16px', width: '130px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <div style={{ flex: 1, height: '6px', background: 'var(--bg-sidebar)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ width: `${j.progress_percent}%`, height: '100%', background: j.status === 'failed' ? 'var(--danger)' : 'var(--primary)' }} />
                          </div>
                          <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>{j.progress_percent}%</span>
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '2px' }}>
                          {j.current_stage}
                        </div>
                      </td>
                      <td style={{ padding: '12px 16px', color: 'var(--text-muted)' }}>
                        {j.retry_count} / {j.max_retries}
                      </td>
                      <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                          {(j.status === 'failed' || j.status === 'cancelled') && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '11px' }}
                              onClick={(e) => handleRetry(j.id, e)}
                              title="Reintentar job"
                            >
                              <RefreshCw size={12} />
                              <span>Retry</span>
                            </button>
                          )}
                          {(j.status === 'queued' || j.status === 'running') && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '11px', color: 'var(--danger)' }}
                              onClick={(e) => handleCancel(j.id, e)}
                              title="Cancelar job"
                            >
                              <XCircle size={12} />
                              <span>Cancel</span>
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })
              ) : (
                <tr>
                  <td colSpan={6} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
                    No se encontraron jobs registrados.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Panel Lateral: Detalle del Job & Eventos */}
        {selectedJob && (
          <div className="card" style={{ height: '600px', overflowY: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px' }}>
              <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Detalle de Ejecución</h2>
              <button className="btn btn-secondary" style={{ padding: '2px 6px', fontSize: '11px' }} onClick={() => setSelectedJob(null)}>
                Cerrar
              </button>
            </div>

            <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '12px', lineHeight: '1.7', marginBottom: '16px' }}>
              <div><strong>Job ID:</strong> <span className="font-mono">{selectedJob.id}</span></div>
              <div><strong>Tipo:</strong> <span className="badge badge-medium">{selectedJob.job_type}</span></div>
              <div><strong>Pipeline:</strong> {selectedJob.pipeline_name} ({selectedJob.pipeline_version})</div>
              <div><strong>Encolado:</strong> {new Date(selectedJob.queued_at).toLocaleTimeString()}</div>
              {selectedJob.started_at && <div><strong>Iniciado:</strong> {new Date(selectedJob.started_at).toLocaleTimeString()}</div>}
              {selectedJob.completed_at && <div><strong>Completado:</strong> {new Date(selectedJob.completed_at).toLocaleTimeString()}</div>}
              {selectedJob.error_message && (
                <div style={{ marginTop: '8px', color: 'var(--danger)', background: 'rgba(239, 68, 68, 0.1)', padding: '8px', borderRadius: '6px' }}>
                  <strong>Error ({selectedJob.error_code}):</strong>
                  <pre style={{ fontSize: '11px', whiteSpace: 'pre-wrap', marginTop: '4px' }}>{selectedJob.error_message}</pre>
                </div>
              )}
            </div>

            {/* Eventos del Job */}
            <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '8px' }}>Historial de Eventos ({events.length})</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {events.map((ev) => (
                <div key={ev.id} style={{ background: 'var(--bg-sidebar)', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--text-muted)' }}>
                    <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{ev.event_type.toUpperCase()}</span>
                    <span style={{ fontSize: '10px' }}>{new Date(ev.created_at).toLocaleTimeString()}</span>
                  </div>
                  <div style={{ marginTop: '2px', color: 'var(--text-main)' }}>{ev.message || ev.stage}</div>
                  <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '2px' }}>
                    Actor: {ev.actor_type} {ev.stage && `• Etapa: ${ev.stage}`}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
