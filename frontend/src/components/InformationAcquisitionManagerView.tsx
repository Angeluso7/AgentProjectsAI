import React, { useState, useEffect } from 'react';
import {
  Globe, Shield, CheckCircle2, AlertTriangle, HelpCircle, ArrowRight,
  RefreshCw, Search, Filter, Plus, FileText, Image as ImageIcon,
  Check, X, ChevronRight, Sparkles, Building2, User, Clock,
  ExternalLink, Layers, Eye, Cpu, Database, Send, AlertOctagon
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  InformationAcquisitionRequestDTO,
  IngestionChannelSummaryResponseDTO,
  IngestionChannelItemDTO
} from '../types';

interface InformationAcquisitionManagerViewProps {
  projectId?: string;
  projectName?: string;
  projectStage?: string;
}

export const InformationAcquisitionManagerView: React.FC<InformationAcquisitionManagerViewProps> = ({
  projectId,
  projectName,
  projectStage
}) => {
  const [activeTab, setActiveTab] = useState<'requests' | 'channels' | 'detect'>('requests');
  const [channelsData, setChannelsData] = useState<IngestionChannelSummaryResponseDTO | null>(null);
  const [requests, setRequests] = useState<InformationAcquisitionRequestDTO[]>([]);
  const [loading, setLoading] = useState(false);
  const [processingId, setProcessingId] = useState<string | null>(null);
  const [actionSuccessMsg, setActionSuccessMsg] = useState<string | null>(null);
  const [actionErrorMsg, setActionErrorMsg] = useState<string | null>(null);

  // Formulario de detección manual de brechas
  const [gapQuery, setGapQuery] = useState('');
  const [gapDiscipline, setGapDiscipline] = useState('architecture');
  const [detectingGap, setDetectingGap] = useState(false);
  const [gapDetectResult, setGapDetectResult] = useState<any | null>(null);

  // Modal o estado para ajuste de búsqueda web
  const [selectedReqForAction, setSelectedReqForAction] = useState<InformationAcquisitionRequestDTO | null>(null);
  const [queryOverride, setQueryOverride] = useState('');
  const [rejectionReason, setRejectionReason] = useState('');

  const loadData = async () => {
    try {
      setLoading(true);
      const [channelsRes, requestsRes] = await Promise.all([
        apiService.getIngestionChannelsSummary(projectId),
        apiService.getAcquisitionRequests({ project_id: projectId, limit: 50 })
      ]);
      setChannelsData(channelsRes);
      setRequests(requestsRes);
    } catch (err: any) {
      console.error('Error cargando datos de adquisición:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  const handleApproveWebSearch = async (req: InformationAcquisitionRequestDTO, forceDoc = false) => {
    try {
      setProcessingId(req.id);
      setActionErrorMsg(null);
      setActionSuccessMsg(null);
      const updated = await apiService.respondWebSearchPermission(req.id, {
        action: 'approve',
        query_override: queryOverride || undefined,
        force_document_request: forceDoc
      });
      setActionSuccessMsg(
        forceDoc
          ? `Se escaló a Solicitud Formal de Documentación para «${req.missing_topic}».`
          : `Búsqueda Web ejecutada. Conocimiento incorporado en estado 'extracted' para «${req.missing_topic}».`
      );
      setSelectedReqForAction(null);
      setQueryOverride('');
      await loadData();
    } catch (err: any) {
      setActionErrorMsg(err?.response?.data?.detail || 'Error al procesar autorización.');
    } finally {
      setProcessingId(null);
    }
  };

  const handleRejectWebSearch = async (req: InformationAcquisitionRequestDTO) => {
    try {
      setProcessingId(req.id);
      setActionErrorMsg(null);
      setActionSuccessMsg(null);
      await apiService.respondWebSearchPermission(req.id, {
        action: 'reject',
        rejection_reason: rejectionReason || 'Rechazado por el usuario.'
      });
      setActionSuccessMsg(`Solicitud de búsqueda web denegada para «${req.missing_topic}».`);
      setSelectedReqForAction(null);
      setRejectionReason('');
      await loadData();
    } catch (err: any) {
      setActionErrorMsg(err?.response?.data?.detail || 'Error al rechazar solicitud.');
    } finally {
      setProcessingId(null);
    }
  };

  const handleDetectGapSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!gapQuery.trim()) return;

    try {
      setDetectingGap(true);
      setGapDetectResult(null);
      const res = await apiService.detectInformationGap({
        project_id: projectId,
        stage: projectStage,
        discipline: gapDiscipline,
        topic_query: gapQuery.trim(),
        detection_source: 'manual_auditor',
        auto_request_permission: true
      });
      setGapDetectResult(res);
      await loadData();
    } catch (err: any) {
      console.error('Error detectando brecha:', err);
    } finally {
      setDetectingGap(false);
    }
  };

  const pendingRequests = requests.filter(r => r.permission_status === 'pending_permission');
  const historicalRequests = requests.filter(r => r.permission_status !== 'pending_permission');

  const getChannelIcon = (code: string) => {
    switch (code) {
      case 'viewer_capture':
        return <Eye className="w-5 h-5 text-indigo-400" />;
      case 'manual_intake':
        return <FileText className="w-5 h-5 text-blue-400" />;
      case 'rule_derivation':
        return <Cpu className="w-5 h-5 text-amber-400" />;
      case 'review_finding':
        return <Shield className="w-5 h-5 text-emerald-400" />;
      case 'ai_web_search':
        return <Globe className="w-5 h-5 text-purple-400" />;
      case 'manual_entry':
      default:
        return <Database className="w-5 h-5 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Banner Principal */}
      <div className="p-6 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900/90 to-purple-950/40 border border-purple-800/40 shadow-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold uppercase tracking-wider flex items-center gap-1">
              <Globe className="w-3 h-3" /> Arquitectura de Ingesta & Web-First con Permiso
            </span>
            {projectName && (
              <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 text-[10px] font-medium">
                {projectName}
              </span>
            )}
          </div>
          <h1 className="text-xl font-black text-slate-100 flex items-center gap-2">
            Canales de Ingesta & Gobernanza de Adquisición
          </h1>
          <p className="text-xs text-slate-400 max-w-2xl leading-relaxed">
            Gestión unificada de fuentes (Intake, Visor de Planos, Motor de Reglas, Observaciones de Revisión y Búsqueda Web Asistida con IA). 
            Garantiza que toda información entrante cuente con trazabilidad, modalidad y aprobación humana previa antes de su reutilización activa.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button
            onClick={loadData}
            disabled={loading}
            className="px-3.5 py-2 text-xs font-semibold rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 flex items-center gap-1.5 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refrescar</span>
          </button>
        </div>
      </div>

      {/* Alertas y Notificaciones */}
      {actionSuccessMsg && (
        <div className="p-4 rounded-xl bg-emerald-950/70 border border-emerald-700/60 text-emerald-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{actionSuccessMsg}</span>
          </div>
          <button onClick={() => setActionSuccessMsg(null)} className="text-emerald-400 hover:text-emerald-200 text-xs">✕</button>
        </div>
      )}
      {actionErrorMsg && (
        <div className="p-4 rounded-xl bg-rose-950/70 border border-rose-700/60 text-rose-200 text-xs flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{actionErrorMsg}</span>
          </div>
          <button onClick={() => setActionErrorMsg(null)} className="text-rose-400 hover:text-rose-200 text-xs">✕</button>
        </div>
      )}

      {/* Resumen Superior de Canales de Ingesta */}
      {channelsData && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {channelsData.channels.map((ch) => (
            <div
              key={ch.channel_code}
              className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 hover:border-slate-700 transition"
            >
              <div className="flex items-center justify-between">
                <div className="p-2 rounded-lg bg-slate-950 border border-slate-800">
                  {getChannelIcon(ch.channel_code)}
                </div>
                <span className="text-xs font-black text-slate-100">{ch.total_items}</span>
              </div>
              <div>
                <p className="text-[11px] font-bold text-slate-200 truncate">{ch.channel_name}</p>
                <div className="flex items-center justify-between text-[10px] text-slate-400 mt-1">
                  <span className="text-emerald-400 font-semibold">{ch.approved_reusable_items} activos</span>
                  <span className="text-amber-400">{ch.pending_validation_items} pend.</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Selector de Pestañas */}
      <div className="flex border-b border-slate-800 text-xs font-semibold gap-3">
        <button
          onClick={() => setActiveTab('requests')}
          className={`pb-3 px-3 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'requests'
              ? 'border-purple-500 text-purple-400 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Globe className="w-4 h-4" />
          <span>Solicitudes Web-First ({pendingRequests.length} pendientes)</span>
          {pendingRequests.length > 0 && (
            <span className="px-1.5 py-0.2 rounded-full bg-purple-500/20 text-purple-300 text-[10px] font-bold">
              {pendingRequests.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab('channels')}
          className={`pb-3 px-3 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'channels'
              ? 'border-purple-500 text-purple-400 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Database className="w-4 h-4" />
          <span>Matriz de Canales & Gobernanza</span>
        </button>

        <button
          onClick={() => setActiveTab('detect')}
          className={`pb-3 px-3 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'detect'
              ? 'border-purple-500 text-purple-400 font-bold'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Search className="w-4 h-4" />
          <span>Comprobar / Detectar Brecha</span>
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: BANDEJA DE SOLICITUDES WEB-FIRST CON PERMISO */}
      {/* ========================================================================= */}
      {activeTab === 'requests' && (
        <div className="space-y-6">
          {/* Solicitudes Pendientes de Autorización */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
                <Clock className="w-4 h-4 text-amber-400" />
                <span>Solicitudes Pendientes de Permiso de Búsqueda Web</span>
              </h2>
              <span className="text-xs text-slate-400">
                {pendingRequests.length} requerimientos esperando autorización humana
              </span>
            </div>

            {pendingRequests.length === 0 ? (
              <div className="p-8 rounded-2xl bg-slate-900/40 border border-slate-800/80 text-center space-y-2">
                <CheckCircle2 className="w-8 h-8 text-emerald-400/80 mx-auto" />
                <p className="text-sm font-bold text-slate-200">No hay solicitudes pendientes de autorización</p>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  El sistema no ha detectado faltantes que requieran permiso para búsqueda web en este momento.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {pendingRequests.map((req) => (
                  <div
                    key={req.id}
                    className="p-5 rounded-2xl bg-slate-900/90 border border-purple-800/40 hover:border-purple-600/60 transition space-y-4 shadow-lg"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-slate-800/80">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="px-2 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 text-[10px] font-bold uppercase">
                            {req.discipline}
                          </span>
                          <span className="text-[10px] text-slate-400">
                            Detectado por: <strong className="text-slate-300">{req.detection_source}</strong>
                          </span>
                          <span className="text-[10px] text-slate-500">•</span>
                          <span className="text-[10px] text-slate-400">
                            {new Date(req.permission_requested_at).toLocaleString()}
                          </span>
                        </div>
                        <h3 className="text-base font-bold text-slate-100 mt-1">
                          «{req.missing_topic}»
                        </h3>
                      </div>

                      <div className="flex items-center gap-2">
                        <span className="px-2.5 py-1 rounded-full bg-amber-950/80 text-amber-300 border border-amber-700 text-xs font-bold flex items-center gap-1">
                          <Clock className="w-3 h-3" /> Requiere Autorización
                        </span>
                      </div>
                    </div>

                    <p className="text-xs text-slate-300 leading-relaxed">
                      {req.gap_description}
                    </p>

                    <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
                      <div>
                        <span className="text-[11px] text-slate-400">Resultado en Base de Conocimiento Interna (RAG):</span>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className={`font-bold ${req.internal_rag_status === 'resolved' ? 'text-emerald-400' : 'text-amber-400'}`}>
                            {req.internal_rag_status === 'resolved' ? 'Resuelto' : (req.internal_rag_status === 'insufficient' ? 'Insuficiente' : 'No encontrado')}
                          </span>
                          <span className="text-slate-500">•</span>
                          <span className="text-slate-400">Relevancia RAG: {(req.internal_rag_score * 100).toFixed(0)}%</span>
                          <span className="text-slate-500">•</span>
                          <span className="text-slate-400">{req.internal_rag_matches_count} coincidencias</span>
                        </div>
                      </div>

                      {/* Botones de Decisión Humana */}
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleApproveWebSearch(req, false)}
                          disabled={processingId === req.id}
                          className="px-3 py-1.5 text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl flex items-center gap-1.5 transition shadow"
                        >
                          <Globe className="w-3.5 h-3.5" />
                          <span>{processingId === req.id ? 'Buscando...' : 'Autorizar Búsqueda Web con IA'}</span>
                        </button>

                        <button
                          onClick={() => handleApproveWebSearch(req, true)}
                          disabled={processingId === req.id}
                          className="px-3 py-1.5 text-xs font-semibold text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-xl flex items-center gap-1.5 transition"
                          title="Si la información es privada del proyecto y no está en la web"
                        >
                          <FileText className="w-3.5 h-3.5 text-amber-400" />
                          <span>Solicitar Documento Directo</span>
                        </button>

                        <button
                          onClick={() => handleRejectWebSearch(req)}
                          disabled={processingId === req.id}
                          className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-rose-950/30 rounded-xl transition"
                          title="Rechazar búsqueda"
                        >
                          <X className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Historial de Adquisiciones Procesadas */}
          <div className="space-y-3 pt-6 border-t border-slate-800">
            <h2 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>Historial de Adquisiciones & Trazabilidad ({historicalRequests.length})</span>
            </h2>

            {historicalRequests.length === 0 ? (
              <p className="text-xs text-slate-500 italic">No hay registros históricos previos.</p>
            ) : (
              <div className="space-y-3">
                {historicalRequests.map((req) => (
                  <div
                    key={req.id}
                    className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2 text-xs"
                  >
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-slate-200">{req.missing_topic}</span>
                        <span className="text-slate-500">•</span>
                        <span className="text-[11px] text-slate-400">{req.discipline}</span>
                        <span className="text-slate-500">•</span>
                        <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 text-[10px] font-mono">
                          Iteración {req.iteration_count || 1}/{req.max_iterations || 3} (Límite: {req.search_sources_limit || 5} fuentes)
                        </span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        {req.permission_status === 'approved' ? (
                          <span className="px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] font-semibold">
                            Búsqueda Autorizada por {req.permission_granted_by}
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px] font-semibold">
                            Denegada: {req.rejection_reason}
                          </span>
                        )}

                        {req.termination_reason && (
                          <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                            req.termination_reason === 'resolved_satisfactory' ? 'bg-emerald-950/80 text-emerald-300 border-emerald-700' :
                            req.termination_reason === 'partial_needs_validation' ? 'bg-amber-950/80 text-amber-300 border-amber-700' :
                            req.termination_reason === 'exhausted_max_attempts' ? 'bg-orange-950/80 text-orange-300 border-orange-700' :
                            req.termination_reason === 'cancelled_by_user' ? 'bg-rose-950/80 text-rose-300 border-rose-700' :
                            req.termination_reason === 'not_applicable_private_project_data' ? 'bg-blue-950/80 text-blue-300 border-blue-700' :
                            'bg-slate-800 text-slate-300 border-slate-700'
                          }`}>
                            {req.termination_reason === 'resolved_satisfactory' && '✓ Término: Resuelta Satisfactoriamente'}
                            {req.termination_reason === 'partial_needs_validation' && '⚠ Término: Parcial Requiere Validación'}
                            {req.termination_reason === 'insufficient_document_requested' && '✕ Término: Insuficiente (Doc Requerido)'}
                            {req.termination_reason === 'exhausted_max_attempts' && '⏹ Término: Agotado por Límite de Intentos'}
                            {req.termination_reason === 'cancelled_by_user' && '⊘ Término: Cancelado por Rechazo de Permiso'}
                            {req.termination_reason === 'not_applicable_private_project_data' && '🔒 Término: Información Privada de Proyecto'}
                          </span>
                        )}

                        {req.status === 'escalated' && (
                          <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-bold">
                            Escalado a Solicitud Documental
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Barra de Scores de Suficiencia Informacional */}
                    {req.web_search_executed && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 p-2.5 rounded-lg bg-slate-950/70 border border-slate-800 text-[10px]">
                        <div>
                          <span className="text-slate-400">Relevancia Web:</span>
                          <p className="font-bold text-indigo-300 text-xs">{((req.relevance_score || 0) * 100).toFixed(0)}%</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Confianza Fuentes:</span>
                          <p className="font-bold text-emerald-300 text-xs">{((req.confidence_score || 0) * 100).toFixed(0)}%</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Cobertura Aspectos:</span>
                          <p className="font-bold text-purple-300 text-xs">{((req.coverage_score || 0) * 100).toFixed(0)}%</p>
                        </div>
                        <div>
                          <span className="text-slate-400">Suficiencia Global:</span>
                          <p className="font-bold text-amber-300 text-xs">{((req.overall_adequacy_score || 0) * 100).toFixed(0)}% ({req.adequacy_classification || 'evaluado'})</p>
                        </div>
                      </div>
                    )}

                    {req.web_search_result_summary && (
                      <p className="text-slate-400 text-[11px] bg-slate-950/60 p-2.5 rounded-lg border border-slate-800/80 whitespace-pre-line">
                        {req.web_search_result_summary}
                      </p>
                    )}

                    {/* Desglose Explicable de Escalamiento Documental */}
                    {(req.requested_document_type || req.escalation_details?.requested_document_type) && (
                      <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-700/60 space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-amber-300 font-bold flex items-center gap-1.5 text-xs">
                            <FileText className="w-4 h-4 text-amber-400" />
                            <span>Solicitud Formal de Documentación Técnica</span>
                          </p>
                          <span className="text-[10px] text-amber-400/90 font-mono">
                            Escalado: {req.escalation_details?.escalated_at ? new Date(req.escalation_details.escalated_at).toLocaleString() : 'Reciente'}
                          </span>
                        </div>
                        
                        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px] pt-1">
                          <div className="p-2 rounded-lg bg-black/40 border border-amber-900/40">
                            <span className="text-slate-400 text-[10px] block">¿Qué información sigue faltando?</span>
                            <span className="text-slate-200 font-semibold">{req.escalation_details?.missing_information_details || req.missing_topic}</span>
                          </div>
                          <div className="p-2 rounded-lg bg-black/40 border border-amber-900/40">
                            <span className="text-slate-400 text-[10px] block">¿Por qué la Web/Interno no bastó?</span>
                            <span className="text-slate-200">{req.escalation_details?.why_web_internal_failed || 'La búsqueda web no contiene parámetros privados del proyecto.'}</span>
                          </div>
                          <div className="p-2 rounded-lg bg-black/40 border border-amber-900/40">
                            <span className="text-slate-400 text-[10px] block">Documento / Entregable exacto requerido:</span>
                            <span className="text-amber-300 font-bold">{req.requested_document_type || req.escalation_details?.requested_document_type}</span>
                          </div>
                          <div className="p-2 rounded-lg bg-black/40 border border-amber-900/40">
                            <span className="text-slate-400 text-[10px] block">Responsable sugerido para aportarlo:</span>
                            <span className="text-emerald-300 font-semibold">{req.suggested_responsible || req.escalation_details?.suggested_responsible}</span>
                          </div>
                        </div>

                        <div className="p-2 rounded-lg bg-black/40 border border-amber-900/40 text-[11px]">
                          <span className="text-slate-400 text-[10px] block">Impacto en Auditoría & Desbloqueo:</span>
                          <p className="text-slate-300">{req.requested_document_justification || req.escalation_details?.audit_impact_justification}</p>
                          {req.escalation_details?.unlocked_deliverables_and_rules && req.escalation_details.unlocked_deliverables_and_rules.length > 0 && (
                            <div className="flex flex-wrap gap-1 mt-1.5">
                              <span className="text-[10px] text-amber-400 font-semibold">Desbloquearía:</span>
                              {req.escalation_details.unlocked_deliverables_and_rules.map((rule, idx) => (
                                <span key={idx} className="px-1.5 py-0.2 rounded bg-amber-900/60 text-amber-200 text-[9px] font-mono border border-amber-700/50">
                                  {rule}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: MATRIZ DE CANALES DE INGESTA & GOBERNANZA */}
      {/* ========================================================================= */}
      {activeTab === 'channels' && channelsData && (
        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 flex items-center justify-between text-xs">
            <div>
              <p className="text-slate-200 font-bold">Resumen Global de Conocimiento Gobernado</p>
              <p className="text-slate-400 text-[11px]">
                Total unidades registradas en la organización: <strong>{channelsData.total_knowledge_items}</strong> (<strong>{channelsData.total_active_for_reuse}</strong> activas para reutilización activa por el Asistente).
              </p>
            </div>
          </div>

          <div className="overflow-x-auto rounded-xl border border-slate-800">
            <table className="w-full text-xs text-left">
              <thead className="bg-slate-950/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="p-3.5">Canal de Ingesta</th>
                  <th className="p-3.5">Descripción & Naturaleza</th>
                  <th className="p-3.5">Total Unidades</th>
                  <th className="p-3.5">Activas Reutilizables</th>
                  <th className="p-3.5">Pendientes Validación</th>
                  <th className="p-3.5">Requiere Aprobación</th>
                  <th className="p-3.5">Modalidades</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 bg-slate-900/50">
                {channelsData.channels.map((ch) => (
                  <tr key={ch.channel_code} className="hover:bg-slate-800/30 transition">
                    <td className="p-3.5 font-bold text-slate-100 flex items-center gap-2">
                      <div className="p-1.5 rounded-lg bg-slate-950 border border-slate-800">
                        {getChannelIcon(ch.channel_code)}
                      </div>
                      <span>{ch.channel_name}</span>
                    </td>
                    <td className="p-3.5 text-slate-400 max-w-xs">{ch.description}</td>
                    <td className="p-3.5 font-black text-slate-200">{ch.total_items}</td>
                    <td className="p-3.5 font-bold text-emerald-400">{ch.approved_reusable_items}</td>
                    <td className="p-3.5 font-bold text-amber-400">{ch.pending_validation_items}</td>
                    <td className="p-3.5">
                      {ch.requires_human_approval ? (
                        <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-semibold">
                          Obligatoria
                        </span>
                      ) : (
                        <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 text-[10px] font-semibold">
                          Automática / Base
                        </span>
                      )}
                    </td>
                    <td className="p-3.5 text-[11px] text-slate-400">
                      {Object.entries(ch.modalities_count).map(([m, c]) => `${m}: ${c}`).join(', ') || 'N/A'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: COMPROBAR / DETECTAR BRECHA MANUALMENTE */}
      {/* ========================================================================= */}
      {activeTab === 'detect' && (
        <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4 max-w-2xl">
          <div>
            <h2 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              <Search className="w-4 h-4 text-purple-400" />
              <span>Comprobar Suficiencia de Información & Detección de Brecha</span>
            </h2>
            <p className="text-xs text-slate-400 mt-1">
              Ingresa un tópico normativo o técnico para evaluar si existe respaldo interno suficiente en la Base de Conocimiento
              o si debe dispararse una solicitud de búsqueda web con permiso humano.
            </p>
          </div>

          <form onSubmit={handleDetectGapSubmit} className="space-y-3">
            <div>
              <label className="block text-[11px] font-semibold text-slate-400 mb-1">Tópico / Requisito a Verificar</label>
              <input
                type="text"
                value={gapQuery}
                onChange={(e) => setGapQuery(e.target.value)}
                placeholder="Ej. Resistencia al fuego de muros medianeros F-120..."
                className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 mb-1">Disciplina</label>
                <select
                  value={gapDiscipline}
                  onChange={(e) => setGapDiscipline(e.target.value)}
                  className="w-full px-3 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-purple-500"
                >
                  <option value="architecture">Arquitectura</option>
                  <option value="structures">Estructuras</option>
                  <option value="electrical">Electricidad</option>
                  <option value="sanitary">Sanitaria</option>
                  <option value="general">General</option>
                </select>
              </div>

              <div className="flex items-end">
                <button
                  type="submit"
                  disabled={detectingGap || !gapQuery.trim()}
                  className="w-full py-2 px-4 text-xs font-bold text-white bg-purple-600 hover:bg-purple-500 rounded-xl flex items-center justify-center gap-2 transition disabled:opacity-50"
                >
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>{detectingGap ? 'Evaluando...' : 'Comprobar Brecha'}</span>
                </button>
              </div>
            </div>
          </form>

          {gapDetectResult && (
            <div className={`p-4 rounded-xl border space-y-2 text-xs mt-4 ${
              gapDetectResult.is_gap_detected
                ? 'bg-amber-950/40 border-amber-800 text-amber-200'
                : 'bg-emerald-950/40 border-emerald-800 text-emerald-200'
            }`}>
              <div className="flex items-center gap-2 font-bold">
                {gapDetectResult.is_gap_detected ? <AlertTriangle className="w-4 h-4 text-amber-400" /> : <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                <span>{gapDetectResult.message}</span>
              </div>
              <div className="text-[11px] text-slate-400 flex items-center gap-3">
                <span>Estado RAG: <strong>{gapDetectResult.internal_rag_status}</strong></span>
                <span>Score: <strong>{(gapDetectResult.internal_rag_score * 100).toFixed(0)}%</strong></span>
                <span>Acción Recomendada: <strong>{gapDetectResult.recommended_action}</strong></span>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
