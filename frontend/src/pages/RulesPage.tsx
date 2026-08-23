import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { RuleDefinitionItem, RuleDocument } from '../types';
import {
  ShieldAlert, Sparkles, BookOpen, Layers, Check, Trash2,
  FolderOpen, Plus, Tag, RefreshCw, FileText, CheckCircle2,
  AlertCircle, Table as TableIcon, X, ArrowUpRight, ShieldCheck,
  SquareCheck, ExternalLink, Award
} from 'lucide-react';
import { DocumentContentReviewModal } from '../components/DocumentContentReviewModal';

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

  const handleDeleteDoc = async (docId: string) => {
    if (!window.confirm('¿Está seguro de eliminar este documento normativo y sus reglas asociadas?')) return;
    try {
      await apiService.deleteRuleDocument(docId);
      loadRuleDocuments();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Error al eliminar documento.');
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
          <button
            className="btn btn-secondary"
            onClick={loadRuleDocuments}
            style={{ padding: '5px 12px', fontSize: '12px' }}
          >
            <RefreshCw size={14} className={loadingDocs ? 'animate-spin' : ''} />
            <span>Actualizar Documentos</span>
          </button>
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
                        <div style={{ display: 'flex', gap: '6px', color: 'var(--text-dim)', fontSize: '10px' }}>
                          {doc.tables_count > 0 && <span>{doc.tables_count} tablas</span>}
                          {doc.images_count > 0 && <span>{doc.images_count} fig.</span>}
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

                        {/* 2. BOTÓN "ACEPTAR" DEL RENGLÓN (Promueve a Baseline QA/QC) */}
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
                              : 'Promover reglas confirmadas de este documento hacia las Reglas Baseline QA/QC'
                          }
                        >
                          <SquareCheck size={13} />
                          <span>{promotingDocId === doc.id ? 'Promoviendo...' : doc.status === 'promovido_baseline' ? 'Sincronizar Baseline' : 'Aceptar'}</span>
                        </button>

                        {/* 3. Eliminar Documento */}
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '5px 8px', fontSize: '11px', color: 'var(--danger)' }}
                          onClick={() => handleDeleteDoc(doc.id)}
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

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {rules.map((r) => {
            const isPromoted = Boolean(r.input_requirements?.source_document_title || r.input_requirements?.source_document_id);
            return (
              <div
                key={r.id || r.code}
                className="card"
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'flex-start',
                  borderLeft: isPromoted ? '4px solid #10b981' : '4px solid var(--primary)',
                  backgroundColor: 'var(--bg-card)',
                }}
              >
                <div>
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
                        ✓ Promovida desde: {r.input_requirements?.source_document_title || 'Documento Normativo'}
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

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="badge badge-success">Activa en Motor</span>
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
        }}
      />
    </div>
  );
};
