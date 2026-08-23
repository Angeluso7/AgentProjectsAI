import React, { useState, useEffect, useMemo } from 'react';
import { apiService } from '../services/api';
import { useProject } from '../context/ProjectContext';
import {
  KnowledgeItemSummaryDTO,
  KnowledgeItemDetailDTO,
  KnowledgeStatsDTO,
  KnowledgeDomain,
  KnowledgeStatus,
  KnowledgeSearchResponseDTO,
  KnowledgeSearchResultItemDTO
} from '../types';
import {
  Database,
  Search,
  Filter,
  RefreshCw,
  ShieldCheck,
  CheckCircle,
  Clock,
  Archive,
  BookOpen,
  Sliders,
  FileText,
  AlertTriangle,
  Layers,
  Award,
  Sparkles,
  GitBranch,
  ExternalLink,
  ChevronRight,
  X,
  Plus,
  Play,
  RotateCcw,
  Tag,
  Info,
  Globe
} from 'lucide-react';
import { InformationAcquisitionManagerView } from './InformationAcquisitionManagerView';

const DOMAIN_LABELS: Record<string, { label: string; color: string; bg: string }> = {
  normative_knowledge: { label: 'Normativo & Criterios', color: '#38bdf8', bg: 'rgba(56, 189, 248, 0.12)' },
  rule_knowledge: { label: 'Reglas QA/QC', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.12)' },
  deliverable_knowledge: { label: 'Entregables & Gatekeeper', color: '#f59e0b', bg: 'rgba(245, 158, 11, 0.12)' },
  guide_document_knowledge: { label: 'Documentos Guía & Plantillas', color: '#06b6d4', bg: 'rgba(6, 182, 212, 0.12)' },
  review_knowledge: { label: 'Patrones de Revisión', color: '#ec4899', bg: 'rgba(236, 72, 153, 0.12)' },
  observation_rfi_knowledge: { label: 'Lecciones Observaciones & RFIs', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' },
  project_knowledge: { label: 'Hitos & Memoria de Proyecto', color: '#6366f1', bg: 'rgba(99, 102, 241, 0.12)' },
  feedback_learning_knowledge: { label: 'Feedback & Active Learning', color: '#14b8a6', bg: 'rgba(20, 184, 166, 0.12)' },
  symbol_knowledge: { label: 'Catálogo de Símbolos', color: '#8b5cf6', bg: 'rgba(139, 92, 246, 0.12)' },
  template_knowledge: { label: 'Plantillas & Viñetas', color: '#f43f5e', bg: 'rgba(244, 63, 94, 0.12)' },
  lesson_knowledge: { label: 'Lecciones Aprendidas', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' },
  guide_knowledge: { label: 'Checklists & Guías', color: '#0ea5e9', bg: 'rgba(14, 165, 233, 0.12)' },
  web_research_knowledge: { label: 'Búsqueda Web Asistida', color: '#c084fc', bg: 'rgba(192, 132, 252, 0.12)' },
};

const STATUS_CONFIG: Record<KnowledgeStatus, { label: string; badgeClass: string; isReusable: boolean }> = {
  draft: { label: 'Borrador', badgeClass: 'badge-medium', isReusable: false },
  extracted: { label: 'Extraído', badgeClass: 'badge-medium', isReusable: false },
  reviewed: { label: 'Revisado', badgeClass: 'badge-low', isReusable: false },
  validated: { label: 'Validado', badgeClass: 'badge-success', isReusable: true },
  approved_for_reuse: { label: 'Aprobado Reutilización', badgeClass: 'badge-success', isReusable: true },
  superseded: { label: 'Reemplazado (Histórico)', badgeClass: 'badge-low', isReusable: false },
  archived: { label: 'Archivado', badgeClass: 'badge-low', isReusable: false },
  rejected: { label: 'Rechazado', badgeClass: 'badge-high', isReusable: false },
};

export const KnowledgeBaseManager: React.FC = () => {
  const { activeProject } = useProject();

  // Estados principales
  const [items, setItems] = useState<KnowledgeItemSummaryDTO[]>([]);
  const [stats, setStats] = useState<KnowledgeStatsDTO | null>(null);
  const [selectedItem, setSelectedItem] = useState<KnowledgeItemDetailDTO | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null);

  // Subpestaña: 'catalog' | 'rag_simulator' | 'acquisition'
  const [activeTab, setActiveTab] = useState<'catalog' | 'rag_simulator' | 'acquisition'>('catalog');

  // Filtros
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [domainFilter, setDomainFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [disciplineFilter, setDisciplineFilter] = useState<string>('all');
  const [stageFilter, setStageFilter] = useState<string>('all');
  const [activeOnly, setActiveOnly] = useState<boolean>(false);
  const [scopeMode, setScopeMode] = useState<'all' | 'project' | 'global'>('all');

  // Modal nueva versión
  const [isVersionModalOpen, setIsVersionModalOpen] = useState<boolean>(false);
  const [versionText, setVersionText] = useState<string>('');
  const [versionNotes, setVersionNotes] = useState<string>('');
  const [versionTitle, setVersionTitle] = useState<string>('');

  // RAG Simulator
  const [ragQuery, setRagQuery] = useState<string>('ancho libre minimo de puertas y cuadro de vanos');
  const [ragDomain, setRagDomain] = useState<string>('all');
  const [ragActiveOnly, setRagActiveOnly] = useState<boolean>(true);
  const [ragResults, setRagResults] = useState<KnowledgeSearchResponseDTO | null>(null);
  const [isSearchingRag, setIsSearchingRag] = useState<boolean>(false);

  // Cargar datos
  const loadKnowledgeData = async () => {
    setIsLoading(true);
    try {
      const [statsData, itemsData] = await Promise.all([
        apiService.getKnowledgeStats(activeProject?.id),
        apiService.getKnowledgeItems({
          project_id: scopeMode === 'project' ? activeProject?.id : undefined,
          domain: domainFilter !== 'all' ? domainFilter : undefined,
          status: statusFilter !== 'all' ? statusFilter : undefined,
          discipline: disciplineFilter !== 'all' ? disciplineFilter : undefined,
          stage: stageFilter !== 'all' ? stageFilter : undefined,
          active_only: activeOnly,
          search: searchTerm ? searchTerm : undefined,
          include_global: scopeMode !== 'project',
          limit: 150
        })
      ]);
      setStats(statsData);
      setItems(itemsData);
    } catch (err) {
      console.error('Error cargando base de conocimiento:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadKnowledgeData();
  }, [activeProject?.id, domainFilter, statusFilter, disciplineFilter, stageFilter, activeOnly, scopeMode]);

  // Selección de ítem
  const handleSelectItem = async (itemId: string) => {
    setIsDetailLoading(true);
    try {
      const detail = await apiService.getKnowledgeItemDetail(itemId);
      setSelectedItem(detail);
    } catch (err) {
      console.error('Error obteniendo detalle de conocimiento:', err);
    } finally {
      setIsDetailLoading(false);
    }
  };

  // Transición de estado
  const handleTransitionStatus = async (targetStatus: KnowledgeStatus, notes?: string) => {
    if (!selectedItem) return;
    try {
      const updated = await apiService.transitionKnowledgeStatus(selectedItem.id, {
        target_status: targetStatus,
        notes: notes || `Transición a ${STATUS_CONFIG[targetStatus].label} desde UI`
      });
      setSelectedItem(updated);
      await loadKnowledgeData();
    } catch (err) {
      console.error('Error en transición de estado:', err);
    }
  };

  // Sincronización desde módulos
  const handleSync = async (sourceModule: string = 'all', autoApprove: boolean = false) => {
    setIsSyncing(true);
    setSyncFeedback(null);
    try {
      const res = await apiService.syncKnowledgeBase({
        project_id: activeProject?.id,
        auto_approve: autoApprove,
        source_module: sourceModule
      });
      setSyncFeedback(res.message);
      await loadKnowledgeData();
    } catch (err) {
      console.error('Error sincronizando conocimiento:', err);
      setSyncFeedback('Ocurrió un error al sincronizar con los módulos.');
    } finally {
      setIsSyncing(false);
    }
  };

  // Crear nueva versión
  const handleCreateNewVersion = async () => {
    if (!selectedItem || !versionText.trim() || !versionNotes.trim()) return;
    try {
      const newVersion = await apiService.versionKnowledgeItem(selectedItem.id, {
        new_title: versionTitle || undefined,
        new_content_text: versionText,
        change_notes: versionNotes
      });
      setSelectedItem(newVersion);
      setIsVersionModalOpen(false);
      setVersionText('');
      setVersionNotes('');
      setVersionTitle('');
      await loadKnowledgeData();
    } catch (err) {
      console.error('Error creando nueva versión:', err);
    }
  };

  // Simulación de consulta RAG
  const handleRunRagSearch = async () => {
    if (!ragQuery.trim()) return;
    setIsSearchingRag(true);
    try {
      const res = await apiService.searchKnowledgeBase({
        query: ragQuery,
        project_id: activeProject?.id,
        domain: ragDomain !== 'all' ? ragDomain : undefined,
        active_only: ragActiveOnly,
        top_k: 5
      });
      setRagResults(res);
    } catch (err) {
      console.error('Error en simulación RAG:', err);
    } finally {
      setIsSearchingRag(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header & Stats Strip */}
      <div className="card" style={{ padding: '20px', background: 'linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px', marginBottom: '20px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div style={{ width: '38px', height: '38px', borderRadius: '10px', background: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#fff' }}>
                <Database size={22} />
              </div>
              <div>
                <h1 style={{ fontSize: '20px', fontWeight: 800, margin: 0, letterSpacing: '-0.02em' }}>Base de Conocimiento Operacional del Asistente</h1>
                <p style={{ color: 'var(--text-muted)', fontSize: '13px', margin: '2px 0 0 0' }}>
                  Repositorio estructurado, versionado y gobernable para el aprendizaje y recuperación contextual (RAG) de normas, reglas, entregables y lecciones de revisión.
                </p>
              </div>
            </div>
          </div>

          {/* Sync Controls */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary"
              onClick={() => handleSync('all', false)}
              disabled={isSyncing}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}
            >
              <RefreshCw size={15} className={isSyncing ? 'animate-spin' : ''} />
              {isSyncing ? 'Sincronizando...' : 'Sincronizar Módulos'}
            </button>
            <button
              className="btn btn-primary"
              onClick={() => handleSync('all', true)}
              disabled={isSyncing}
              style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px' }}
              title="Sincroniza y aprueba automáticamente para reutilización inmediata"
            >
              <ShieldCheck size={15} />
              Sincronizar & Auto-Aprobar
            </button>
          </div>
        </div>

        {syncFeedback && (
          <div style={{ background: 'rgba(56, 189, 248, 0.15)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '13px', color: '#38bdf8', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span>{syncFeedback}</span>
            <button onClick={() => setSyncFeedback(null)} style={{ background: 'none', border: 'none', color: '#38bdf8', cursor: 'pointer' }}>
              <X size={14} />
            </button>
          </div>
        )}

        {/* KPIs Cards */}
        {stats && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '12px' }}>
            <div style={{ background: 'rgba(15, 23, 42, 0.6)', padding: '14px', borderRadius: '10px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Total Unidades</div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: 'var(--text-main)', marginTop: '4px' }}>{stats.total_items}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>{stats.global_items_count} Globales · {stats.project_scoped_items_count} Proyecto</div>
            </div>

            <div style={{ background: 'rgba(16, 185, 129, 0.08)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
              <div style={{ fontSize: '11px', color: '#10b981', textTransform: 'uppercase', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <ShieldCheck size={13} /> Aprobadas Reutilización
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#10b981', marginTop: '4px' }}>{stats.approved_for_reuse_count}</div>
              <div style={{ fontSize: '11px', color: 'rgba(16, 185, 129, 0.8)', marginTop: '2px' }}>Elegibles para Asistente RAG</div>
            </div>

            <div style={{ background: 'rgba(56, 189, 248, 0.08)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(56, 189, 248, 0.25)' }}>
              <div style={{ fontSize: '11px', color: '#38bdf8', textTransform: 'uppercase', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle size={13} /> Validadas
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#38bdf8', marginTop: '4px' }}>{stats.validated_count}</div>
              <div style={{ fontSize: '11px', color: 'rgba(56, 189, 248, 0.8)', marginTop: '2px' }}>Revisadas formalmente</div>
            </div>

            <div style={{ background: 'rgba(245, 158, 11, 0.08)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
              <div style={{ fontSize: '11px', color: '#f59e0b', textTransform: 'uppercase', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Clock size={13} /> Borrador / Extracción
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#f59e0b', marginTop: '4px' }}>{stats.draft_or_extracted_count}</div>
              <div style={{ fontSize: '11px', color: 'rgba(245, 158, 11, 0.8)', marginTop: '2px' }}>Pendientes de aprobación</div>
            </div>

            <div style={{ background: 'rgba(148, 163, 184, 0.08)', padding: '14px', borderRadius: '10px', border: '1px solid rgba(148, 163, 184, 0.25)' }}>
              <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '4px' }}>
                <Archive size={13} /> Histórico / Rechazado
              </div>
              <div style={{ fontSize: '24px', fontWeight: 800, color: '#94a3b8', marginTop: '4px' }}>{stats.rejected_or_superseded_count}</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>No recuperables por defecto</div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation Subtabs */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
        <button
          className={`btn ${activeTab === 'catalog' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('catalog')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Layers size={16} /> Catálogo de Conocimiento Operacional
        </button>
        <button
          className={`btn ${activeTab === 'rag_simulator' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('rag_simulator')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Sparkles size={16} /> Simulador RAG & Recuperación Asistente
        </button>
        <button
          className={`btn ${activeTab === 'acquisition' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setActiveTab('acquisition')}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <Globe size={16} /> Ingesta & Solicitudes Web-First
        </button>
      </div>

      {/* Subtab 1: Catálogo y Gestión de Unidades */}
      {activeTab === 'catalog' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Controls & Filter Bar */}
          <div className="card" style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'center' }}>
              {/* Search text */}
              <div style={{ position: 'relative', flex: 1, minWidth: '220px' }}>
                <Search size={16} style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)', color: 'var(--text-dim)' }} />
                <input
                  type="text"
                  placeholder="Buscar en títulos, resúmenes, artículos o reglas..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') loadKnowledgeData(); }}
                  style={{ width: '100%', padding: '8px 12px 8px 36px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
                />
              </div>

              {/* Domain Filter */}
              <select
                value={domainFilter}
                onChange={(e) => setDomainFilter(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              >
                <option value="all">Todos los Dominios</option>
                <option value="normative_knowledge">Normativo & Criterios</option>
                <option value="rule_knowledge">Reglas QA/QC</option>
                <option value="deliverable_knowledge">Entregables & Gatekeeper</option>
                <option value="guide_document_knowledge">Documentos Guía & Plantillas</option>
                <option value="review_knowledge">Patrones de Revisión</option>
                <option value="observation_rfi_knowledge">Observaciones & RFIs</option>
                <option value="project_knowledge">Hitos de Proyecto</option>
                <option value="feedback_learning_knowledge">Feedback Humano</option>
                <option value="symbol_knowledge">Catálogo de Símbolos</option>
                <option value="template_knowledge">Plantillas & Viñetas</option>
                <option value="lesson_knowledge">Lecciones Aprendidas</option>
                <option value="guide_knowledge">Checklists & Guías</option>
                <option value="web_research_knowledge">Búsqueda Web Asistida</option>
              </select>

              {/* Status Filter */}
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              >
                <option value="all">Todos los Estados</option>
                <option value="approved_for_reuse">Aprobado Reutilización</option>
                <option value="validated">Validado</option>
                <option value="reviewed">Revisado</option>
                <option value="extracted">Extraído</option>
                <option value="draft">Borrador</option>
                <option value="superseded">Reemplazado (Histórico)</option>
                <option value="rejected">Rechazado</option>
              </select>

              {/* Scope Mode */}
              <select
                value={scopeMode}
                onChange={(e) => setScopeMode(e.target.value as any)}
                style={{ padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              >
                <option value="all">Alcance: Global + Proyecto</option>
                <option value="project">Solo Proyecto Activo</option>
                <option value="global">Solo Global Organización</option>
              </select>

              {/* Checkbox Reusable Only */}
              <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', cursor: 'pointer', color: 'var(--text-main)' }}>
                <input
                  type="checkbox"
                  checked={activeOnly}
                  onChange={(e) => setActiveOnly(e.target.checked)}
                />
                Solo Aprobados RAG
              </label>

              <button className="btn btn-secondary" onClick={loadKnowledgeData} style={{ padding: '8px 12px' }}>
                <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
              </button>
            </div>
          </div>

          {/* Main Grid: Catalog List & Detail Inspector */}
          <div style={{ display: 'grid', gridTemplateColumns: selectedItem ? '1fr 1fr' : '1fr', gap: '16px' }}>
            {/* Catalog List Table / Cards */}
            <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
              <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 700, fontSize: '14px' }}>Unidades de Conocimiento ({items.length})</span>
                {activeProject && (
                  <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Proyecto: <strong>{activeProject.code}</strong>
                  </span>
                )}
              </div>

              {isLoading ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <RefreshCw size={24} className="animate-spin" style={{ margin: '0 auto 8px' }} />
                  Cargando base de conocimiento...
                </div>
              ) : items.length === 0 ? (
                <div style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                  <Info size={28} style={{ margin: '0 auto 8px', opacity: 0.6 }} />
                  <div>No se encontraron unidades de conocimiento para los filtros seleccionados.</div>
                  <button className="btn btn-secondary" onClick={() => handleSync('all', false)} style={{ marginTop: '12px', fontSize: '12px' }}>
                    Sincronizar desde Módulos Ahora
                  </button>
                </div>
              ) : (
                <div style={{ maxHeight: '680px', overflowY: 'auto' }}>
                  {items.map((item) => {
                    const domainCfg = DOMAIN_LABELS[item.domain as KnowledgeDomain] || { label: item.domain, color: '#94a3b8', bg: 'rgba(148, 163, 184, 0.1)' };
                    const statusCfg = STATUS_CONFIG[item.status as KnowledgeStatus] || { label: item.status, badgeClass: 'badge-low', isReusable: false };
                    const isSelected = selectedItem?.id === item.id;

                    return (
                      <div
                        key={item.id}
                        onClick={() => handleSelectItem(item.id)}
                        style={{
                          padding: '14px 16px',
                          borderBottom: '1px solid var(--border-subtle)',
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                          borderLeft: isSelected ? '3px solid var(--primary)' : '3px solid transparent',
                          transition: 'all 0.15s ease'
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '8px', marginBottom: '6px' }}>
                          <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-main)' }}>{item.title}</div>
                          <span className={`badge ${statusCfg.badgeClass}`} style={{ fontSize: '10px', whiteSpace: 'nowrap' }}>
                            {statusCfg.label}
                          </span>
                        </div>

                        {item.summary && (
                          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px', lineHeight: '1.4' }}>
                            {item.summary.length > 120 ? `${item.summary.slice(0, 120)}...` : item.summary}
                          </div>
                        )}

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', alignItems: 'center', fontSize: '11px' }}>
                          <span style={{ color: domainCfg.color, background: domainCfg.bg, padding: '2px 6px', borderRadius: '4px', fontWeight: 600 }}>
                            {domainCfg.label}
                          </span>
                          <span className="badge badge-low" style={{ fontSize: '10px' }}>
                            {item.discipline}
                          </span>
                          {item.stage && (
                            <span className="badge badge-low" style={{ fontSize: '10px' }}>
                              {item.stage}
                            </span>
                          )}
                          <span style={{ color: 'var(--text-dim)', marginLeft: 'auto' }}>
                            v{item.version_number} · {item.project_id ? 'Proyecto' : 'Global'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Detail Inspector Drawer */}
            {selectedItem && (
              <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px', maxHeight: '740px', overflowY: 'auto' }}>
                {isDetailLoading ? (
                  <div style={{ padding: '40px', textAlign: 'center' }}>
                    <RefreshCw size={24} className="animate-spin" />
                  </div>
                ) : (
                  <>
                    {/* Top Bar of Detail */}
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
                      <div>
                        <div style={{ display: 'flex', gap: '6px', alignItems: 'center', marginBottom: '6px' }}>
                          <span
                            style={{
                              color: DOMAIN_LABELS[selectedItem.domain as KnowledgeDomain]?.color || '#38bdf8',
                              background: DOMAIN_LABELS[selectedItem.domain as KnowledgeDomain]?.bg || 'rgba(56, 189, 248, 0.1)',
                              padding: '2px 8px',
                              borderRadius: '4px',
                              fontWeight: 700,
                              fontSize: '11px'
                            }}
                          >
                            {DOMAIN_LABELS[selectedItem.domain as KnowledgeDomain]?.label || selectedItem.domain}
                          </span>
                          <span className="badge badge-low" style={{ fontSize: '11px' }}>
                            Tipo: {selectedItem.item_type}
                          </span>
                          <span className="badge badge-low" style={{ fontSize: '11px' }}>
                            v{selectedItem.version_number}
                          </span>
                        </div>
                        <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0, color: 'var(--text-main)' }}>{selectedItem.title}</h2>
                      </div>
                      <button
                        onClick={() => setSelectedItem(null)}
                        style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}
                      >
                        <X size={18} />
                      </button>
                    </div>

                    {/* Governance Action Bar */}
                    <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
                      <div style={{ fontSize: '12px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-muted)' }}>
                        Gobernanza & Estado: <span className={`badge ${STATUS_CONFIG[selectedItem.status as KnowledgeStatus]?.badgeClass}`}>{STATUS_CONFIG[selectedItem.status as KnowledgeStatus]?.label}</span>
                        {selectedItem.is_active_for_reuse ? (
                          <span style={{ color: '#10b981', marginLeft: '8px', fontSize: '11px' }}>● Apto Reutilización RAG</span>
                        ) : (
                          <span style={{ color: '#f59e0b', marginLeft: '8px', fontSize: '11px' }}>○ No Elegible para Asistente</span>
                        )}
                      </div>

                      <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                        {selectedItem.status !== 'approved_for_reuse' && (
                          <button
                            className="btn btn-primary"
                            style={{ fontSize: '11px', padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                            onClick={() => handleTransitionStatus('approved_for_reuse', 'Aprobado formalmente por auditor')}
                          >
                            <ShieldCheck size={13} /> Aprobar para Reutilización
                          </button>
                        )}
                        {selectedItem.status !== 'validated' && selectedItem.status !== 'approved_for_reuse' && (
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: '11px', padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                            onClick={() => handleTransitionStatus('validated', 'Validado técnicamente')}
                          >
                            <CheckCircle size={13} /> Validar
                          </button>
                        )}
                        {selectedItem.status !== 'rejected' && (
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: '11px', padding: '6px 10px', color: '#f87171' }}
                            onClick={() => handleTransitionStatus('rejected', 'Rechazado por auditor')}
                          >
                            Rechazar
                          </button>
                        )}
                        {selectedItem.status !== 'archived' && (
                          <button
                            className="btn btn-secondary"
                            style={{ fontSize: '11px', padding: '6px 10px' }}
                            onClick={() => handleTransitionStatus('archived', 'Archivado')}
                          >
                            Archivar
                          </button>
                        )}
                        <button
                          className="btn btn-secondary"
                          style={{ fontSize: '11px', padding: '6px 10px', display: 'flex', alignItems: 'center', gap: '4px' }}
                          onClick={() => {
                            setVersionTitle(selectedItem.title);
                            setVersionText(selectedItem.content_text);
                            setIsVersionModalOpen(true);
                          }}
                        >
                          <GitBranch size={13} /> Nueva Versión
                        </button>
                      </div>
                    </div>

                    {/* Visual Knowledge Metadata & Linked Occurrences */}
                    {(selectedItem.visual_crop_url || selectedItem.structured_payload?.normalized_category || selectedItem.structured_payload?.linked_occurrences) && (
                      <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--primary)', textTransform: 'uppercase', margin: 0, display: 'flex', alignItems: 'center', gap: '6px' }}>
                          <Layers size={14} /> Atributos Visuales & Deduplicación
                        </h3>
                        
                        <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
                          {selectedItem.visual_crop_url && (
                            <div style={{ width: '90px', height: '90px', borderRadius: '6px', background: '#020617', border: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '4px', overflow: 'hidden' }}>
                              <img
                                src={`http://localhost:8000/${selectedItem.visual_crop_url.replace(/^\.\//, '')}`}
                                alt={selectedItem.title}
                                style={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain' }}
                                onError={(e) => { e.currentTarget.style.display = 'none'; }}
                              />
                            </div>
                          )}

                          <div style={{ flex: 1, minWidth: '200px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                            {selectedItem.structured_payload?.normalized_category && (
                              <div><strong>Categoría Taxonómica:</strong> <code style={{ color: '#a78bfa' }}>{selectedItem.structured_payload.normalized_category}</code></div>
                            )}
                            {selectedItem.structured_payload?.aliases && selectedItem.structured_payload.aliases.length > 0 && (
                              <div><strong>Alias / Sinónimos:</strong> {selectedItem.structured_payload.aliases.join(', ')}</div>
                            )}
                            {selectedItem.legend_reference && (
                              <div><strong>Leyenda / Cuadro:</strong> {selectedItem.legend_reference}</div>
                            )}
                            {selectedItem.structured_payload?.related_rule_code && (
                              <div><strong>Regla QA/QC Vinculada:</strong> <code>{selectedItem.structured_payload.related_rule_code}</code></div>
                            )}
                          </div>
                        </div>

                        {selectedItem.structured_payload?.linked_occurrences && selectedItem.structured_payload.linked_occurrences.length > 0 && (
                          <div style={{ marginTop: '6px', borderTop: '1px solid rgba(255,255,255,0.05)', paddingTop: '6px' }}>
                            <strong style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                              Ocurrencias Vinculadas ({selectedItem.structured_payload.linked_occurrences.length} ubicaciones):
                            </strong>
                            <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '4px' }}>
                              {selectedItem.structured_payload.linked_occurrences.map((occ: any, oidx: number) => (
                                <span key={oidx} style={{ fontSize: '10px', background: 'rgba(99, 102, 241, 0.15)', color: '#818cf8', border: '1px solid rgba(99, 102, 241, 0.3)', padding: '2px 6px', borderRadius: '4px' }}>
                                  Lámina: {occ.sheet_code || occ.sheet_id || `Pág. ${occ.page_number || 1}`}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                      </div>
                    )}

                    {/* Normalized Content */}
                    <div>
                      <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                        Contenido Normalizado
                      </h3>
                      <div
                        style={{
                          background: 'var(--bg-sidebar)',
                          padding: '12px',
                          borderRadius: '6px',
                          fontSize: '13px',
                          lineHeight: '1.5',
                          whiteSpace: 'pre-wrap',
                          fontFamily: 'inherit',
                          border: '1px solid var(--border-subtle)'
                        }}
                      >
                        {selectedItem.content_text}
                      </div>
                    </div>

                    {/* Chunks Prepared for RAG */}
                    {selectedItem.chunks && selectedItem.chunks.length > 0 && (
                      <div>
                        <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Fragmentos Indexables ({selectedItem.chunks.length} Chunks RAG)
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                          {selectedItem.chunks.map((c) => (
                            <div key={c.id} style={{ background: 'rgba(15, 23, 42, 0.5)', padding: '10px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '12px' }}>
                              <div style={{ display: 'flex', justifyContent: 'space-between', color: 'var(--primary)', fontWeight: 700, marginBottom: '4px' }}>
                                <span>{c.chunk_title || `Chunk #${c.chunk_index + 1}`}</span>
                                <span style={{ color: 'var(--text-dim)', fontWeight: 400 }}>~{c.token_count} tokens</span>
                              </div>
                              <div style={{ color: 'var(--text-muted)', lineHeight: '1.4' }}>{c.chunk_text}</div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Provenance & Traceability */}
                    <div>
                      <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                        Procedencia & Trazabilidad de Origen
                      </h3>
                      <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '6px', fontSize: '12px', border: '1px solid var(--border-subtle)' }}>
                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', marginBottom: '10px' }}>
                          <div><strong>Origen:</strong> {selectedItem.origin_type}</div>
                          <div><strong>Autor:</strong> {selectedItem.author}</div>
                          <div><strong>Disciplina:</strong> {selectedItem.discipline}</div>
                          <div><strong>Etapa:</strong> {selectedItem.stage || 'Transversal / General'}</div>
                          <div><strong>Confianza:</strong> {(selectedItem.confidence_score * 100).toFixed(0)}%</div>
                          <div><strong>Creado:</strong> {new Date(selectedItem.created_at).toLocaleDateString()}</div>
                        </div>

                        {selectedItem.tags && selectedItem.tags.length > 0 && (
                          <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap', marginTop: '6px' }}>
                            {selectedItem.tags.map((t, idx) => (
                              <span key={idx} className="badge badge-low" style={{ fontSize: '10px' }}>
                                #{t}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Audit Event Timeline */}
                    {selectedItem.provenance_trace && selectedItem.provenance_trace.length > 0 && (
                      <div>
                        <h3 style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '6px' }}>
                          Historial de Eventos de Auditoría
                        </h3>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                          {selectedItem.provenance_trace.map((evt, idx) => (
                            <div key={idx} style={{ fontSize: '11px', color: 'var(--text-muted)', padding: '6px 8px', background: 'rgba(15, 23, 42, 0.4)', borderRadius: '4px' }}>
                              <span style={{ color: 'var(--primary)', fontWeight: 700 }}>[{evt.action}]</span> {evt.notes || 'Evento de ciclo de vida'} — <span style={{ color: 'var(--text-dim)' }}>{evt.author} ({new Date(evt.timestamp).toLocaleString()})</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Subtab 2: Simulador RAG & Recuperación del Asistente */}
      {activeTab === 'rag_simulator' && (
        <div className="card" style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Sparkles size={20} style={{ color: 'var(--primary)' }} />
            <div>
              <h2 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>Simulador de Recuperación Contextual (RAG Tester)</h2>
              <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Prueba cómo el Asistente AI recupera, califica y filtra fragmentos de conocimiento operacional según consultas técnicas.
              </p>
            </div>
          </div>

          {/* Search Inputs */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: '300px' }}>
              <input
                type="text"
                value={ragQuery}
                onChange={(e) => setRagQuery(e.target.value)}
                placeholder="Ejemplo: 'ancho de puertas normativa OGUC', 'viñeta obligatoria plano arquitectura'..."
                onKeyDown={(e) => { if (e.key === 'Enter') handleRunRagSearch(); }}
                style={{ width: '100%', padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '14px' }}
              />
            </div>
            <select
              value={ragDomain}
              onChange={(e) => setRagDomain(e.target.value)}
              style={{ padding: '10px 14px', borderRadius: '8px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
            >
              <option value="all">Todos los Dominios</option>
              <option value="normative_knowledge">Normativo</option>
              <option value="rule_knowledge">Reglas QA/QC</option>
              <option value="deliverable_knowledge">Entregables</option>
              <option value="observation_rfi_knowledge">Observaciones & RFIs</option>
              <option value="project_knowledge">Proyecto</option>
            </select>
            <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-main)', cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={ragActiveOnly}
                onChange={(e) => setRagActiveOnly(e.target.checked)}
              />
              Solo Aprobados para Reutilización
            </label>
            <button
              className="btn btn-primary"
              onClick={handleRunRagSearch}
              disabled={isSearchingRag}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Play size={15} /> {isSearchingRag ? 'Recuperando...' : 'Consultar Asistente'}
            </button>
          </div>

          {/* RAG Results Display */}
          {ragResults && (
            <div style={{ marginTop: '12px' }}>
              <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '12px' }}>
                Resultados Recuperados ({ragResults.total_matches} coincidencias para "{ragResults.query}"):
              </div>

              {ragResults.results.length === 0 ? (
                <div style={{ padding: '30px', textAlign: 'center', background: 'var(--bg-sidebar)', borderRadius: '8px', color: 'var(--text-muted)' }}>
                  No se encontraron fragmentos aprobados para esta consulta. Prueba flexibilizar los filtros o sincronizar más conocimiento.
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  {ragResults.results.map((r, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'var(--bg-sidebar)',
                        padding: '16px',
                        borderRadius: '8px',
                        border: '1px solid var(--border-subtle)',
                        borderLeft: `4px solid ${DOMAIN_LABELS[r.domain]?.color || 'var(--primary)'}`
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontWeight: 800, fontSize: '14px', color: 'var(--text-main)' }}>{r.title}</span>
                          <span className="badge badge-low" style={{ fontSize: '10px' }}>{r.discipline}</span>
                          {r.stage && <span className="badge badge-low" style={{ fontSize: '10px' }}>{r.stage}</span>}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--primary)' }}>
                            Score: {(r.relevance_score * 100).toFixed(0)}%
                          </span>
                          <span className={`badge ${STATUS_CONFIG[r.status]?.badgeClass}`} style={{ fontSize: '10px' }}>
                            {STATUS_CONFIG[r.status]?.label}
                          </span>
                        </div>
                      </div>

                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: '1.5', background: 'rgba(15, 23, 42, 0.5)', padding: '10px', borderRadius: '6px', marginBottom: '8px' }}>
                        {r.snippet}
                      </div>

                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '11px', color: 'var(--text-dim)' }}>
                        <div><strong>Procedencia:</strong> {r.provenance.origin_type} · Autor: {r.provenance.author} · v{r.provenance.version_number}</div>
                        <button
                          className="btn btn-secondary"
                          style={{ fontSize: '11px', padding: '4px 8px' }}
                          onClick={() => {
                            setActiveTab('catalog');
                            handleSelectItem(r.item_id);
                          }}
                        >
                          Ver en Catálogo
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Subtab 3: Ingesta Unificada & Solicitudes Web-First */}
      {activeTab === 'acquisition' && (
        <InformationAcquisitionManagerView
          projectId={activeProject?.id}
          projectName={activeProject?.name}
          projectStage={activeProject?.stage}
        />
      )}

      {/* Modal Crear Nueva Versión */}
      {isVersionModalOpen && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0, 0, 0, 0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div className="card" style={{ width: '90%', maxWidth: '600px', padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '10px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 800, margin: 0 }}>Crear Nueva Versión (v{(selectedItem?.version_number || 1) + 1})</h3>
              <button onClick={() => setIsVersionModalOpen(false)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer' }}>
                <X size={18} />
              </button>
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Título</label>
              <input
                type="text"
                value={versionTitle}
                onChange={(e) => setVersionTitle(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Contenido de la Nueva Versión</label>
              <textarea
                rows={6}
                value={versionText}
                onChange={(e) => setVersionText(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              />
            </div>

            <div>
              <label style={{ fontSize: '12px', fontWeight: 700, display: 'block', marginBottom: '4px' }}>Motivo / Justificación del Cambio (Auditoría)</label>
              <input
                type="text"
                placeholder="Ejemplo: Actualización de criterio según adenda normativa 2026..."
                value={versionNotes}
                onChange={(e) => setVersionNotes(e.target.value)}
                style={{ width: '100%', padding: '8px 12px', borderRadius: '6px', border: '1px solid var(--border-subtle)', background: 'var(--bg-sidebar)', color: 'var(--text-main)', fontSize: '13px' }}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '10px' }}>
              <button className="btn btn-secondary" onClick={() => setIsVersionModalOpen(false)}>
                Cancelar
              </button>
              <button className="btn btn-primary" onClick={handleCreateNewVersion} disabled={!versionText.trim() || !versionNotes.trim()}>
                Guardar Nueva Versión
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
