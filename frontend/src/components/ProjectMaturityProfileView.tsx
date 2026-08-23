import React, { useState, useEffect } from 'react';
import {
  TrendingUp, Award, AlertCircle, CheckCircle2, ShieldAlert,
  ArrowRight, RefreshCw, Download, Database, Layers, Sparkles,
  FileText, SquareCheck, Clock, User, Compass, HelpCircle,
  ExternalLink, BarChart3, ChevronRight, Zap, Target
} from 'lucide-react';
import { apiService } from '../services/api';
import { ProjectMaturityProfileDTO, MaturityLevel } from '../types';
import { useProject } from '../context/ProjectContext';

export const ProjectMaturityProfileView: React.FC = () => {
  const { activeProject, activeProjectId } = useProject();

  const [profile, setProfile] = useState<ProjectMaturityProfileDTO | null>(null);
  const [history, setHistory] = useState<ProjectMaturityProfileDTO[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<'routes_gaps' | 'dimensions' | 'knowledge_assistant' | 'capability' | 'history'>('routes_gaps');
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    if (activeProjectId) {
      loadProfileData();
    }
  }, [activeProjectId]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 4000);
  };

  const loadProfileData = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const [prof, hist] = await Promise.all([
        apiService.getLatestProjectMaturity(activeProjectId),
        apiService.getProjectMaturityHistory(activeProjectId, 10)
      ]);
      setProfile(prof);
      setHistory(hist);
    } catch (e) {
      console.error('Error cargando perfil de madurez:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleReEvaluate = async () => {
    if (!activeProjectId) return;
    setEvaluating(true);
    try {
      const updated = await apiService.evaluateProjectMaturity(activeProjectId, activeProject?.stage || 'Ingeniería Básica');
      setProfile(updated);
      const hist = await apiService.getProjectMaturityHistory(activeProjectId, 10);
      setHistory(hist);
      showToast(`Evaluación completada: Score ${updated.overall_score} pts (${updated.maturity_level.toUpperCase()})`);
    } catch (e: any) {
      console.error(e);
      alert(e.response?.data?.detail || 'Error al ejecutar evaluación de madurez.');
    } finally {
      setEvaluating(false);
    }
  };

  const handleExportJson = async () => {
    if (!profile || !activeProjectId) return;
    try {
      const data = await apiService.exportProjectMaturityProfile(activeProjectId, profile.id);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `perfil_madurez_${activeProject?.code || 'PRJ'}_${profile.stage}_${profile.id.substring(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
      showToast('Perfil de madurez exportado con hash criptográfico SHA-256.');
    } catch (e) {
      console.error(e);
      alert('Error al exportar perfil JSON.');
    }
  };

  const getLevelBadge = (level: MaturityLevel) => {
    switch (level) {
      case 'insufficient':
        return <span className="badge badge-critical" style={{ fontSize: '13px', padding: '6px 12px' }}>INSUFICIENTE (&lt;35)</span>;
      case 'basic':
        return <span className="badge badge-medium" style={{ fontSize: '13px', padding: '6px 12px' }}>BÁSICO (35-59)</span>;
      case 'intermediate':
        return <span className="badge badge-info" style={{ fontSize: '13px', padding: '6px 12px' }}>INTERMEDIO (60-79)</span>;
      case 'advanced':
        return <span className="badge badge-success" style={{ fontSize: '13px', padding: '6px 12px' }}>AVANZADO (80-94)</span>;
      case 'exhaustive':
        return <span className="badge" style={{ fontSize: '13px', padding: '6px 12px', background: 'linear-gradient(135deg, #8b5cf6, #06b6d4)', color: '#fff' }}>EXHAUSTIVO (≥95)</span>;
      default:
        return <span className="badge badge-info">{level}</span>;
    }
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority) {
      case 'critical':
        return <span className="badge badge-critical">CRÍTICA</span>;
      case 'high':
        return <span className="badge badge-medium">ALTA</span>;
      case 'medium':
        return <span className="badge badge-info">MEDIA</span>;
      default:
        return <span className="badge badge-low">BAJA</span>;
    }
  };

  if (!activeProjectId) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center' }}>
        <Compass size={40} style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
        <h3 style={{ fontSize: '18px', fontWeight: 700 }}>Ningún Proyecto Activo</h3>
        <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '6px' }}>
          Selecciona un proyecto activo en el selector superior para auditar su perfil de madurez informacional.
        </p>
      </div>
    );
  }

  if (loading && !profile) {
    return (
      <div className="card" style={{ padding: '50px', textAlign: 'center' }}>
        <RefreshCw className="animate-spin" size={32} style={{ color: 'var(--primary)', margin: '0 auto 12px' }} />
        <p style={{ color: 'var(--text-muted)' }}>Evaluando suficiencia y madurez informacional del proyecto...</p>
      </div>
    );
  }

  if (!profile) return null;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      
      {/* Toast Notification */}
      {toastMessage && (
        <div style={{
          position: 'fixed',
          top: '20px',
          right: '20px',
          background: '#059669',
          color: '#ffffff',
          padding: '12px 20px',
          borderRadius: '8px',
          boxShadow: '0 10px 25px rgba(0,0,0,0.5)',
          zIndex: 2000,
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          fontSize: '13px',
          fontWeight: 600
        }}>
          <CheckCircle2 size={18} />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Tarjeta Principal de Madurez & Score */}
      <div className="card" style={{ background: 'linear-gradient(135deg, var(--bg-card) 0%, rgba(15, 23, 42, 0.95) 100%)', border: '1px solid var(--border-subtle)', padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Compass size={28} style={{ color: 'var(--primary)' }} />
              <div>
                <h2 style={{ fontSize: '20px', fontWeight: 800, margin: 0 }}>
                  Perfil de Madurez & Suficiencia Informacional
                </h2>
                <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
                  Proyecto: <strong>{activeProject?.name}</strong> ({activeProject?.code}) | Etapa: <strong>{profile.stage}</strong>
                </span>
              </div>
            </div>
          </div>

          {/* Botones de Acción */}
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
            <button
              className="btn btn-secondary"
              onClick={handleExportJson}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Download size={15} /> Exportar JSON
            </button>
            <button
              className="btn btn-primary"
              onClick={handleReEvaluate}
              disabled={evaluating}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700 }}
            >
              <RefreshCw size={15} className={evaluating ? 'animate-spin' : ''} />
              <span>{evaluating ? 'Evaluando...' : 'Re-evaluar Madurez'}</span>
            </button>
          </div>
        </div>

        {/* Métricas Principales en Grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginTop: '24px' }}>
          
          {/* Card 1: Score Global */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>SCORE GLOBAL</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '32px', fontWeight: 900, color: profile.overall_score >= 80 ? '#10b981' : profile.overall_score >= 60 ? '#38bdf8' : '#f59e0b' }}>
                {profile.overall_score}
              </span>
              <span style={{ fontSize: '14px', color: 'var(--text-muted)' }}>/ 100 pts</span>
            </div>
            
            {/* Barra de Progreso */}
            <div style={{ width: '100%', height: '6px', background: '#334155', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
              <div style={{
                width: `${profile.overall_score}%`,
                height: '100%',
                background: profile.overall_score >= 80 ? 'linear-gradient(90deg, #10b981, #06b6d4)' : 'linear-gradient(90deg, #f59e0b, #3b82f6)',
                transition: 'width 0.5s ease'
              }} />
            </div>
          </div>

          {/* Card 2: Nivel Actual */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>NIVEL ACTUAL</span>
            <div style={{ marginTop: '8px' }}>
              {getLevelBadge(profile.maturity_level)}
            </div>
            <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-muted)' }}>
              Objetivo: <strong>{profile.target_level.toUpperCase()}</strong> {profile.is_target_achieved ? '✓ Alcanzado' : '⏳ Pendiente'}
            </div>
          </div>

          {/* Card 3: Brechas Críticas */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>BRECHAS CRÍTICAS</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '4px' }}>
              <span style={{ fontSize: '28px', fontWeight: 800, color: profile.critical_gaps.length > 0 ? '#ef4444' : '#10b981' }}>
                {profile.critical_gaps.length}
              </span>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>faltantes bloqueantes</span>
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              Rutas sugeridas: <strong>{profile.acquisition_routes.length}</strong>
            </div>
          </div>

          {/* Card 4: Evolución Delta */}
          <div style={{ background: 'rgba(0,0,0,0.25)', padding: '16px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 600 }}>EVOLUCIÓN RESPECTO PREVIA</span>
            <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px', marginTop: '4px' }}>
              {profile.delta_summary.previous_score !== null && profile.delta_summary.previous_score !== undefined ? (
                <>
                  <span style={{ fontSize: '28px', fontWeight: 800, color: profile.delta_summary.score_delta >= 0 ? '#10b981' : '#ef4444' }}>
                    {profile.delta_summary.score_delta >= 0 ? `+${profile.delta_summary.score_delta}` : profile.delta_summary.score_delta}
                  </span>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>pts delta</span>
                </>
              ) : (
                <span style={{ fontSize: '14px', color: 'var(--text-muted)', marginTop: '8px' }}>Evaluación Inicial Base</span>
              )}
            </div>
            <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
              {profile.delta_summary.newly_resolved_gaps_count > 0 ? `✓ ${profile.delta_summary.newly_resolved_gaps_count} brechas resueltas` : 'Línea de base establecida'}
            </div>
          </div>

        </div>
      </div>

      {/* Selector de Pestañas de Detalle */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px', flexWrap: 'wrap' }}>
        <button
          className={`btn ${activeTab === 'routes_gaps' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('routes_gaps')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Target size={15} /> Ruta Sugerida de Adquisición ({profile.acquisition_routes.length})
        </button>
        <button
          className={`btn ${activeTab === 'dimensions' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('dimensions')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <BarChart3 size={15} /> Dimensiones & Disciplinas
        </button>
        <button
          className={`btn ${activeTab === 'knowledge_assistant' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('knowledge_assistant')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Sparkles size={15} /> Conocimiento Adquirido & Asistente RAG
        </button>
        <button
          className={`btn ${activeTab === 'capability' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('capability')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <ShieldAlert size={15} /> Capacidad de Revisión del Sistema
        </button>
        <button
          className={`btn ${activeTab === 'history' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('history')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Clock size={15} /> Historial Snapshots ({history.length})
        </button>
      </div>

      {/* PESTAÑA 1: RUTA SUGERIDA DE ADQUISICIÓN & BRECHAS */}
      {activeTab === 'routes_gaps' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          
          <div className="card" style={{ padding: '16px', background: 'rgba(30, 41, 59, 0.4)', border: '1px solid var(--border-subtle)' }}>
            <h3 style={{ fontSize: '15px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Compass size={18} style={{ color: 'var(--primary)' }} />
              Ruta Accionable de Adquisición de Información para Desbloquear la Auditoría
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginTop: '4px' }}>
              El motor identificó las siguientes fuentes faltantes prioritarias, indicando responsable, vía de incorporación e impacto de desbloqueo en la etapa actual.
            </p>
          </div>

          {profile.acquisition_routes.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {profile.acquisition_routes.map((route, idx) => {
                const associatedGap = profile.critical_gaps.find(g => g.id === route.gap_id);
                return (
                  <div key={route.id || idx} className="card" style={{ padding: '18px', borderLeft: '4px solid var(--primary)', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <span style={{ fontWeight: 800, fontSize: '15px' }}>{route.gap_title}</span>
                        {associatedGap && getPriorityBadge(associatedGap.priority)}
                        <span className="badge badge-info">{route.target_discipline.toUpperCase()}</span>
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#10b981', fontWeight: 700 }}>
                        <TrendingUp size={14} /> +{route.estimated_score_gain} pts ganancia estimada
                      </div>
                    </div>

                    {associatedGap && (
                      <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '4px 0' }}>
                        <strong>Por qué importa:</strong> {associatedGap.impact_rationale}
                      </p>
                    )}

                    {/* Fila de Detalles Operativos */}
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px', background: 'rgba(0,0,0,0.2)', padding: '12px', borderRadius: '6px', fontSize: '12px' }}>
                      <div>
                        <span style={{ color: 'var(--text-muted)', display: 'block' }}>Responsable Sugerido:</span>
                        <strong style={{ color: '#f8fafc' }}>{route.suggested_responsible}</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)', display: 'block' }}>Método de Ingreso:</span>
                        <strong style={{ color: '#38bdf8' }}>{route.intake_method}</strong>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)', display: 'block' }}>Fuente / Repositorio:</span>
                        <span>{route.suggested_repository}</span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)', display: 'block' }}>Impacto de Desbloqueo:</span>
                        <span style={{ color: '#10b981' }}>{route.unlock_impact}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="card" style={{ padding: '30px', textAlign: 'center' }}>
              <CheckCircle2 size={36} style={{ color: '#10b981', margin: '0 auto 10px' }} />
              <h4 style={{ fontWeight: 700 }}>Sin Brechas Críticas Detectadas</h4>
              <p style={{ color: 'var(--text-muted)', fontSize: '13px' }}>El proyecto cuenta con la información base suficiente para su nivel de exigencia actual.</p>
            </div>
          )}
        </div>
      )}

      {/* PESTAÑA 2: DIMENSIONES & DISCIPLINAS */}
      {activeTab === 'dimensions' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* 5 Dimensiones */}
          <div className="card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '16px' }}>Desglose Explicable por Dimensiones (100% Ponderado)</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              {Object.entries(profile.dimension_scores).map(([key, dim]) => (
                <div key={key} style={{ background: 'rgba(0,0,0,0.15)', padding: '12px 16px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
                    <span style={{ fontWeight: 700, fontSize: '14px' }}>{dim.title} <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>({(dim.weight * 100).toFixed(0)}% peso)</span></span>
                    <span style={{ fontWeight: 800, color: dim.score >= 70 ? '#10b981' : dim.score >= 50 ? '#38bdf8' : '#f59e0b' }}>
                      {dim.score.toFixed(1)} pts → +{dim.weighted_score.toFixed(2)} pts ponderados
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', background: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ width: `${dim.score}%`, height: '100%', background: dim.score >= 70 ? '#10b981' : '#38bdf8' }} />
                  </div>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block', marginTop: '6px' }}>
                    {dim.details}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Disciplinas */}
          <div className="card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '16px' }}>Cobertura Informacional por Disciplina</h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '14px' }}>
              {Object.entries(profile.discipline_scores).map(([discKey, disc]) => (
                <div key={discKey} style={{ background: 'rgba(0,0,0,0.2)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontWeight: 700, fontSize: '14px' }}>{disc.title}</span>
                    <span className={`badge ${disc.status === 'adequate' ? 'badge-success' : disc.status === 'partial' ? 'badge-medium' : 'badge-critical'}`}>
                      {disc.status === 'adequate' ? 'Adecuada' : disc.status === 'partial' ? 'Parcial' : 'Insuficiente'}
                    </span>
                  </div>
                  <div style={{ marginTop: '8px', fontSize: '20px', fontWeight: 800 }}>
                    {disc.score} pts
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    {disc.doc_count} documentos cargados | {disc.rule_count} reglas aplicables
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* PESTAÑA 3: CONOCIMIENTO ADQUIRIDO & ASISTENTE RAG */}
      {activeTab === 'knowledge_assistant' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          
          {/* Panel Izquierdo: Conocimiento Adquirido & Validado */}
          <div className="card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Database size={18} style={{ color: 'var(--primary)' }} />
              Conocimiento Adquirido & Validado
            </h3>
            
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Docs Disponibles</span>
                <div style={{ fontSize: '18px', fontWeight: 800 }}>{profile.acquired_knowledge_summary.available_documents_count}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Evidencia Apta</span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#10b981' }}>{profile.acquired_knowledge_summary.validated_evidence_count}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>KB Items Aprobados</span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#38bdf8' }}>{profile.acquired_knowledge_summary.approved_kb_items_count}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>RFIs Cerrados</span>
                <div style={{ fontSize: '18px', fontWeight: 800 }}>{profile.acquired_knowledge_summary.closed_rfis_count}</div>
              </div>
            </div>

            <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px' }}>Adquirido Recientemente (Últimos 7 días)</h4>
            {profile.acquired_knowledge_summary.recently_acquired_items?.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {profile.acquired_knowledge_summary.recently_acquired_items.map((item) => (
                  <div key={item.id} style={{ padding: '8px 10px', background: 'rgba(255,255,255,0.03)', borderRadius: '6px', fontSize: '12px', borderLeft: '3px solid #10b981' }}>
                    <div style={{ fontWeight: 700 }}>{item.title}</div>
                    <span style={{ color: 'var(--text-muted)', fontSize: '11px' }}>{item.domain} | Origen: {item.origin_type}</span>
                  </div>
                ))}
              </div>
            ) : (
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Sin nuevas incorporaciones en la última semana.</span>
            )}
          </div>

          {/* Panel Derecho: Uso por el Asistente RAG */}
          <div className="card" style={{ padding: '20px' }}>
            <h3 style={{ fontSize: '16px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '14px' }}>
              <Sparkles size={18} style={{ color: 'var(--accent)' }} />
              Conocimiento Utilizado por el Asistente
            </h3>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px', marginBottom: '16px' }}>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Interacciones RAG</span>
                <div style={{ fontSize: '18px', fontWeight: 800 }}>{profile.assistant_usage_summary.total_interactions}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Chunks Reutilizados</span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#38bdf8' }}>{profile.assistant_usage_summary.project_chunks_used_count}</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Confianza Promedio</span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#10b981' }}>{(profile.assistant_usage_summary.average_confidence * 100).toFixed(0)}%</div>
              </div>
              <div style={{ background: 'rgba(0,0,0,0.2)', padding: '10px', borderRadius: '6px' }}>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Ahorro Routing USD</span>
                <div style={{ fontSize: '18px', fontWeight: 800, color: '#10b981' }}>${profile.assistant_usage_summary.estimated_savings_usd}</div>
              </div>
            </div>

            <h4 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px' }}>Tareas Asistidas Ejecutadas</h4>
            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
              {profile.assistant_usage_summary.tasks_executed?.length > 0 ? (
                profile.assistant_usage_summary.tasks_executed.map(t => (
                  <span key={t} className="badge badge-info">{t}</span>
                ))
              ) : (
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Sin interacciones del asistente registradas aún.</span>
              )}
            </div>
          </div>

        </div>
      )}

      {/* PESTAÑA 4: CAPACIDAD DE REVISIÓN */}
      {activeTab === 'capability' && (
        <div className="card" style={{ padding: '24px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '16px' }}>Diagnóstico de Capacidad de Auditoría Técnica</h3>
          
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ background: 'rgba(16, 185, 129, 0.1)', border: '1px solid rgba(16, 185, 129, 0.3)', padding: '16px', borderRadius: '8px' }}>
              <strong style={{ color: '#10b981', display: 'block', fontSize: '14px', marginBottom: '4px' }}>✓ Alcance Auditable con Alta Confianza</strong>
              <p style={{ margin: 0, fontSize: '13px', color: '#e2e8f0' }}>{profile.review_capability_assessment.auditable_scope}</p>
            </div>

            <div style={{ background: 'rgba(56, 189, 248, 0.1)', border: '1px solid rgba(56, 189, 248, 0.3)', padding: '16px', borderRadius: '8px' }}>
              <strong style={{ color: '#38bdf8', display: 'block', fontSize: '14px', marginBottom: '4px' }}>⚠ Alcance con Cobertura Parcial</strong>
              <p style={{ margin: 0, fontSize: '13px', color: '#e2e8f0' }}>{profile.review_capability_assessment.partially_auditable_scope}</p>
            </div>

            <div style={{ background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.3)', padding: '16px', borderRadius: '8px' }}>
              <strong style={{ color: '#ef4444', display: 'block', fontSize: '14px', marginBottom: '4px' }}>✕ Áreas Ciegas / Bloqueadas por Falta de Datos</strong>
              <p style={{ margin: 0, fontSize: '13px', color: '#e2e8f0' }}>{profile.review_capability_assessment.blind_blocked_scope}</p>
            </div>
          </div>
        </div>
      )}

      {/* PESTAÑA 5: HISTORIAL SNAPSHOTS */}
      {activeTab === 'history' && (
        <div className="card" style={{ padding: '20px' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 800, marginBottom: '14px' }}>Evolución Temporal de Suficiencia Informacional</h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {history.map((hist, idx) => (
              <div key={hist.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 16px', background: 'rgba(0,0,0,0.2)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)', width: '30px' }}>#{history.length - idx}</span>
                  <div>
                    <span style={{ fontWeight: 700, fontSize: '14px' }}>Score: {hist.overall_score} pts</span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'block' }}>{new Date(hist.created_at).toLocaleString()} | Por: {hist.evaluated_by}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                  {getLevelBadge(hist.maturity_level)}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};
