import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles, Bot, Zap, ShieldCheck, AlertTriangle, CheckCircle2,
  XCircle, ChevronDown, ChevronUp, Database, ArrowRight, CornerDownRight,
  BookOpen, Layers, SquareCheck, FileText, Send, Edit3, X, History, ExternalLink
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  AssistantTaskType,
  AssistantExecutionResponseDTO,
  AssistantInteractionItemDTO,
  AssistantTaskCatalogItemDTO,
  KnowledgeSearchResultItemDTO
} from '../types';

interface AssistantCopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  initialTaskType?: AssistantTaskType;
  initialPrompt?: string;
  contextData?: Record<string, any>;
  projectId?: string;
  stage?: string;
  discipline?: string;
  onApplySuggestion?: (structuredOutput: any) => void;
}

const DarkSelect = ({ value, onChange, options, style, disabled = false }: any) => {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleOutsideClick);
    }
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [isOpen]);

  const selectedOption = options.find((o: any) => String(o.value) === String(value)) || options[0] || { label: 'Seleccionar...' };

  return (
    <div ref={containerRef} style={{ position: 'relative', width: '100%', ...style }}>
      <div 
        onClick={() => !disabled && setIsOpen(!isOpen)}
        style={{
          background: '#090d16',
          color: '#f8fafc',
          border: '1px solid #334155',
          borderRadius: '6px',
          padding: '9px 12px',
          cursor: disabled ? 'not-allowed' : 'pointer',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: 'inherit',
          opacity: disabled ? 0.6 : 1,
          outline: isOpen ? '2px solid #38bdf8' : 'none',
          userSelect: 'none'
        }}
      >
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontWeight: 500 }}>
          {selectedOption.label}
        </span>
        <ChevronDown size={14} style={{ flexShrink: 0, marginLeft: '8px', transform: isOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s', color: '#94a3b8' }} />
      </div>
      
      {isOpen && (
        <div style={{
          position: 'absolute',
          top: '100%',
          left: 0,
          right: 0,
          marginTop: '4px',
          background: '#090d16',
          border: '1px solid #334155',
          borderRadius: '6px',
          boxShadow: '0 8px 24px rgba(0,0,0,0.85)',
          zIndex: 1000,
          maxHeight: '240px',
          overflowY: 'auto'
        }}>
          {options.map((opt: any) => {
            const isSelected = String(opt.value) === String(value);
            return (
              <div
                key={opt.value}
                onClick={() => {
                  onChange(opt.value);
                  setIsOpen(false);
                }}
                style={{
                  padding: '9px 12px',
                  cursor: 'pointer',
                  background: isSelected ? '#1e293b' : 'transparent',
                  color: isSelected ? '#38bdf8' : '#f8fafc',
                  fontSize: 'inherit',
                  display: 'flex',
                  alignItems: 'center',
                  fontWeight: isSelected ? 600 : 400,
                  borderBottom: '1px solid #172033'
                }}
                onMouseEnter={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = '#131d33';
                    e.currentTarget.style.color = '#ffffff';
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isSelected) {
                    e.currentTarget.style.background = 'transparent';
                    e.currentTarget.style.color = '#f8fafc';
                  }
                }}
              >
                {opt.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export const AssistantCopilotDrawer: React.FC<AssistantCopilotDrawerProps> = ({
  isOpen,
  onClose,
  initialTaskType = 'normative_query',
  initialPrompt = '',
  contextData = {},
  projectId,
  stage,
  discipline,
  onApplySuggestion
}) => {
  const [activeTab, setActiveTab] = useState<'assistant' | 'history'>('assistant');
  const [taskType, setTaskType] = useState<AssistantTaskType>(initialTaskType);
  const [prompt, setPrompt] = useState(initialPrompt);
  const [forceTier, setForceTier] = useState<number | undefined>(undefined);
  const [allowEscalation, setAllowEscalation] = useState(true);
  const [loading, setLoading] = useState(false);

  // Resultado actual
  const [result, setResult] = useState<AssistantExecutionResponseDTO | null>(null);
  const [feedbackNotes, setFeedbackNotes] = useState('');
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [editedResponse, setEditedResponse] = useState('');

  // Catálogo de tareas e Historial
  const [tasksCatalog, setTasksCatalog] = useState<AssistantTaskCatalogItemDTO[]>([]);
  const [interactions, setInteractions] = useState<AssistantInteractionItemDTO[]>([]);
  const [expandedSourceId, setExpandedSourceId] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadCatalog();
      if (initialTaskType) setTaskType(initialTaskType);
      if (initialPrompt) setPrompt(initialPrompt);
      setResult(null);
      setFeedbackSent(false);
    }
  }, [isOpen, initialTaskType, initialPrompt]);

  useEffect(() => {
    if (activeTab === 'history') {
      loadHistory();
    }
  }, [activeTab]);

  const loadCatalog = async () => {
    try {
      const cat = await apiService.getAssistantTasks();
      setTasksCatalog(cat);
    } catch (e) {
      console.error('Error cargando catálogo de tareas:', e);
    }
  };

  const loadHistory = async () => {
    try {
      const hist = await apiService.getAssistantInteractions({ project_id: projectId, limit: 30 });
      setInteractions(hist);
    } catch (e) {
      console.error('Error cargando historial de interacciones:', e);
    }
  };

  const handleExecute = async () => {
    if (!prompt.trim()) return;
    try {
      setLoading(true);
      setResult(null);
      setFeedbackSent(false);
      setIsEditing(false);

      const resp = await apiService.executeAssistantTask({
        task_type: taskType,
        prompt: prompt.trim(),
        project_id: projectId,
        stage: stage || 'Ingeniería Básica',
        discipline: discipline || 'general',
        context_data: contextData,
        force_tier: forceTier,
        allow_escalation: allowEscalation
      });

      setResult(resp);
      setEditedResponse(resp.generated_response);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al ejecutar tarea asistida con RAG.');
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = async (status: 'accepted' | 'edited' | 'rejected') => {
    if (!result) return;
    try {
      await apiService.submitAssistantFeedback(result.interaction_id, {
        status,
        feedback_notes: feedbackNotes || undefined,
        edited_payload: isEditing ? { edited_text: editedResponse, original: result.structured_output } : undefined
      });
      setFeedbackSent(true);
      if (status === 'accepted' && onApplySuggestion && result.structured_output) {
        onApplySuggestion(result.structured_output);
      }
    } catch (err: any) {
      console.error(err);
      alert('Error registrando feedback.');
    }
  };

  if (!isOpen) return null;

  const currentTaskMeta = tasksCatalog.find(t => t.task_type === taskType);

  const getTierBadge = (tier: number, isEscalated: boolean) => {
    switch (tier) {
      case 1:
        return <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>⚡ Tier 1: Local / Gratis ($0.00)</span>;
      case 2:
        return <span className="badge badge-info" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>✨ Tier 2: Gemini Flash ($0.00015)</span>;
      case 3:
        return <span className="badge badge-critical" style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>🔥 Tier 3: GPT-4o Premium ($0.005)</span>;
      default:
        return <span className="badge badge-medium">Tier {tier}</span>;
    }
  };

  const getDomainBadge = (domain: string) => {
    switch (domain) {
      case 'normative_knowledge':
        return <span className="badge badge-info" style={{ fontSize: '10px' }}>Normativa</span>;
      case 'rule_knowledge':
        return <span className="badge badge-primary" style={{ fontSize: '10px' }}>Regla QA/QC</span>;
      case 'deliverable_knowledge':
        return <span className="badge badge-medium" style={{ fontSize: '10px' }}>Entregable</span>;
      case 'observation_rfi_knowledge':
        return <span className="badge badge-warning" style={{ fontSize: '10px' }}>Lección OBS/RFI</span>;
      case 'project_knowledge':
        return <span className="badge badge-success" style={{ fontSize: '10px' }}>Hito Snapshot</span>;
      default:
        return <span className="badge badge-neutral" style={{ fontSize: '10px' }}>{domain}</span>;
    }
  };

  return (
    <div style={{
      position: 'fixed',
      top: 0,
      right: 0,
      bottom: 0,
      width: '620px',
      maxWidth: '95vw',
      background: 'var(--bg-card)',
      boxShadow: '-6px 0 25px rgba(0, 0, 0, 0.45)',
      zIndex: 1000,
      display: 'flex',
      flexDirection: 'column',
      borderLeft: '1px solid var(--border-subtle)',
      transition: 'all 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 20px',
        borderBottom: '1px solid var(--border-subtle)',
        background: 'var(--bg-sidebar)',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div style={{
            background: 'linear-gradient(135deg, var(--primary), var(--accent))',
            padding: '8px',
            borderRadius: '8px',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}>
            <Bot size={20} />
          </div>
          <div>
            <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
              Asistente Copilot Operacional
              <span className="badge badge-primary" style={{ fontSize: '10px' }}>RAG + Multi-Tier AI</span>
            </h2>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {stage || 'Ingeniería Básica'} • {discipline || 'general'} {projectId ? `• Proyecto: ${projectId.substring(0, 8)}...` : '• Global'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div style={{ display: 'flex', background: 'var(--bg-card)', borderRadius: '6px', padding: '2px', border: '1px solid var(--border-subtle)' }}>
            <button
              className={`btn ${activeTab === 'assistant' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
              onClick={() => setActiveTab('assistant')}
            >
              <Sparkles size={12} /> Asistente
            </button>
            <button
              className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-ghost'}`}
              style={{ padding: '4px 10px', fontSize: '11px' }}
              onClick={() => setActiveTab('history')}
            >
              <History size={12} /> Historial
            </button>
          </div>
          <button
            className="btn btn-ghost btn-icon"
            onClick={onClose}
            style={{ color: 'var(--text-muted)' }}
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Main Body */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px' }}>
        {activeTab === 'assistant' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {/* Selector de Tarea */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                Tipo de Tarea Asistida
              </label>
              <DarkSelect
                style={{ width: '100%', fontSize: '13px' }}
                value={taskType}
                onChange={(val: any) => setTaskType(val as AssistantTaskType)}
                options={[
                  { value: "normative_query", label: "📖 Consulta Normativa Especializada (OGUC/NCh)" },
                  { value: "rule_suggestion", label: "⚙️ Sugerencia y Formulación de Reglas QA/QC" },
                  { value: "completeness_assistance", label: "📋 Asistencia de Completitud Documental & Gatekeeper" },
                  { value: "document_classification", label: "📑 Clasificación y Validación de Entregables" },
                  { value: "review_support", label: "🔍 Apoyo Contextual a Revisión Técnica (HITL)" },
                  { value: "observation_rfi_draft", label: "✍️ Borrador de Observación / RFI / Bloqueo" },
                  { value: "finding_explanation", label: "💡 Explicación Técnica de Hallazgos" },
                  { value: "stage_synthesis", label: "📊 Síntesis Ejecutiva de Corte de Etapa" }
                ]}
              />
              {currentTaskMeta && (
                <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                  {currentTaskMeta.description} • <em>Default: Tier {currentTaskMeta.default_tier} ({currentTaskMeta.default_engine})</em>
                </div>
              )}
            </div>

            {/* Contexto precargado */}
            {contextData && Object.keys(contextData).length > 0 && (
              <div style={{ background: 'rgba(59, 130, 246, 0.08)', border: '1px solid rgba(59, 130, 246, 0.25)', borderRadius: '8px', padding: '10px 14px' }}>
                <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--primary)', marginBottom: '4px' }}>
                  🎯 Contexto Activo Inyectado:
                </div>
                <div style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-muted)', wordBreak: 'break-all' }}>
                  {JSON.stringify(contextData)}
                </div>
              </div>
            )}

            {/* Prompt Input */}
            <div>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '6px', display: 'block' }}>
                Instrucción o Consulta para el Asistente
              </label>
              <textarea
                className="input"
                rows={4}
                style={{ width: '100%', fontSize: '13px', resize: 'vertical' }}
                placeholder="Escribe tu consulta o los detalles del hallazgo/plano a analizar..."
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
              />
            </div>

            {/* Configuración de Routing Avanzada */}
            <div style={{ display: 'flex', gap: '12px', alignItems: 'center', background: 'var(--bg-sidebar)', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ flex: 1 }}>
                <label style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>
                  Forzar Tier de Motor (Opcional):
                </label>
                <DarkSelect
                  style={{ width: '100%', fontSize: '11px', padding: '0px' }} // padding handled internally
                  value={forceTier ?? ''}
                  onChange={(val: any) => setForceTier(val ? Number(val) : undefined)}
                  options={[
                    { value: "", label: "Auto-Routing por Tiers (Recomendado)" },
                    { value: "1", label: "Tier 1: Heurístico Local ($0.00)" },
                    { value: "2", label: "Tier 2: Gemini 2.0 Flash" },
                    { value: "3", label: "Tier 3: GPT-4o Premium" }
                  ]}
                />
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', paddingTop: '16px' }}>
                <input
                  type="checkbox"
                  id="escalation-toggle"
                  checked={allowEscalation}
                  onChange={(e) => setAllowEscalation(e.target.checked)}
                />
                <label htmlFor="escalation-toggle" style={{ fontSize: '11px', cursor: 'pointer' }}>
                  Auto-escalar por criticidad
                </label>
              </div>
            </div>

            {/* Botón de Ejecución */}
            <button
              className="btn btn-primary"
              style={{ padding: '10px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px', fontWeight: 700 }}
              onClick={handleExecute}
              disabled={loading || !prompt.trim()}
            >
              {loading ? (
                <>
                  <div className="spinner" style={{ width: '16px', height: '16px' }} />
                  Recuperando RAG y Consultando Motor IA...
                </>
              ) : (
                <>
                  <Sparkles size={16} /> Ejecutar Asistencia Operacional
                </>
              )}
            </button>

            {/* RESULTADO GENERADO */}
            {result && (
              <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '14px' }}>
                {/* Meta Banner */}
                <div style={{
                  background: 'var(--bg-sidebar)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '12px 16px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: '8px'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    {getTierBadge(result.tier_used, result.was_escalated)}
                    <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                      Motor: <strong style={{ color: 'var(--text-main)' }}>{result.engine_model_used}</strong>
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '11px' }}>
                    <span>Confianza: <strong>{Math.round(result.confidence_score * 100)}%</strong></span>
                    <span>Costo Est.: <strong>${result.cost_estimate_usd.toFixed(5)}</strong></span>
                  </div>

                  {result.was_escalated && (
                    <div style={{ width: '100%', marginTop: '4px', fontSize: '11px', color: 'var(--accent)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Zap size={12} /> Escalado automáticamente a Tier {result.tier_used}: <em>{result.escalation_reason}</em>
                    </div>
                  )}
                </div>

                {/* Respuesta Formateada */}
                <div style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '16px',
                  boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--primary)' }}>
                      Respuesta del Asistente:
                    </span>
                    <button
                      className="btn btn-ghost"
                      style={{ fontSize: '11px', padding: '2px 8px' }}
                      onClick={() => setIsEditing(!isEditing)}
                    >
                      <Edit3 size={12} /> {isEditing ? 'Cancelar Edición' : 'Editar Respuesta'}
                    </button>
                  </div>

                  {isEditing ? (
                    <textarea
                      className="input"
                      rows={8}
                      style={{ width: '100%', fontSize: '12px', fontFamily: 'monospace' }}
                      value={editedResponse}
                      onChange={(e) => setEditedResponse(e.target.value)}
                    />
                  ) : (
                    <div style={{ fontSize: '13px', lineHeight: '1.6', whiteSpace: 'pre-wrap', color: 'var(--text-main)' }}>
                      {result.generated_response}
                    </div>
                  )}

                  {/* Salida Estructurada (JSON) */}
                  {result.structured_output && Object.keys(result.structured_output).length > 0 && (
                    <div style={{ marginTop: '12px', background: 'var(--bg-sidebar)', padding: '10px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '11px', fontWeight: 700, color: 'var(--accent)', marginBottom: '4px' }}>
                        📦 Payload Estructurado Generado:
                      </div>
                      <pre style={{ fontSize: '10px', margin: 0, overflowX: 'auto', color: 'var(--text-muted)' }}>
                        {JSON.stringify(result.structured_output, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>

                {/* Fuentes RAG Recuperadas */}
                <div style={{
                  background: 'var(--bg-sidebar)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '14px 16px'
                }}>
                  <div style={{ fontSize: '12px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                    <Database size={14} style={{ color: 'var(--primary)' }} />
                    Fuentes & Conocimiento Recuperado de la Base Operacional ({result.retrieved_sources.length}):
                  </div>

                  {result.retrieved_sources.length === 0 ? (
                    <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                      No se requirió conocimiento específico de la base o no se encontraron antecedentes aprobados.
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      {result.retrieved_sources.map((src, sIdx) => (
                        <div
                          key={sIdx}
                          style={{
                            background: 'var(--bg-card)',
                            border: '1px solid var(--border-subtle)',
                            borderRadius: '6px',
                            padding: '8px 12px',
                            fontSize: '11px'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 600 }}>
                              {getDomainBadge(src.domain)}
                              <span>{src.title}</span>
                            </div>
                            <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>
                              Relevancia: <strong>{Math.round(src.relevance_score * 100)}%</strong>
                            </span>
                          </div>

                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px', fontStyle: 'italic' }}>
                            "{src.snippet.length > 180 ? src.snippet.substring(0, 180) + '...' : src.snippet}"
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {/* Acciones y Feedback HITL */}
                <div style={{
                  background: 'var(--bg-card)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '8px',
                  padding: '14px 16px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px'
                }}>
                  <div style={{ fontSize: '12px', fontWeight: 700 }}>
                    Gobernanza & Feedback del Auditor (HITL):
                  </div>

                  {feedbackSent ? (
                    <div className="badge badge-success" style={{ padding: '8px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <CheckCircle2 size={16} /> Feedback registrado exitosamente para la interacción.
                    </div>
                  ) : (
                    <>
                      <input
                        type="text"
                        className="input"
                        placeholder="Notas o justificación de auditoría (opcional)..."
                        style={{ fontSize: '12px' }}
                        value={feedbackNotes}
                        onChange={(e) => setFeedbackNotes(e.target.value)}
                      />

                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                          className="btn btn-success"
                          style={{ flex: 1, padding: '8px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          onClick={() => handleFeedback('accepted')}
                        >
                          <CheckCircle2 size={14} /> Aceptar y Aplicar
                        </button>
                        {isEditing && (
                          <button
                            className="btn btn-primary"
                            style={{ flex: 1, padding: '8px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                            onClick={() => handleFeedback('edited')}
                          >
                            <Edit3 size={14} /> Guardar Versión Editada
                          </button>
                        )}
                        <button
                          className="btn btn-danger"
                          style={{ padding: '8px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                          onClick={() => handleFeedback('rejected')}
                        >
                          <XCircle size={14} /> Descartar
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Tab Historial */}
        {activeTab === 'history' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 700, margin: '0 0 8px 0' }}>
              Historial de Interacciones Asistidas ({interactions.length})
            </h3>

            {interactions.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-muted)', fontSize: '12px' }}>
                No hay interacciones registradas aún.
              </div>
            ) : (
              interactions.map((item) => (
                <div
                  key={item.id}
                  style={{
                    background: 'var(--bg-sidebar)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '8px',
                    padding: '12px 14px'
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span className="badge badge-primary" style={{ fontSize: '10px' }}>{item.task_type}</span>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        Tier {item.executed_tier} ({item.engine_model_used})
                      </span>
                    </div>
                    <span className={`badge ${item.feedback_status === 'accepted' ? 'badge-success' : item.feedback_status === 'rejected' ? 'badge-danger' : item.feedback_status === 'edited' ? 'badge-info' : 'badge-warning'}`} style={{ fontSize: '10px' }}>
                      {item.feedback_status.toUpperCase()}
                    </span>
                  </div>

                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '4px' }}>
                    "{item.user_prompt}"
                  </div>

                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', maxHeight: '60px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.generated_response}
                  </div>

                  <div style={{ marginTop: '8px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '10px', color: 'var(--text-dim)' }}>
                    <span>Fuentes RAG: {item.retrieved_knowledge_ids?.length || 0}</span>
                    <span>{new Date(item.created_at).toLocaleString()}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </div>
    </div>
  );
};
