import React, { useEffect, useState } from 'react';
import { apiService } from '../services/api';
import { AuditReportItem, EvidenceManifestItem, DocumentItem } from '../types';
import {
  FileText, Download, ShieldCheck, CheckCircle2, AlertTriangle,
  Play, RefreshCw, FileArchive, Hash, ExternalLink, Clock, FolderKanban,
  Layers, SquareCheck
} from 'lucide-react';
import { ConsolidatedStageReportView } from '../components/ConsolidatedStageReportView';
import { AssistantCopilotDrawer } from '../components/AssistantCopilotDrawer';
import { Bot, Sparkles } from 'lucide-react';

export const ReportsPage: React.FC = () => {
  const [activeSubTab, setActiveSubTab] = useState<'stage_consolidated' | 'sheet_reports'>('stage_consolidated');
  const [reports, setReports] = useState<AuditReportItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<AuditReportItem | null>(null);
  const [manifest, setManifest] = useState<EvidenceManifestItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [targetSheetId, setTargetSheetId] = useState<string>('');
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [reps, docs] = await Promise.all([
        apiService.getReports(),
        apiService.getDocuments()
      ]);
      setReports(reps);
      setDocuments(docs);
      if (docs.length > 0 && docs[0].sheets && docs[0].sheets.length > 0) {
        setTargetSheetId(docs[0].sheets[0].id);
      }
      if (reps.length > 0) {
        handleSelectReport(reps[0]);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectReport = async (rep: AuditReportItem) => {
    setSelectedReport(rep);
    try {
      const man = await apiService.getReportManifest(rep.id);
      setManifest(man);
    } catch (e) {
      console.error(e);
      setManifest(null);
    }
  };

  const handleGenerateSheetReport = async () => {
    if (!targetSheetId) return;
    try {
      setGenerating(true);
      const newRep = await apiService.generateSheetReport(targetSheetId, 'technical_audit_qaqc', 'auditor_senior');
      await loadData();
      alert(`Informe técnico generado exitosamente: ID ${newRep.id.substring(0, 8)}`);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al generar reporte técnico.');
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="page-container">
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <FileText size={24} style={{ color: 'var(--primary)' }} />
            Informes Técnicos de Auditoría & Reporte Consolidado
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Consolidación formal por etapa, trazabilidad de completitud, 4 veredictos y exportaciones PDF/JSON con hash SHA-256.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          {/* Sub-tab Switcher */}
          <div style={{ display: 'flex', gap: '8px', background: 'var(--bg-card)', padding: '4px 8px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              className={`btn ${activeSubTab === 'stage_consolidated' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setActiveSubTab('stage_consolidated')}
            >
              <Layers size={14} /> Reporte Consolidado por Etapa
            </button>
            <button
              className={`btn ${activeSubTab === 'sheet_reports' ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
              onClick={() => setActiveSubTab('sheet_reports')}
            >
              <FileText size={14} /> Informes por Lámina ({reports.length})
            </button>
          </div>

          <button
            className="btn btn-primary"
            style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, background: 'linear-gradient(135deg, var(--primary), var(--accent))' }}
            onClick={() => setIsCopilotOpen(true)}
          >
            <Sparkles size={16} /> Asistente de Síntesis
          </button>
        </div>
      </div>

      <AssistantCopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        initialTaskType="stage_synthesis"
      />

      {activeSubTab === 'stage_consolidated' ? (
        <ConsolidatedStageReportView />
      ) : (
        <>
          {/* Acción de Generación Rápida de Informe por Lámina */}
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center', marginBottom: '20px', background: 'var(--bg-card)', padding: '12px 16px', borderRadius: '12px', border: '1px solid var(--border-subtle)' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-dim)' }}>Generar Informe Individual:</span>
            <select
              value={targetSheetId}
              onChange={(e) => setTargetSheetId(e.target.value)}
              style={{
                background: 'var(--bg-sidebar)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '6px 12px',
                fontSize: '13px',
                flex: 1
              }}
            >
              {documents.map((doc) =>
                (doc.sheets || []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {doc.filename} — {s.sheet_code || `Lámina #${s.sheet_number}`}
                  </option>
                ))
              )}
            </select>

            <button
              className="btn btn-primary"
              onClick={handleGenerateSheetReport}
              disabled={generating || !targetSheetId}
            >
              <Play size={14} className={generating ? 'animate-spin' : ''} />
              <span>{generating ? 'Generando...' : 'Generar Informe PDF & Bundle'}</span>
            </button>
          </div>

          {/* Grid Principal: Listado a la Izquierda, Inspector a la Derecha */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 440px', gap: '20px' }}>
        
        {/* Tabla de Reportes Generados */}
        <div className="card" style={{ overflowX: 'auto' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '14px' }}>
            Historial de Informes de Auditoría ({reports.length})
          </h2>

          {reports.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '30px', color: 'var(--text-dim)' }}>
              <FileText size={36} style={{ margin: '0 auto 10px', opacity: 0.4 }} />
              <div>No hay informes de auditoría generados todavía.</div>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-subtle)', textAlign: 'left', color: 'var(--text-dim)' }}>
                  <th style={{ padding: '8px' }}>Reporte</th>
                  <th style={{ padding: '8px' }}>Alcance</th>
                  <th style={{ padding: '8px' }}>Hallazgos</th>
                  <th style={{ padding: '8px' }}>Fecha UTC</th>
                  <th style={{ padding: '8px', textAlign: 'right' }}>Descargas</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((r) => {
                  const isSelected = selectedReport?.id === r.id;
                  const crit = r.summary?.by_severity?.critical || 0;
                  const high = r.summary?.by_severity?.high || 0;

                  return (
                    <tr
                      key={r.id}
                      onClick={() => handleSelectReport(r)}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                        cursor: 'pointer'
                      }}
                    >
                      <td style={{ padding: '10px 8px' }}>
                        <div style={{ fontWeight: 700, color: 'var(--text-main)' }}>
                          {r.report_type.replace('_', ' ').toUpperCase()}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-dim)' }} className="font-mono">
                          ID: {r.id.substring(0, 8)}...
                        </div>
                      </td>

                      <td style={{ padding: '10px 8px' }}>
                        <span className="badge badge-neutral" style={{ textTransform: 'uppercase', fontSize: '10px' }}>
                          {r.report_scope}
                        </span>
                      </td>

                      <td style={{ padding: '10px 8px' }}>
                        <div style={{ display: 'flex', gap: '4px' }}>
                          {crit > 0 && <span className="badge badge-danger" style={{ fontSize: '10px' }}>{crit} Crit</span>}
                          {high > 0 && <span className="badge badge-warning" style={{ fontSize: '10px' }}>{high} Alto</span>}
                          <span className="badge badge-info" style={{ fontSize: '10px' }}>{r.summary?.total_findings || 0} Total</span>
                        </div>
                      </td>

                      <td style={{ padding: '10px 8px', color: 'var(--text-dim)', fontSize: '11px' }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString() : 'N/A'}
                      </td>

                      <td style={{ padding: '10px 8px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                          <a
                            href={apiService.getReportDownloadPdfUrl(r.id)}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Descargar PDF"
                          >
                            <FileText size={12} /> PDF
                          </a>
                          <a
                            href={apiService.getReportDownloadJsonUrl(r.id)}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Descargar JSON"
                          >
                            JSON
                          </a>
                          <a
                            href={apiService.getReportDownloadBundleUrl(r.id)}
                            target="_blank"
                            rel="noreferrer"
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px' }}
                            title="Descargar Paquete ZIP"
                          >
                            <FileArchive size={12} /> ZIP
                          </a>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Panel Lateral: Manifiesto de Integridad y Detalles */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <h2 style={{ fontSize: '16px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Hash size={16} style={{ color: 'var(--primary)' }} />
            Manifiesto de Integridad SHA-256
          </h2>

          {selectedReport ? (
            <div>
              <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '12px', lineHeight: '1.6' }}>
                <div><strong>ID Reporte:</strong> <span className="font-mono" style={{ color: 'var(--primary)' }}>{selectedReport.id}</span></div>
                <div><strong>Alcance:</strong> {selectedReport.report_scope.toUpperCase()} • <strong>Autor:</strong> {selectedReport.generated_by}</div>
                <div><strong>Hash Manifiesto:</strong> <code style={{ fontSize: '10px' }}>{selectedReport.manifest_hash || 'Calculado'}</code></div>
              </div>

              {manifest && (
                <div style={{ marginTop: '14px' }}>
                  <h3 style={{ fontSize: '13px', fontWeight: 700, marginBottom: '8px', color: 'var(--text-dim)' }}>
                    Archivos en el Bundle ({manifest.manifest_json.files.length})
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '300px', overflowY: 'auto' }}>
                    {manifest.manifest_json.files.map((file) => (
                      <div
                        key={file.path}
                        style={{
                          background: 'var(--bg-sidebar)',
                          padding: '8px 10px',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                          fontSize: '11px'
                        }}
                      >
                        <div style={{ fontWeight: 700, color: 'var(--text-main)', marginBottom: '2px' }}>
                          📄 {file.path} ({file.size_bytes} bytes)
                        </div>
                        <div style={{ color: 'var(--text-dim)', fontSize: '10px', wordBreak: 'break-all' }} className="font-mono">
                          SHA256: {file.sha256}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div style={{ color: 'var(--text-dim)', fontSize: '12px', textAlign: 'center', padding: '20px' }}>
              Seleccione un reporte para inspeccionar su integridad.
            </div>
          )}
          </div>
        </div>
      </>
    )}
  </div>
);
};
