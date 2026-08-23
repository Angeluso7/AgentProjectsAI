import React, { useState, useEffect } from 'react';
import {
  FileText, Download, ShieldCheck, CheckCircle2, AlertTriangle,
  Play, RefreshCw, Lock, HelpCircle, Info, Clock, ArrowRight,
  Send, Layers, SquareCheck, XCircle, FileCode, ChevronRight,
  Sparkles, Filter, ExternalLink, Calendar, User, Compass
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  ConsolidatedStageReportItem, ProjectStageReportSnapshotSummary,
  GlobalStageVerdict, ObservationType, ObservationStatus
} from '../types';
import { useProject } from '../context/ProjectContext';
import { ProjectMaturityProfileView } from './ProjectMaturityProfileView';

export const ConsolidatedStageReportView: React.FC = () => {
  const { activeProject, activeProjectId } = useProject();

  const [reportData, setReportData] = useState<ConsolidatedStageReportItem | null>(null);
  const [snapshots, setSnapshots] = useState<ProjectStageReportSnapshotSummary[]>([]);
  const [selectedSnapshotId, setSelectedSnapshotId] = useState<string>('live_preview');
  const [activeTab, setActiveTab] = useState<'overview' | 'maturity' | 'completeness' | 'verdicts' | 'observations' | 'delta'>('overview');

  const [loading, setLoading] = useState<boolean>(true);
  const [emitting, setEmitting] = useState<boolean>(false);
  const [isEmitModalOpen, setIsEmitModalOpen] = useState<boolean>(false);
  const [emissionTitle, setEmissionTitle] = useState<string>('');
  const [emissionNotes, setEmissionNotes] = useState<string>('');

  useEffect(() => {
    if (activeProjectId) {
      loadSnapshotsAndReport();
    }
  }, [activeProjectId]);

  const loadSnapshotsAndReport = async () => {
    if (!activeProjectId) return;
    setLoading(true);
    try {
      const snapList = await apiService.getStageReportSnapshots(activeProjectId);
      setSnapshots(snapList);

      if (selectedSnapshotId === 'live_preview') {
        const preview = await apiService.getConsolidatedReportPreview(activeProjectId);
        setReportData(preview);
      } else {
        const snap = await apiService.getStageReportSnapshotDetail(selectedSnapshotId);
        setReportData(snap);
      }
    } catch (err) {
      console.error('Error cargando reporte consolidado:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSnapshot = async (id: string) => {
    setSelectedSnapshotId(id);
    setLoading(true);
    try {
      if (id === 'live_preview') {
        if (!activeProjectId) return;
        const preview = await apiService.getConsolidatedReportPreview(activeProjectId);
        setReportData(preview);
      } else {
        const snap = await apiService.getStageReportSnapshotDetail(id);
        setReportData(snap);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEmitSnapshot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeProjectId) return;
    setEmitting(true);
    try {
      const emitted = await apiService.emitConsolidatedStageReport({
        project_id: activeProjectId,
        title: emissionTitle || undefined,
        notes: emissionNotes || undefined
      });
      setIsEmitModalOpen(false);
      setEmissionTitle('');
      setEmissionNotes('');
      alert(`Snapshot Rev ${emitted.revision_number} emitido exitosamente.`);
      await loadSnapshotsAndReport();
      setSelectedSnapshotId(emitted.id || 'live_preview');
      setReportData(emitted);
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al emitir snapshot.');
    } finally {
      setEmitting(false);
    }
  };

  const handleDownloadPdf = () => {
    if (!reportData?.id) {
      alert('Para descargar el PDF oficial primero emita un Snapshot formal.');
      return;
    }
    const url = apiService.getSnapshotPdfDownloadUrl(reportData.id);
    window.open(url, '_blank');
  };

  const handleDownloadJson = () => {
    if (!reportData?.id) {
      // Export live preview JSON directly
      const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `auditoria_consolidada_${reportData?.project_code || 'PRJ'}_live.json`;
      a.click();
      return;
    }
    const url = apiService.getSnapshotJsonDownloadUrl(reportData.id);
    window.open(url, '_blank');
  };

  const getVerdictBanner = (verdict: GlobalStageVerdict, rationale: string) => {
    switch (verdict) {
      case 'aprobable':
        return (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-950/80 via-emerald-900/40 to-slate-900 border border-emerald-500/50 shadow-xl shadow-emerald-950/40 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-emerald-500/20 border border-emerald-400/40 rounded-xl text-emerald-400">
                  <CheckCircle2 className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-emerald-400">Veredicto Global de la Etapa</div>
                  <div className="text-lg font-black text-white">ETAPA APROBABLE</div>
                </div>
              </div>
              <span className="px-3 py-1 bg-emerald-500/20 text-emerald-300 font-mono text-xs font-bold rounded-lg border border-emerald-500/40">
                100% CUMPLIMIENTO
              </span>
            </div>
            <p className="text-xs text-emerald-200/90 leading-relaxed pl-12">{rationale}</p>
          </div>
        );

      case 'aprobable_con_observaciones':
        return (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-amber-950/80 via-amber-900/40 to-slate-900 border border-amber-500/50 shadow-xl shadow-amber-950/40 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-amber-500/20 border border-amber-400/40 rounded-xl text-amber-400">
                  <AlertTriangle className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-amber-400">Veredicto Global de la Etapa</div>
                  <div className="text-lg font-black text-white">ETAPA APROBABLE CON OBSERVACIONES</div>
                </div>
              </div>
              <span className="px-3 py-1 bg-amber-500/20 text-amber-300 font-mono text-xs font-bold rounded-lg border border-amber-500/40">
                CON REPAROS MENORES
              </span>
            </div>
            <p className="text-xs text-amber-200/90 leading-relaxed pl-12">{rationale}</p>
          </div>
        );

      case 'parcial_incompleta':
        return (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-purple-950/80 via-purple-900/40 to-slate-900 border border-purple-500/50 shadow-xl shadow-purple-950/40 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-purple-500/20 border border-purple-400/40 rounded-xl text-purple-400">
                  <HelpCircle className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-purple-400">Veredicto Global de la Etapa</div>
                  <div className="text-lg font-black text-white">ETAPA EN REVISIÓN PARCIAL / INCOMPLETA</div>
                </div>
              </div>
              <span className="px-3 py-1 bg-purple-500/20 text-purple-300 font-mono text-xs font-bold rounded-lg border border-purple-500/40">
                RFIs / ENTREGABLES PENDIENTES
              </span>
            </div>
            <p className="text-xs text-purple-200/90 leading-relaxed pl-12">{rationale}</p>
          </div>
        );

      default: // no_aprobable_bloqueada
        return (
          <div className="p-5 rounded-2xl bg-gradient-to-r from-rose-950/80 via-rose-900/40 to-slate-900 border border-rose-500/50 shadow-xl shadow-rose-950/40 space-y-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 bg-rose-500/20 border border-rose-400/40 rounded-xl text-rose-400">
                  <Lock className="w-6 h-6" />
                </div>
                <div>
                  <div className="text-xs font-bold uppercase tracking-wider text-rose-400">Veredicto Global de la Etapa</div>
                  <div className="text-lg font-black text-white">ETAPA NO APROBABLE / BLOQUEADA</div>
                </div>
              </div>
              <span className="px-3 py-1 bg-rose-500/20 text-rose-300 font-mono text-xs font-bold rounded-lg border border-rose-500/40">
                BLOQUEO DOCUMENTAL / CRÍTICO
              </span>
            </div>
            <p className="text-xs text-rose-200/90 leading-relaxed pl-12">{rationale}</p>
          </div>
        );
    }
  };

  const getVerdictTag = (verdict: string) => {
    switch (verdict) {
      case 'cumple':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">CUMPLE</span>;
      case 'no_cumple':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-950 text-rose-300 border border-rose-700">NO CUMPLE</span>;
      case 'no_verificable':
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950 text-amber-300 border border-amber-700">NO VERIFICABLE</span>;
      default:
        return <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-slate-800 text-slate-400 border border-slate-700">NO APLICA</span>;
    }
  };

  if (!activeProject) {
    return (
      <div className="p-8 text-center bg-slate-900 border border-slate-800 rounded-2xl">
        <FileText className="w-10 h-10 mx-auto text-slate-600 mb-3" />
        <p className="text-sm font-semibold text-slate-300">Seleccione un proyecto activo para visualizar el Reporte Consolidado por Etapa.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Control Bar: Snapshot Switcher & Action Buttons */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl flex flex-wrap items-center justify-between gap-4 shadow-lg">
        <div className="flex items-center gap-3">
          <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Corte / Emisión:</label>
          <select
            value={selectedSnapshotId}
            onChange={(e) => handleSelectSnapshot(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs font-medium rounded-xl px-3.5 py-2 focus:outline-none focus:border-indigo-500 shadow-inner"
          >
            <option value="live_preview">⚡ Vista Previa en Vivo (Estado Actual)</option>
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>
                📦 Rev {s.revision_number} — {s.title} ({new Date(s.created_at).toLocaleDateString()})
              </option>
            ))}
          </select>

          {reportData?.is_live_preview ? (
            <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-indigo-950/80 text-indigo-300 border border-indigo-700/60 animate-pulse flex items-center gap-1.5">
              <Sparkles className="w-3 h-3" /> Tiempo Real
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded-md text-[11px] font-bold bg-slate-800 text-slate-300 border border-slate-700 font-mono">
              Snapshot Rev {reportData?.revision_number}
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => loadSnapshotsAndReport()}
            disabled={loading}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refrescar</span>
          </button>

          <button
            onClick={() => setIsEmitModalOpen(true)}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-lg shadow-indigo-600/30 transition"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Emitir Snapshot Formal</span>
          </button>

          <button
            onClick={handleDownloadPdf}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition"
          >
            <Download className="w-3.5 h-3.5 text-rose-400" />
            <span>PDF</span>
          </button>

          <button
            onClick={handleDownloadJson}
            className="px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-xl text-xs font-semibold flex items-center gap-1.5 border border-slate-700 transition"
          >
            <FileCode className="w-3.5 h-3.5 text-blue-400" />
            <span>JSON</span>
          </button>
        </div>
      </div>

      {loading || !reportData ? (
        <div className="py-20 text-center text-slate-400 text-xs flex items-center justify-center gap-2">
          <RefreshCw className="w-5 h-5 animate-spin text-indigo-400" />
          <span>Calculando reporte consolidado de etapa...</span>
        </div>
      ) : (
        <>
          {/* Global Stage Verdict Banner */}
          {getVerdictBanner(reportData.global_stage_verdict, reportData.verdict_rationale)}

          {/* Sub-Navigation Tabs */}
          <div className="flex border-b border-slate-800 text-xs font-semibold gap-2 flex-wrap">
            <button
              onClick={() => setActiveTab('overview')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'overview' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <FileText className="w-4 h-4" /> Resumen Ejecutivo
            </button>
            <button
              onClick={() => setActiveTab('maturity')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'maturity' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <Compass className="w-4 h-4" /> Madurez & Suficiencia Informacional
            </button>
            <button
              onClick={() => setActiveTab('completeness')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'completeness' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <SquareCheck className="w-4 h-4" /> Completitud & Gatekeeper ({reportData.completeness.completeness_percentage.toFixed(0)}%)
            </button>
            <button
              onClick={() => setActiveTab('verdicts')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'verdicts' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <ShieldCheck className="w-4 h-4" /> 4 Veredictos QA/QC ({reportData.audit_verdicts.total_rules_evaluated})
            </button>
            <button
              onClick={() => setActiveTab('observations')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'observations' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <AlertTriangle className="w-4 h-4" /> Observaciones & RFIs ({reportData.observations.items.length})
            </button>
            <button
              onClick={() => setActiveTab('delta')}
              className={`pb-3 px-3 border-b-2 transition flex items-center gap-1.5 ${activeTab === 'delta' ? 'border-indigo-500 text-indigo-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              <Clock className="w-4 h-4" /> Evolución Delta
            </button>
          </div>

          {/* TAB 0: PERFIL DE MADUREZ & SUFICIENCIA INFORMACIONAL */}
          {activeTab === 'maturity' && (
            <ProjectMaturityProfileView />
          )}

          {/* TAB 1: RESUMEN EJECUTIVO & KPIS */}
          {activeTab === 'overview' && (
            <div className="space-y-6">
              {/* KPI Strip */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <div className="text-xs text-slate-400 font-medium uppercase">Completitud Documental</div>
                  <div className="text-2xl font-bold text-white mt-1">{reportData.completeness.completeness_percentage.toFixed(1)}%</div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {reportData.completeness.eligible_count} de {reportData.completeness.total_required_count} entregables aptos
                  </div>
                </div>

                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <div className="text-xs text-slate-400 font-medium uppercase">Gatekeeper de Etapa</div>
                  <div className={`text-xl font-bold mt-1 ${reportData.completeness.is_gate_passed ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {reportData.completeness.is_gate_passed ? 'SUPERADO' : 'BLOQUEADO'}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {reportData.completeness.blocked_rules_count} reglas bloqueadas
                  </div>
                </div>

                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <div className="text-xs text-slate-400 font-medium uppercase">Auditoría Determinística</div>
                  <div className="text-2xl font-bold text-white mt-1">{reportData.audit_verdicts.total_rules_evaluated}</div>
                  <div className="text-[11px] text-emerald-400 mt-1">
                    {reportData.audit_verdicts.cumple_count} CUMPLE • {reportData.audit_verdicts.no_cumple_count} NO CUMPLE
                  </div>
                </div>

                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl">
                  <div className="text-xs text-slate-400 font-medium uppercase">Observaciones & RFIs</div>
                  <div className="text-2xl font-bold text-amber-400 mt-1">
                    {reportData.observations.open_obs + reportData.observations.open_rfi + reportData.observations.active_blk}
                  </div>
                  <div className="text-[11px] text-slate-500 mt-1">
                    {reportData.observations.closed_obs + reportData.observations.closed_rfi + reportData.observations.resolved_blk} resueltas
                  </div>
                </div>
              </div>

              {/* Context Summary Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                  <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wider">Contexto del Proyecto & Emisión</h3>
                  <div className="space-y-1.5 text-xs text-slate-300">
                    <div><span className="text-slate-500">Proyecto:</span> <strong>{reportData.project_name}</strong> ({reportData.project_code})</div>
                    <div><span className="text-slate-500">Etapa Auditada:</span> <strong className="text-indigo-300">{reportData.stage}</strong></div>
                    <div><span className="text-slate-500">Revisión:</span> <strong className="font-mono">Rev {reportData.revision_number}</strong></div>
                    <div><span className="text-slate-500">Emitido Por:</span> <span>{reportData.issued_by}</span></div>
                    {reportData.manifest_hash && (
                      <div className="pt-2 text-[10px] font-mono text-slate-500 break-all">
                        SHA-256: {reportData.manifest_hash}
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                  <h3 className="font-bold text-xs text-slate-200 uppercase tracking-wider">Desglose de 4 Veredictos</h3>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="p-2.5 rounded-lg bg-emerald-950/40 border border-emerald-800/40">
                      <div className="text-emerald-400 font-bold text-lg">{reportData.audit_verdicts.cumple_count}</div>
                      <div className="text-[11px] text-slate-300 font-medium">CUMPLE</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/40">
                      <div className="text-rose-400 font-bold text-lg">{reportData.audit_verdicts.no_cumple_count}</div>
                      <div className="text-[11px] text-slate-300 font-medium">NO CUMPLE</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/40">
                      <div className="text-amber-400 font-bold text-lg">{reportData.audit_verdicts.no_verificable_count}</div>
                      <div className="text-[11px] text-slate-300 font-medium">NO VERIFICABLE</div>
                    </div>
                    <div className="p-2.5 rounded-lg bg-slate-800/60 border border-slate-700/60">
                      <div className="text-slate-300 font-bold text-lg">{reportData.audit_verdicts.no_aplica_count}</div>
                      <div className="text-[11px] text-slate-400 font-medium">NO APLICA</div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: COMPLETITUD & GATEKEEPER */}
          {activeTab === 'completeness' && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Matriz de Entregables Requeridos para {reportData.stage}
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  {reportData.completeness.eligible_count} / {reportData.completeness.total_required_count} Validados
                </span>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800 text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Entregable Requerido</th>
                      <th className="py-3 px-4">Tipo</th>
                      <th className="py-3 px-4">Carácter</th>
                      <th className="py-3 px-4">Documentos Provistos</th>
                      <th className="py-3 px-4 text-right">Estado de Evidencia</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {reportData.completeness.deliverables_matrix.map((d, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition">
                        <td className="py-3.5 px-4 font-semibold text-slate-100">{d.title}</td>
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">{d.deliverable_type}</td>
                        <td className="py-3.5 px-4">
                          {d.is_mandatory ? (
                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-950 text-rose-300 border border-rose-800">Obligatorio</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-400">Opcional</span>
                          )}
                        </td>
                        <td className="py-3.5 px-4 font-mono">{d.provided_files_count} archivos</td>
                        <td className="py-3.5 px-4 text-right">
                          {d.readiness_status === 'eligible' || d.is_fulfilled ? (
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-950 text-emerald-300 border border-emerald-700">Apto Evidencia</span>
                          ) : d.readiness_status === 'pending_validation' ? (
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-950 text-amber-300 border border-amber-700">Por Validar</span>
                          ) : (
                            <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-rose-950 text-rose-300 border border-rose-700">Faltante</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 3: 4 VEREDICTOS DE AUDITORÍA */}
          {activeTab === 'verdicts' && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Resultados Canónicos de Auditoría Técnica ({reportData.audit_verdicts.verdicts_list.length})
                </h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800 text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Regla QA/QC</th>
                      <th className="py-3 px-4">Nombre / Categoría</th>
                      <th className="py-3 px-4">Disciplina</th>
                      <th className="py-3 px-4">Documento / Lámina</th>
                      <th className="py-3 px-4 text-right">Veredicto Canónico</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {reportData.audit_verdicts.verdicts_list.map((v, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition">
                        <td className="py-3.5 px-4 font-mono font-bold text-indigo-300">{v.rule_code}</td>
                        <td className="py-3.5 px-4">
                          <div className="font-semibold text-slate-100">{v.rule_name}</div>
                          <div className="text-[10px] text-slate-500 capitalize">{v.category}</div>
                        </td>
                        <td className="py-3.5 px-4 capitalize font-mono text-[11px]">{v.discipline}</td>
                        <td className="py-3.5 px-4 font-mono text-[11px] text-slate-400">
                          {v.document_filename || v.sheet_code || 'General'}
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          {getVerdictTag(v.verdict)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 4: OBSERVACIONES & RFIs */}
          {activeTab === 'observations' && (
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
              <div className="p-4 border-b border-slate-800 flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider">
                  Listado Formal de Observaciones, RFIs y Bloqueos ({reportData.observations.items.length})
                </h3>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="bg-slate-950 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800 text-[11px]">
                    <tr>
                      <th className="py-3 px-4">Código / Tipo</th>
                      <th className="py-3 px-4">Título</th>
                      <th className="py-3 px-4">Disciplina</th>
                      <th className="py-3 px-4">Criticidad</th>
                      <th className="py-3 px-4 text-right">Estado</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {reportData.observations.items.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/30 transition">
                        <td className="py-3.5 px-4 font-mono font-bold text-slate-100">
                          {item.code}
                        </td>
                        <td className="py-3.5 px-4 font-semibold text-slate-200">{item.title}</td>
                        <td className="py-3.5 px-4 capitalize font-mono">{item.discipline}</td>
                        <td className="py-3.5 px-4 font-mono uppercase text-[10px]">
                          <span className={`px-2 py-0.5 rounded font-bold ${item.severity === 'critical' ? 'bg-rose-950 text-rose-300' : item.severity === 'high' ? 'bg-amber-950 text-amber-300' : 'bg-slate-800 text-slate-300'}`}>
                            {item.severity}
                          </span>
                        </td>
                        <td className="py-3.5 px-4 text-right">
                          <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${item.status === 'closed' || item.status === 'validated' ? 'bg-emerald-950 text-emerald-300 border border-emerald-700' : 'bg-amber-950 text-amber-300 border border-amber-700'}`}>
                            {item.status.toUpperCase()}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* TAB 5: EVOLUCIÓN DELTA */}
          {activeTab === 'delta' && (
            <div className="space-y-4">
              <div className="p-5 bg-slate-900 border border-slate-800 rounded-xl space-y-3">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <Clock className="w-4 h-4 text-indigo-400" />
                  <span>Resumen Comparativo de Evolución Delta</span>
                </h3>
                <p className="text-xs text-slate-300 leading-relaxed">
                  {reportData.delta_evolution.summary_narrative}
                </p>
              </div>

              {/* Registro de Cambios de Estado */}
              <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
                <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider">Historial de Transiciones de Estado</h4>
                {reportData.delta_evolution.status_changes && reportData.delta_evolution.status_changes.length > 0 ? (
                  <div className="space-y-2">
                    {reportData.delta_evolution.status_changes.map((sc, idx) => (
                      <div key={idx} className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-xs flex items-center justify-between">
                        <div>
                          <strong className="font-mono text-indigo-300">[{sc.code}]</strong> <span className="text-slate-200">{sc.notes}</span>
                        </div>
                        <span className="text-slate-500 font-mono text-[11px]">{sc.from} → {sc.to}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-slate-500 italic">No se registran cambios de estado respecto a la revisión anterior.</p>
                )}
              </div>
            </div>
          )}
        </>
      )}

      {/* Modal de Emisión Formal de Snapshot */}
      {isEmitModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4 animate-in fade-in zoom-in-95">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <Send className="w-5 h-5 text-indigo-400" />
              <span>Emitir Snapshot Formal de Cierre</span>
            </h3>

            <p className="text-xs text-slate-400">
              Esta acción congelará el estado actual de la etapa en un Snapshot inmutable (Rev {(snapshots[0]?.revision_number || 0) + 1}), generando sus archivos PDF y JSON auditables con hash SHA-256.
            </p>

            <form onSubmit={handleEmitSnapshot} className="space-y-3.5 pt-2">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Título de la Emisión:</label>
                <input
                  type="text"
                  value={emissionTitle}
                  onChange={(e) => setEmissionTitle(e.target.value)}
                  placeholder={`Reporte Consolidado Final Rev ${(snapshots[0]?.revision_number || 0) + 1}`}
                  className="w-full bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1">Notas de Emisión / Observaciones:</label>
                <textarea
                  value={emissionNotes}
                  onChange={(e) => setEmissionNotes(e.target.value)}
                  rows={3}
                  placeholder="Ej: Emisión formal de cierre con EETT incorporadas y veredictos delta verificados..."
                  className="w-full bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-xl px-3 py-2 focus:outline-none focus:border-indigo-500"
                />
              </div>

              <div className="flex items-center justify-end gap-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setIsEmitModalOpen(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={emitting}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold shadow-lg shadow-indigo-600/30 transition flex items-center gap-1.5"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>{emitting ? 'Emitiendo...' : 'Confirmar & Emitir'}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
