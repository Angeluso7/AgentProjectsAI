import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { ReviewTaskItem, ReviewRun } from '../types';
import {
  CheckCircle2, XCircle, AlertTriangle, Send, Play, Sparkles,
  ClipboardList, Edit3, ShieldAlert, SquareCheck, RefreshCw, Layers
} from 'lucide-react';
import { ObservationsPanel } from '../components/ObservationsPanel';
import { AssistantCopilotDrawer } from '../components/AssistantCopilotDrawer';

export const ReviewPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'observations' | 'tasks' | 'runs'>('observations');
  const [tasks, setTasks] = useState<ReviewTaskItem[]>([]);
  const [selectedTask, setSelectedTask] = useState<ReviewTaskItem | null>(null);
  const [runs, setRuns] = useState<ReviewRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<ReviewRun | null>(null);
  const [loading, setLoading] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [copilotTaskType, setCopilotTaskType] = useState<any>('review_support');
  const [copilotContext, setCopilotContext] = useState<any>({});

  // Formulario de Corrección Humana
  const [correctedText, setCorrectedText] = useState('');
  const [reviewNotes, setReviewNotes] = useState('');
  const [reviewerName, setReviewerName] = useState('auditor_senior_1');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, [activeSubTab]);

  const loadData = async () => {
    try {
      setLoading(true);
      if (activeSubTab === 'tasks') {
        const tList = await apiService.getReviewTasks();
        setTasks(tList);
        if (tList.length > 0) setSelectedTask(tList[0]);
      } else if (activeSubTab === 'runs') {
        const rList = await apiService.getReviewRuns();
        setRuns(rList);
        if (rList.length > 0) setSelectedRun(rList[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenCopilot = (type: string, ctx: any = {}) => {
    setCopilotTaskType(type);
    setCopilotContext(ctx);
    setIsCopilotOpen(true);
  };

  const handleDecision = async (decision: 'approved' | 'corrected' | 'rejected') => {
    if (!selectedTask) return;
    try {
      setSubmitting(true);
      let correctedVal = undefined;
      if (decision === 'corrected') {
        correctedVal = {
          user_correction: correctedText || 'Valor ajustado por auditor',
          original_payload: selectedTask.payload
        };
      }

      await apiService.submitReviewDecision(selectedTask.id, {
        decision,
        corrected_value: correctedVal,
        reviewer: reviewerName,
        notes: reviewNotes,
        reason_code: selectedTask.reason_code
      });

      alert(`Decisión registrada: ${decision.toUpperCase()}. Valor original preservado.`);
      setCorrectedText('');
      setReviewNotes('');
      loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al registrar decisión.');
    } finally {
      setSubmitting(false);
    }
  };

  const getPriorityBadge = (p: string) => {
    switch (p) {
      case 'critical':
      case 'high':
        return <span className="badge badge-critical">ALTA ({p})</span>;
      case 'low':
        return <span className="badge badge-low">BAJA</span>;
      default:
        return <span className="badge badge-medium">MEDIA</span>;
    }
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '8px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800 }}>Triage, Observaciones & Revisión Humana (HITL)</h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Gestión formal de Observaciones Técnicas (OBS), Solicitudes de Información (RFI), Bloqueos (BLK) y Re-evaluación Delta.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          {/* Selector de Sub-pestaña */}
          <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-card)', padding: '4px 8px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              className={`btn ${activeSubTab === 'observations' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setActiveSubTab('observations')}
            >
              <ShieldAlert size={14} /> Observaciones & RFIs
            </button>
            <button
              className={`btn ${activeSubTab === 'tasks' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setActiveSubTab('tasks')}
            >
              <ClipboardList size={14} /> Cola de Tareas HITL ({tasks.filter(t => t.status === 'open').length})
            </button>
            <button
              className={`btn ${activeSubTab === 'runs' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setActiveSubTab('runs')}
            >
              <Sparkles size={14} /> Corridas QA/QC ({runs.length})
            </button>
          </div>

          <button
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, background: 'linear-gradient(135deg, var(--primary), var(--accent))' }}
            onClick={() => handleOpenCopilot('review_support', { activeTab: activeSubTab })}
          >
            <Sparkles size={16} /> Asistente de Auditoría
          </button>
        </div>
      </div>

      <AssistantCopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        initialTaskType={copilotTaskType}
        contextData={copilotContext}
      />

      {activeSubTab === 'observations' ? (
        <ObservationsPanel />
      ) : activeSubTab === 'tasks' ? (
        <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.8fr', gap: '20px' }}>
          {/* Lista de Tareas de Revisión */}
          <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px', background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 700, fontSize: '14px' }}>Tareas Pendientes ({tasks.length})</span>
              <button className="btn btn-secondary" style={{ padding: '2px 6px', fontSize: '11px' }} onClick={loadData}>
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
              </button>
            </div>

            <div style={{ maxHeight: '600px', overflowY: 'auto' }}>
              {tasks.length > 0 ? (
                tasks.map((t) => {
                  const isSelected = selectedTask?.id === t.id;
                  return (
                    <div
                      key={t.id}
                      onClick={() => setSelectedTask(t)}
                      style={{
                        padding: '14px 16px',
                        borderBottom: '1px solid var(--border-subtle)',
                        background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                        cursor: 'pointer',
                        transition: 'background 0.15s',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-main)' }}>{t.task_type}</span>
                        {getPriorityBadge(t.priority)}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                        {t.reason_message}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '6px', fontSize: '11px', color: 'var(--text-dim)' }}>
                        <span>Razón: <code style={{ color: 'var(--primary)' }}>{t.reason_code}</code></span>
                        <span>{new Date(t.created_at).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  );
                })
              ) : (
                <div style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '13px' }}>
                  No hay tareas pendientes en la cola de revisión.
                </div>
              )}
            </div>
          </div>

          {/* Panel de Decisión y Corrección Humana */}
          {selectedTask ? (
            <div className="card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Inspección & Decisión de Auditor</h2>
                <span className={`badge ${selectedTask.status === 'open' ? 'badge-medium' : 'badge-success'}`}>
                  {selectedTask.status.toUpperCase()}
                </span>
              </div>

              <div style={{ background: 'var(--bg-sidebar)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '13px', lineHeight: '1.7', marginBottom: '16px' }}>
                <div><strong>Tipo de Tarea:</strong> <span className="badge badge-medium">{selectedTask.task_type}</span></div>
                <div><strong>Causa:</strong> {selectedTask.reason_message}</div>
                {selectedTask.confidence !== null && selectedTask.confidence !== undefined && (
                  <div><strong>Confianza Detectada:</strong> <span style={{ color: 'var(--primary)', fontWeight: 600 }}>{(selectedTask.confidence * 100).toFixed(1)}%</span></div>
                )}
                <div style={{ marginTop: '8px' }}>
                  <strong>Valor Original / Payload:</strong>
                  <pre style={{ fontSize: '11px', background: 'var(--bg-card)', padding: '8px', borderRadius: '6px', marginTop: '4px', overflowX: 'auto' }}>
                    {JSON.stringify(selectedTask.payload, null, 2)}
                  </pre>
                </div>
              </div>

              {/* Formulario de Acción */}
              {selectedTask.status === 'open' ? (
                <div>
                  <div style={{ marginBottom: '12px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Valor Corregido (si aplica):</label>
                    <input
                      type="text"
                      placeholder="ej: Escala corregida: 1:50"
                      value={correctedText}
                      onChange={(e) => setCorrectedText(e.target.value)}
                      style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                    />
                  </div>

                  <div style={{ marginBottom: '16px' }}>
                    <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Notas de Auditoría Técnica:</label>
                    <textarea
                      rows={2}
                      placeholder="Observaciones de la validación..."
                      value={reviewNotes}
                      onChange={(e) => setReviewNotes(e.target.value)}
                      style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                    />
                  </div>

                  <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                    <button
                      className="btn btn-primary"
                      style={{ background: 'var(--success)' }}
                      onClick={() => handleDecision('approved')}
                      disabled={submitting}
                    >
                      <CheckCircle2 size={15} /> 1. Aprobar Original
                    </button>

                    <button
                      className="btn btn-primary"
                      onClick={() => handleDecision('corrected')}
                      disabled={submitting}
                    >
                      <Edit3 size={15} /> 2. Guardar Corrección
                    </button>

                    <button
                      className="btn btn-secondary"
                      style={{ color: 'var(--danger)', borderColor: 'var(--danger)' }}
                      onClick={() => handleDecision('rejected')}
                      disabled={submitting}
                    >
                      <XCircle size={15} /> 3. Rechazar
                    </button>
                  </div>
                </div>
              ) : (
                <div style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--success)', padding: '12px', borderRadius: '6px', fontSize: '13px' }}>
                  ✓ Esta tarea ya fue resuelta como <strong>{selectedTask.status}</strong>. El historial y las trazas han sido persistidos.
                </div>
              )}
            </div>
          ) : (
            <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-dim)' }}>
              Selecciona una tarea de la cola para inspeccionar.
            </div>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '24px' }}>
          {/* Corridas QA/QC */}
          <div className="card">
            <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '14px' }}>Sesiones de Auditoría</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {runs.map((r) => (
                <div
                  key={r.id}
                  onClick={() => setSelectedRun(r)}
                  style={{
                    padding: '12px',
                    borderRadius: '8px',
                    border: `1px solid ${selectedRun?.id === r.id ? 'var(--primary)' : 'var(--border-subtle)'}`,
                    background: selectedRun?.id === r.id ? 'rgba(56, 189, 248, 0.15)' : 'var(--bg-sidebar)',
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ fontWeight: 600, fontSize: '14px' }}>{r.run_name}</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-dim)', marginTop: '2px' }}>
                    {r.findings_count} Hallazgos • {new Date(r.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="card">
            <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>
              Detalle de Auditoría ({selectedRun?.run_name || 'Selecciona una corrida'})
            </h2>
            <div style={{ color: 'var(--text-muted)', fontSize: '13px' }}>
              {selectedRun ? `Reglas aplicadas: ${selectedRun.rules_applied_count} • Tiempo de ejecución: ${selectedRun.execution_time_sec}s` : 'Sin selección.'}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
