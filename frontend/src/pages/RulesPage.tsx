import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { RuleDefinitionItem, RuleDocument } from '../types';
import {
  ShieldAlert, Sparkles, BookOpen, Layers, Check, Trash2,
  FolderOpen, Plus, Tag, RefreshCw, FileText, CheckCircle2,
  AlertCircle, Table as TableIcon, X, ArrowUpRight, ShieldCheck,
  SquareCheck, ExternalLink, Award, Loader2, Power
} from 'lucide-react';
import { DocumentContentReviewModal } from '../components/DocumentContentReviewModal';
import { SymbolCurationStudioModal } from '../components/SymbolCurationStudioModal';
import { ResearchCasesPanel } from '../components/ResearchCasesPanel';

export const RulesPage: React.FC = () => {
  const [rules, setRules] = useState<RuleDefinitionItem[]>([]);
  const [ruleDocuments, setRuleDocuments] = useState<RuleDocument[]>([]);
  const [loadingRules, setLoadingRules] = useState(true);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [promotingDocId, setPromotingDocId] = useState<string | null>(null);
  const [promotionNotification, setPromotionNotification] = useState<{ message: string; count: number } | null>(null);

  // Modal de visualización y confirmación de contenido estructurado
  const [selectedRuleDocId, setSelectedRuleDocId] = useState<string | null>(null);
  const [showContentModal, setShowContentModal] = useState(false);
  const [selectedStudioDoc, setSelectedStudioDoc] = useState<RuleDocument | null>(null);
  const [showResearchCasesModal, setShowResearchCasesModal] = useState(false);

  // Modal de Impacto de Eliminación
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletingDoc, setDeletingDoc] = useState<RuleDocument | null>(null);
  const [deletionImpact, setDeletionImpact] = useState<any | null>(null);
  const [loadingImpact, setLoadingImpact] = useState(false);
  const [deletePolicy, setDeletePolicy] = useState<'keep_baseline_source_removed' | 'retire_rules'>('keep_baseline_source_removed');
  const [deletingInProgress, setDeletingInProgress] = useState(false);

  // Gestión y Eliminación de Reglas Baseline
  const [togglingRuleCode, setTogglingRuleCode] = useState<string | null>(null);
  const [showDeleteRuleModal, setShowDeleteRuleModal] = useState(false);
  const [deletingRule, setDeletingRule] = useState<RuleDefinitionItem | null>(null);
  const [deletingRuleInProgress, setDeletingRuleInProgress] = useState(false);
  const [ruleActionFeedback, setRuleActionFeedback] = useState<{ message: string; type: 'success' | 'warning' | 'error' } | null>(null);

  useEffect(() => {
    loadRules();
    loadRuleDocuments();
  }, []);

  const loadRules = async () => {
    try {
      setLoadingRules(true);
      const data = await apiService.getRules();
      setRules(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoadingRules(false);
    }
  };

  const handleToggleRule = async (ruleCode: string, currentEnabled: boolean) => {
    try {
      setTogglingRuleCode(ruleCode);
      setRuleActionFeedback(null);
      await apiService.toggleRuleEnabled(ruleCode, !currentEnabled);
      setRuleActionFeedback({
        message: `Regla ${ruleCode} ${!currentEnabled ? 'activada' : 'desactivada'} exitosamente.`,
        type: 'success'
      });
      await loadRules();
    } catch (err: any) {
      console.error('Error alternando estado de la regla:', err);
      setRuleActionFeedback({
        message: `Error al ${!currentEnabled ? 'activar' : 'desactivar'} la regla ${ruleCode}.`,
        type: 'error'
      });
    } finally {
      setTogglingRuleCode(null);
    }
  };

  const handleConfirmDeleteRule = async () => {
    if (!deletingRule) return;
    try {
      setDeletingRuleInProgress(true);
      const res = await apiService.deleteRule(deletingRule.code);
      setRuleActionFeedback({
        message: res.message || `Regla ${deletingRule.code} eliminada exitosamente.`,
        type: 'success'
      });
      setShowDeleteRuleModal(false);
      setDeletingRule(null);
      await loadRules();
    } catch (err: any) {
      console.error('Error eliminando regla:', err);
      if (err.response?.status === 409) {
        setRuleActionFeedback({
          message: err.response.data?.detail || `La regla ${deletingRule.code} tiene histórico; fue desactivada en su lugar.`,
          type: 'warning'
        });
        setShowDeleteRuleModal(false);
        setDeletingRule(null);
        await loadRules();
      } else {
        setRuleActionFeedback({
          message: err.response?.data?.detail || `Error al eliminar la regla ${deletingRule.code}.`,
          type: 'error'
        });
      }
    } finally {
      setDeletingRuleInProgress(false);
    }
  };

  const loadRuleDocuments = async () => {
    try {
      setLoadingDocs(true);
      const docs = await apiService.getRuleDocuments();
      setRuleDocuments(docs);
    } catch (e) {
      console.error('Error cargando documentos de reglas:', e);
    } finally {
      setLoadingDocs(false);
    }
  };

  // BOTÓN REQUERIDO: ACEPTAR EN EL RENGLÓN DEL DOCUMENTO (PROMOVER A BASELINE QA/QC)
  const handlePromoteDocToBaseline = async (doc: RuleDocument) => {
    setPromotingDocId(doc.id);
    setPromotionNotification(null);
    try {
      const res = await apiService.promoteRuleDocumentToBaseline(doc.id);
      setPromotionNotification({
        message: res.message,
        count: res.promoted_count,
      });
      await loadRuleDocuments();
      await loadRules();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Error al promover reglas a Baseline QA/QC.');
    } finally {
      setPromotingDocId(null);
    }
  };

  const handleOpenDeleteModal = async (doc: RuleDocument) => {
    setDeletingDoc(doc);
    setShowDeleteModal(true);
    setLoadingImpact(true);
    setDeletionImpact(null);
    setDeletePolicy('keep_baseline_source_removed');
    try {
      const impact = await apiService.getRuleDocumentDeletionImpact(doc.id);
      setDeletionImpact(impact);
      if (impact.recommended_policy === 'retire_rules') {
        setDeletePolicy('retire_rules');
      }
    } catch (err: any) {
      console.error('Error fetching deletion impact:', err);
    } finally {
      setLoadingImpact(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!deletingDoc) return;
    setDeletingInProgress(true);
    try {
      await apiService.deleteRuleDocumentWithPolicy(deletingDoc.id, deletePolicy);
      setShowDeleteModal(false);
      setDeletingDoc(null);
      await loadRuleDocuments();
      await loadRules();
    } catch (err: any) {
      alert(err?.response?.data?.detail || 'Error al eliminar documento.');
    } finally {
      setDeletingInProgress(false);
    }
  };

  const handleOpenContent = (docId: string) => {
    setSelectedRuleDocId(docId);
    setShowContentModal(true);
  };

  const getSeverityBadge = (sev: string) => {
    switch (sev) {
      case 'critical': return 'badge-danger';
      case 'high': return 'badge-warning';
      case 'medium': return 'badge-info';
      default: return 'badge-neutral';
    }
  };

  const getDocumentStatusBadge = (status: string) => {
    switch (status) {
      case 'promovido_baseline':
      case 'baseline_active':
        return (
          <span className="px-2.5 py-1 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[11px] font-bold flex items-center gap-1.5 shadow-sm">
            <ShieldCheck size={13} className="text-emerald-400" />
            <span>✓ En Baseline QA/QC</span>
          </span>
        );
      case 'confirmado':
        return (
          <span className="px-2.5 py-1 rounded-full bg-teal-950 text-teal-300 border border-teal-700 text-[11px] font-bold flex items-center gap-1.5">
            <CheckCircle2 size={13} className="text-teal-400" />
            <span>Contenido Confirmado</span>
          </span>
        );
      case 'active':
        return (
          <span className="px-2.5 py-1 rounded-full bg-sky-950 text-sky-300 border border-sky-700 text-[11px] font-bold flex items-center gap-1.5">
            <span>✓ Activo</span>
          </span>
        );
      default:
        return (
          <span className="px-2.5 py-1 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[11px] font-semibold flex items-center gap-1.5">
            <span>⚪ Incorporado (Intake)</span>
          </span>
        );
    }
  };

  return (
    <div style={{ maxWidth: '1440px', margin: '0 auto', paddingBottom: '60px' }}>
      
      {/* Header de la Página */}
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 800, letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <ShieldAlert size={28} style={{ color: 'var(--primary)' }} />
          Motor de Reglas QA/QC & Base Normativa Incorporada
        </h1>
        <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
          Gestión de documentos técnicos, normas y reglas estructuradas provenientes de Intake. Flujo en dos etapas: revisión de contenido documental y posterior promoción al Baseline QA/QC global del sistema.
        </p>
      </div>

      {/* Notificación de Promoción a Baseline */}
      {promotionNotification && (
        <div
          style={{
            backgroundColor: '#064e3b',
            borderColor: '#047857',
            color: '#a7f3d0',
            marginBottom: '24px',
            padding: '16px 20px',
            borderRadius: '12px',
            border: '1px solid #047857',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
          }}
          className="animate-in fade-in duration-200"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            <Award size={24} style={{ color: '#34d399' }} />
            <div>
              <div style={{ fontWeight: 700, fontSize: '14px' }}>
                ¡Reglas Promovidas a Baseline QA/QC del Sistema!
              </div>
              <div style={{ fontSize: '12px', opacity: 0.9 }}>
                {promotionNotification.message}
              </div>
            </div>
          </div>
          <button
            onClick={() => setPromotionNotification(null)}
            style={{ background: 'none', border: 'none', color: '#a7f3d0', cursor: 'pointer' }}
          >
            <X size={18} />
          </button>
        </div>
      )}

      {/* ========================================================= */}
      {/* SECCIÓN 1: DOCUMENTOS NORMATIVOS E INCORPORACIONES INTAKE */}
      {/* ========================================================= */}
      <div style={{ marginBottom: '36px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BookOpen size={20} style={{ color: 'var(--primary)' }} />
            <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
              Documentos Normativos & Fuentes Incorporados ({ruleDocuments.length})
            </h2>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary"
              onClick={() => setShowResearchCasesModal(true)}
              style={{
                padding: '5px 12px',
                fontSize: '12px',
                borderColor: '#a855f7',
                color: '#c084fc',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '6px'
              }}
              title="Abrir consola de investigación guiada por IA y curación HITL para símbolos desconocidos"
            >
              <Sparkles size={14} color="#c084fc" />
              <span>Casos de Investigación IA</span>
            </button>
            <button
              className="btn btn-secondary"
              onClick={loadRuleDocuments}
              style={{ padding: '5px 12px', fontSize: '12px' }}
            >
              <RefreshCw size={14} className={loadingDocs ? 'animate-spin' : ''} />
              <span>Actualizar Documentos</span>
            </button>
          </div>
        </div>

        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px 16px' }}>Título / Documento</th>
                <th style={{ padding: '12px 16px' }}>Tipo</th>
                <th style={{ padding: '12px 16px' }}>Origen</th>
                <th style={{ padding: '12px 16px' }}>Disciplina</th>
                <th style={{ padding: '12px 16px' }}>Reglas Asociadas</th>
                <th style={{ padding: '12px 16px' }}>Estado</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {ruleDocuments.length > 0 ? (
                ruleDocuments.map((doc) => (
                  <tr key={doc.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    
                    {/* Título y Descripción */}
                    <td style={{ padding: '14px 16px', maxWidth: '320px' }}>
                      <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>{doc.title}</div>
                      {doc.description && (
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px', lineHeight: '1.4' }}>
                          {doc.description}
                        </div>
                      )}
                      <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '4px', fontFamily: 'monospace' }}>
                        Autoridad: {doc.authority || 'N/A'} • v{doc.version}
                      </div>
                    </td>

                    {/* Tipo */}
                    <td style={{ padding: '14px 16px' }}>
                      <span className="badge badge-info uppercase" style={{ fontSize: '10px' }}>
                        {doc.document_type}
                      </span>
                    </td>

                    {/* Origen */}
                    <td style={{ padding: '14px 16px' }}>
                      {doc.source_origin === 'visor_de_planos' || doc.document_type === 'proyecto_evidencia' ? (
                        <span className="badge font-mono" style={{ fontSize: '10px', background: 'rgba(56, 189, 248, 0.15)', color: '#38bdf8', border: '1px solid rgba(56, 189, 248, 0.4)' }}>
                          📐 Visor Planos (Proyecto)
                        </span>
                      ) : doc.source_origin === 'con_ia_web' ? (
                        <span className="badge font-mono" style={{ fontSize: '10px', background: 'rgba(99, 102, 241, 0.15)', color: '#a5b4fc', border: '1px solid rgba(99, 102, 241, 0.4)' }}>
                          🌐 Con IA (Web)
                        </span>
                      ) : doc.source_origin === 'con_ia_documento' || doc.source_origin === 'con_ia' ? (
                        <span className="badge font-mono" style={{ fontSize: '10px', background: 'rgba(20, 184, 166, 0.15)', color: '#5eead4', border: '1px solid rgba(20, 184, 166, 0.4)' }}>
                          ✨ Con IA (Doc)
                        </span>
                      ) : (
                        <span className="badge badge-neutral font-mono" style={{ fontSize: '10px' }}>
                          ✍️ Sin IA (Manual)
                        </span>
                      )}
                    </td>

                    {/* Disciplina */}
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', fontWeight: 500, fontSize: '12px' }}>
                        <Tag size={11} color="var(--primary)" />
                        {doc.discipline}
                      </span>
                    </td>

                    {/* Reglas Asociadas */}
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '11px' }}>
                        <span style={{ color: '#38bdf8', fontWeight: 700 }}>{doc.rules_count} reglas validadas</span>
                        <div style={{ display: 'flex', gap: '6px', color: 'var(--text-dim)', fontSize: '10px', flexWrap: 'wrap' }}>
                          {doc.tables_count > 0 && <span>{doc.tables_count} tablas</span>}
                          {doc.images_count > 0 && <span>{doc.images_count} fig.</span>}
                          {(doc.symbols_count ?? 0) > 0 && (
                            <span style={{ color: '#c084fc', fontWeight: 600 }}>
                              🔘 {doc.symbols_count} símb.
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Estado del Documento */}
                    <td style={{ padding: '14px 16px' }}>
                      {getDocumentStatusBadge(doc.status)}
                    </td>

                    {/* Acciones del Renglón */}
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', alignItems: 'center', flexWrap: 'wrap' }}>
                        
                        {/* 0. BOTÓN "CURAR SÍMBOLOS" (Si el documento posee simbología identificada) */}
                        {(doc.symbols_count ?? 0) > 0 && (
                          <button
                            className="btn btn-secondary"
                            style={{
                              padding: '5px 10px',
                              fontSize: '11px',
                              borderColor: '#a855f7',
                              color: '#c084fc',
                              fontWeight: 600,
                              display: 'flex',
                              alignItems: 'center',
                              gap: '4px'
                            }}
                            onClick={() => setSelectedStudioDoc(doc)}
                            title="Abrir estudio de curación HITL para símbolos y leyendas de este documento"
                          >
                            <Sparkles size={13} color="#c084fc" />
                            <span>Curar Símb.</span>
                          </button>
                        )}

                        {/* 1. BOTÓN "CONTENIDO" (Abre ventana emergente reutilizando lógica de Intake) */}
                        <button
                          className="btn btn-secondary"
                          style={{
                            padding: '5px 10px',
                            fontSize: '11px',
                            borderColor: 'var(--primary)',
                            color: 'var(--primary)',
                            fontWeight: 600,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                          onClick={() => handleOpenContent(doc.id)}
                          title="Abrir ventana de reglas del documento para revisar, editar o confirmar"
                        >
                          <FolderOpen size={13} />
                          <span>Contenido</span>
                        </button>

                        {/* 2. BOTÓN DE PROMOCIÓN A BASELINE QA/QC */}
                        <button
                          className="btn btn-primary"
                          style={{
                            padding: '5px 12px',
                            fontSize: '11px',
                            backgroundColor: doc.status === 'promovido_baseline' ? '#047857' : '#0284c7',
                            borderColor: doc.status === 'promovido_baseline' ? '#059669' : '#0369a1',
                            fontWeight: 700,
                            display: 'flex',
                            alignItems: 'center',
                            gap: '4px'
                          }}
                          disabled={promotingDocId === doc.id || doc.rules_count === 0}
                          onClick={() => handlePromoteDocToBaseline(doc)}
                          title={
                            doc.status === 'promovido_baseline'
                              ? 'Volver a sincronizar reglas validadas hacia Baseline QA/QC'
                              : 'Promover y activar reglas validadas de este documento hacia Baseline QA/QC del Sistema'
                          }
                        >
                          <SquareCheck size={13} />
                          <span>{promotingDocId === doc.id ? 'Promoviendo...' : doc.status === 'promovido_baseline' ? 'Sincronizar Baseline' : 'Promover a Baseline QA/QC'}</span>
                        </button>

                        {/* 3. Eliminar Documento */}
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '5px 8px', fontSize: '11px', color: 'var(--danger)' }}
                          onClick={() => handleOpenDeleteModal(doc)}
                          title="Eliminar documento normativo"
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
                    No hay documentos incorporados. Puedes incorporar normas desde la sección <strong>Intake & Incorporación de Fuentes</strong> (con IA o sin IA).
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ========================================================= */}
      {/* SECCIÓN 2: REGLAS BASELINE DETERMINÍSTICAS DEL SISTEMA */}
      {/* ========================================================= */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <ShieldCheck size={22} style={{ color: '#38bdf8' }} />
            <div>
              <h2 style={{ fontSize: '18px', fontWeight: 700 }}>
                Reglas Baseline QA/QC del Sistema ({rules.length})
              </h2>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Catálogo activo de reglas normativas y determinísticas ejecutadas durante la auditoría de planos.
              </p>
            </div>
          </div>
          <button
            className="btn btn-secondary"
            onClick={loadRules}
            style={{ padding: '5px 12px', fontSize: '12px' }}
          >
            <RefreshCw size={14} className={loadingRules ? 'animate-spin' : ''} />
            <span>Actualizar Baseline</span>
          </button>
        </div>

        {ruleActionFeedback && (
          <div style={{
            padding: '10px 16px',
            marginBottom: '16px',
            borderRadius: '8px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            backgroundColor:
              ruleActionFeedback.type === 'success' ? 'rgba(16, 185, 129, 0.15)' :
              ruleActionFeedback.type === 'warning' ? 'rgba(245, 158, 11, 0.15)' : 'rgba(239, 68, 68, 0.15)',
            border: `1px solid ${
              ruleActionFeedback.type === 'success' ? 'rgba(16, 185, 129, 0.4)' :
              ruleActionFeedback.type === 'warning' ? 'rgba(245, 158, 11, 0.4)' : 'rgba(239, 68, 68, 0.4)'
            }`,
            color:
              ruleActionFeedback.type === 'success' ? '#6ee7b7' :
              ruleActionFeedback.type === 'warning' ? '#fcd34d' : '#fca5a5',
            fontSize: '13px'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {ruleActionFeedback.type === 'success' && <CheckCircle2 size={16} />}
              {ruleActionFeedback.type === 'warning' && <AlertCircle size={16} />}
              {ruleActionFeedback.type === 'error' && <AlertCircle size={16} />}
              <span>{ruleActionFeedback.message}</span>
            </div>
            <button
              onClick={() => setRuleActionFeedback(null)}
              style={{ background: 'none', border: 'none', color: 'inherit', cursor: 'pointer', padding: '2px' }}
            >
              <X size={14} />
            </button>
          </div>
        )}

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {rules.map((r) => {
            const isEnabled = r.enabled !== false && r.is_active !== false;
            const isPromoted = Boolean(
              r.source_document_id ||
              r.source_document_title ||
              r.input_requirements?.source_document_title ||
              r.input_requirements?.source_document_id
            );
            const sourceDocTitle = r.source_document_title || r.input_requirements?.source_document_title || 'Documento Normativo';
            const sourcePage = r.source_page ?? r.input_requirements?.source_page;
            return (
              <div
                key={r.id || r.code}
                className="card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  borderLeft: !isEnabled ? '4px solid #64748b' : (isPromoted ? '4px solid #10b981' : '4px solid var(--primary)'),
                  backgroundColor: 'var(--bg-card)',
                  opacity: isEnabled ? 1 : 0.75,
                }}
              >
                <div style={{ flex: 1, paddingRight: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                    <span className="font-mono" style={{ fontWeight: 700, color: isPromoted ? '#34d399' : 'var(--primary)', fontSize: '14px' }}>
                      {r.code}
                    </span>
                    <span style={{ fontWeight: 700, fontSize: '15px' }}>{r.name}</span>
                    <span className={`badge ${getSeverityBadge(r.severity_default)}`} style={{ fontSize: '10px' }}>
                      {r.severity_default.toUpperCase()}
                    </span>
                    <span className="badge badge-neutral" style={{ fontSize: '10px' }}>v{r.version}</span>
                    {isPromoted && (
                      <span className="badge font-mono" style={{ fontSize: '10px', background: 'rgba(16, 185, 129, 0.15)', color: '#6ee7b7', border: '1px solid rgba(16, 185, 129, 0.4)' }}>
                        ✓ Promovida desde: {sourceDocTitle}{sourcePage ? ` (Pág. ${sourcePage})` : ''}
                      </span>
                    )}
                  </div>
                  
                  <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '6px', lineHeight: '1.5' }}>
                    {r.description}
                  </div>

                  <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '8px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                    <span>Categoría: <strong>{r.category}</strong></span>
                    <span>Disciplina: <strong>{r.discipline}</strong></span>
                    <span>Lógica: <code>{r.rule_logic_type}</code></span>
                    {r.input_requirements?.authority && (
                      <span>Autoridad: <strong>{r.input_requirements.authority}</strong></span>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', minWidth: '170px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    {isEnabled ? (
                      <span className="badge badge-success" style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <CheckCircle2 size={12} />
                        Activa en Motor
                      </span>
                    ) : (
                      <span className="badge badge-neutral" style={{ display: 'flex', alignItems: 'center', gap: '4px', opacity: 0.8 }}>
                        <X size={12} />
                        Desactivada
                      </span>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <button
                      className="btn btn-secondary"
                      onClick={() => handleToggleRule(r.code, isEnabled)}
                      disabled={togglingRuleCode === r.code}
                      style={{
                        padding: '4px 8px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        borderColor: isEnabled ? '#f59e0b' : '#10b981',
                        color: isEnabled ? '#fbbf24' : '#34d399'
                      }}
                      title={isEnabled ? "Desactivar esta regla del Baseline QA/QC" : "Reactivar esta regla en el Baseline QA/QC"}
                    >
                      {togglingRuleCode === r.code ? (
                        <Loader2 size={12} className="animate-spin" />
                      ) : (
                        <Power size={12} />
                      )}
                      <span>{isEnabled ? 'Desactivar' : 'Reactivar'}</span>
                    </button>

                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        setDeletingRule(r);
                        setShowDeleteRuleModal(true);
                      }}
                      style={{
                        padding: '4px 8px',
                        fontSize: '11px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '4px',
                        borderColor: '#ef4444',
                        color: '#f87171'
                      }}
                      title="Eliminar regla del Baseline QA/QC"
                    >
                      <Trash2 size={12} />
                      <span>Eliminar</span>
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* VENTANA EMERGENTE FLOTANTE: "CONTENIDO" (Reutiliza lógica de reglas de Intake con fondo sólido oscuro) */}
      <DocumentContentReviewModal
        isOpen={showContentModal}
        ruleDocumentId={selectedRuleDocId}
        onClose={() => {
          setShowContentModal(false);
          setSelectedRuleDocId(null);
        }}
        onConfirmed={() => {
          loadRuleDocuments();
          loadRules();
        }}
      />

      {/* ESTUDIO DE CURACIÓN HITL DE SÍMBOLOS */}
      {selectedStudioDoc && (
        <SymbolCurationStudioModal
          isOpen={!!selectedStudioDoc}
          extractionId={selectedStudioDoc.source_extraction_id || null}
          ruleDocumentId={selectedStudioDoc.id}
          onClose={() => {
            setSelectedStudioDoc(null);
            loadRuleDocuments();
          }}
          onPromoted={() => {
            setSelectedStudioDoc(null);
            loadRuleDocuments();
          }}
        />
      )}

      {/* CONSOLA DE INVESTIGACIÓN IA & CURACIÓN HITL DE SÍMBOLOS DESCONOCIDOS */}
      <ResearchCasesPanel
        isOpen={showResearchCasesModal}
        onClose={() => setShowResearchCasesModal(false)}
        onCaseUpdated={() => {
          loadRuleDocuments();
        }}
      />

      {/* MODAL DE IMPACTO DE ELIMINACIÓN DE DOCUMENTO NORMATIVO */}
      {showDeleteModal && deletingDoc && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: 'var(--surface-color, #1e293b)',
            border: '1px solid var(--border-color, #334155)',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '560px',
            overflow: 'hidden',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            {/* Encabezado */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--border-color, #334155)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'rgba(239, 68, 68, 0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Trash2 size={20} style={{ color: '#ef4444' }} />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                  Eliminar Documento Normativo
                </h3>
              </div>
              <button
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeletingDoc(null);
                }}
                disabled={deletingInProgress}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted, #94a3b8)',
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Cuerpo */}
            <div style={{ padding: '20px', maxHeight: '70vh', overflowY: 'auto' }}>
              <div style={{ marginBottom: '16px' }}>
                <p style={{ margin: '0 0 6px 0', fontSize: '14px', color: '#f1f5f9', fontWeight: 600 }}>
                  {deletingDoc.title}
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Disciplina: <span style={{ color: '#38bdf8' }}>{deletingDoc.discipline || 'General'}</span> | Versión: {deletingDoc.version || 'N/A'}
                </p>
              </div>

              {loadingImpact ? (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '30px', gap: '10px', color: '#94a3b8' }}>
                  <Loader2 size={20} className="animate-spin" />
                  <span>Calculando impacto de eliminación...</span>
                </div>
              ) : deletionImpact ? (
                <div>
                  <div style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '12px',
                    marginBottom: '16px'
                  }}>
                    <div style={{
                      backgroundColor: 'rgba(15, 23, 42, 0.6)',
                      border: '1px solid #334155',
                      borderRadius: '8px',
                      padding: '12px'
                    }}>
                      <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase' }}>Ítems extraídos</div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: '#f8fafc' }}>{deletionImpact.total_items}</div>
                    </div>
                    <div style={{
                      backgroundColor: deletionImpact.promoted_rules_count > 0 ? 'rgba(234, 179, 8, 0.1)' : 'rgba(15, 23, 42, 0.6)',
                      border: deletionImpact.promoted_rules_count > 0 ? '1px solid rgba(234, 179, 8, 0.3)' : '1px solid #334155',
                      borderRadius: '8px',
                      padding: '12px'
                    }}>
                      <div style={{ fontSize: '11px', color: deletionImpact.promoted_rules_count > 0 ? '#facc15' : '#94a3b8', textTransform: 'uppercase' }}>
                        Reglas en Baseline QA/QC
                      </div>
                      <div style={{ fontSize: '18px', fontWeight: 700, color: deletionImpact.promoted_rules_count > 0 ? '#facc15' : '#f8fafc' }}>
                        {deletionImpact.promoted_rules_count}
                      </div>
                    </div>
                  </div>

                  {deletionImpact.promoted_rules_count > 0 ? (
                    <div style={{ marginBottom: '16px' }}>
                      <div style={{
                        padding: '10px 14px',
                        backgroundColor: 'rgba(234, 179, 8, 0.15)',
                        border: '1px solid rgba(234, 179, 8, 0.3)',
                        borderRadius: '6px',
                        color: '#fef08a',
                        fontSize: '12px',
                        marginBottom: '14px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '8px'
                      }}>
                        <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '2px', color: '#eab308' }} />
                        <div>
                          <strong>Atención:</strong> Este documento tiene reglas promovidas activas en el Baseline QA/QC del Sistema.
                          Seleccione la política de eliminación para asegurar la consistencia del sistema:
                        </div>
                      </div>

                      {/* Lista de reglas afectadas */}
                      <div style={{ marginBottom: '14px' }}>
                        <div style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8', marginBottom: '6px', textTransform: 'uppercase' }}>
                          Reglas afectadas ({deletionImpact.affected_rules.length}):
                        </div>
                        <div style={{ maxHeight: '120px', overflowY: 'auto', border: '1px solid #334155', borderRadius: '6px', backgroundColor: '#0f172a' }}>
                          {deletionImpact.affected_rules.map((r: any) => (
                            <div key={r.rule_id} style={{ padding: '6px 10px', borderBottom: '1px solid #1e293b', fontSize: '12px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <span style={{ fontWeight: 600, color: '#38bdf8' }}>{r.code}</span>
                              <span style={{ color: '#cbd5e1', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '300px' }}>{r.name}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Selector de política */}
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '14px' }}>
                        <label style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          padding: '10px',
                          borderRadius: '6px',
                          border: deletePolicy === 'keep_baseline_source_removed' ? '1px solid #38bdf8' : '1px solid #334155',
                          backgroundColor: deletePolicy === 'keep_baseline_source_removed' ? 'rgba(56, 189, 248, 0.1)' : 'transparent',
                          cursor: 'pointer'
                        }}>
                          <input
                            type="radio"
                            name="delete_policy"
                            value="keep_baseline_source_removed"
                            checked={deletePolicy === 'keep_baseline_source_removed'}
                            onChange={() => setDeletePolicy('keep_baseline_source_removed')}
                            style={{ marginTop: '3px' }}
                          />
                          <div>
                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                              Conservar reglas en Baseline QA/QC (Recomendado)
                            </div>
                            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                              Mantiene las reglas en Baseline marcando su trazabilidad como "fuente retirada". One-Click Review seguirá funcionando normalmente.
                            </div>
                          </div>
                        </label>

                        <label style={{
                          display: 'flex',
                          alignItems: 'flex-start',
                          gap: '10px',
                          padding: '10px',
                          borderRadius: '6px',
                          border: deletePolicy === 'retire_rules' ? '1px solid #ef4444' : '1px solid #334155',
                          backgroundColor: deletePolicy === 'retire_rules' ? 'rgba(239, 68, 68, 0.1)' : 'transparent',
                          cursor: 'pointer'
                        }}>
                          <input
                            type="radio"
                            name="delete_policy"
                            value="retire_rules"
                            checked={deletePolicy === 'retire_rules'}
                            onChange={() => setDeletePolicy('retire_rules')}
                            style={{ marginTop: '3px' }}
                          />
                          <div>
                            <div style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                              Desactivar / retirar reglas del Baseline QA/QC
                            </div>
                            <div style={{ fontSize: '11px', color: '#94a3b8' }}>
                              Desactiva las reglas asociadas en el Baseline QA/QC para que no sean evaluadas en futuros One-Click Reviews.
                            </div>
                          </div>
                        </label>
                      </div>
                    </div>
                  ) : (
                    <div style={{
                      padding: '10px 14px',
                      backgroundColor: 'rgba(34, 197, 94, 0.1)',
                      border: '1px solid rgba(34, 197, 94, 0.25)',
                      borderRadius: '6px',
                      color: '#86efac',
                      fontSize: '12px',
                      marginBottom: '16px'
                    }}>
                      ✓ Este documento no tiene reglas promovidas al Baseline QA/QC. Se puede eliminar de forma segura sin impacto en revisiones.
                    </div>
                  )}
                </div>
              ) : null}
            </div>

            {/* Pie de acciones */}
            <div style={{
              padding: '14px 20px',
              borderTop: '1px solid var(--border-color, #334155)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '10px',
              backgroundColor: 'rgba(15, 23, 42, 0.4)'
            }}>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowDeleteModal(false);
                  setDeletingDoc(null);
                }}
                disabled={deletingInProgress}
              >
                Cancelar
              </button>
              <button
                className="btn btn-danger"
                style={{ backgroundColor: '#dc2626', color: 'white', display: 'flex', alignItems: 'center', gap: '6px' }}
                onClick={handleConfirmDelete}
                disabled={deletingInProgress || loadingImpact}
              >
                {deletingInProgress ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Eliminando...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Eliminar Documento</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MODAL DE CONFIRMACIÓN DE ELIMINACIÓN DE REGLA BASELINE */}
      {showDeleteRuleModal && deletingRule && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.75)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 9999,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: 'var(--surface-color, #1e293b)',
            border: '1px solid var(--border-color, #334155)',
            borderRadius: '12px',
            width: '100%',
            maxWidth: '520px',
            overflow: 'hidden',
            boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)'
          }}>
            {/* Encabezado */}
            <div style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--border-color, #334155)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              backgroundColor: 'rgba(239, 68, 68, 0.1)'
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Trash2 size={20} style={{ color: '#ef4444' }} />
                <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 600, color: '#f8fafc' }}>
                  Eliminar Regla del Baseline QA/QC
                </h3>
              </div>
              <button
                onClick={() => {
                  setShowDeleteRuleModal(false);
                  setDeletingRule(null);
                }}
                disabled={deletingRuleInProgress}
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--text-muted, #94a3b8)',
                  cursor: 'pointer',
                  padding: '4px'
                }}
              >
                <X size={18} />
              </button>
            </div>

            {/* Cuerpo */}
            <div style={{ padding: '20px' }}>
              <div style={{ marginBottom: '16px' }}>
                <span className="font-mono" style={{ fontSize: '13px', color: '#a855f7', fontWeight: 700 }}>
                  {deletingRule.code}
                </span>
                <p style={{ margin: '4px 0 6px 0', fontSize: '15px', color: '#f1f5f9', fontWeight: 600 }}>
                  {deletingRule.name}
                </p>
                <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                  Disciplina: <span style={{ color: '#38bdf8' }}>{deletingRule.discipline}</span> | Categoría: {deletingRule.category}
                </p>
              </div>

              <div style={{
                backgroundColor: 'rgba(239, 68, 68, 0.08)',
                border: '1px solid rgba(239, 68, 68, 0.25)',
                borderRadius: '8px',
                padding: '12px 14px',
                fontSize: '13px',
                color: '#fca5a5',
                lineHeight: '1.5'
              }}>
                <strong>Atención:</strong> Si esta regla no tiene histórico se eliminará físicamente de la base de datos. Si cuenta con ejecuciones o hallazgos previos, el sistema la desactivará permanentemente de forma segura para preservar la trazabilidad de auditoría.
              </div>
            </div>

            {/* Acciones */}
            <div style={{
              padding: '14px 20px',
              borderTop: '1px solid var(--border-color, #334155)',
              display: 'flex',
              justifyContent: 'flex-end',
              gap: '10px',
              backgroundColor: 'rgba(15, 23, 42, 0.4)'
            }}>
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setShowDeleteRuleModal(false);
                  setDeletingRule(null);
                }}
                disabled={deletingRuleInProgress}
                style={{ padding: '6px 14px', fontSize: '13px' }}
              >
                Cancelar
              </button>
              <button
                onClick={handleConfirmDeleteRule}
                disabled={deletingRuleInProgress}
                style={{
                  backgroundColor: '#dc2626',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '6px 16px',
                  fontSize: '13px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  cursor: deletingRuleInProgress ? 'not-allowed' : 'pointer',
                  opacity: deletingRuleInProgress ? 0.7 : 1
                }}
              >
                {deletingRuleInProgress ? (
                  <>
                    <Loader2 size={14} className="animate-spin" />
                    <span>Eliminando...</span>
                  </>
                ) : (
                  <>
                    <Trash2 size={14} />
                    <span>Confirmar Eliminación</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
