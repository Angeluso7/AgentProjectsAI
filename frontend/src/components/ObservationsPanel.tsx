import React, { useState, useEffect } from 'react';
import {
  ShieldAlert, AlertTriangle, HelpCircle, Lock, Info, CheckCircle2,
  XCircle, RefreshCw, Send, Plus, Upload, Play, Clock, ArrowRight,
  Filter, Search, ExternalLink, X, FileText, Check, MessageSquare, Layers
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  AuditObservationItem, ObservationType, ObservationStatus,
  DeltaReevaluationResult, DocumentItem
} from '../types';
import { useProject } from '../context/ProjectContext';

export const ObservationsPanel: React.FC = () => {
  const { activeProject, activeProjectId } = useProject();

  const [observations, setObservations] = useState<AuditObservationItem[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [generating, setGenerating] = useState<boolean>(false);

  // Filtros
  const [selectedType, setSelectedType] = useState<string>('all');
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [selectedDiscipline, setSelectedDiscipline] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Modal de Detalle
  const [selectedObs, setSelectedObs] = useState<AuditObservationItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState<boolean>(false);

  // Formularios dentro del modal
  const [responseText, setResponseText] = useState<string>('');
  const [responseRole, setResponseRole] = useState<string>('contractor');
  const [selectedProvisionDocId, setSelectedProvisionDocId] = useState<string>('');
  const [provisionNotes, setProvisionNotes] = useState<string>('');
  const [actionLoading, setActionLoading] = useState<boolean>(false);
  const [deltaResult, setDeltaResult] = useState<DeltaReevaluationResult | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    loadObservations();
    if (activeProjectId) {
      loadDocuments();
    }
  }, [activeProjectId, selectedType, selectedStatus, selectedDiscipline]);

  const loadObservations = async () => {
    setLoading(true);
    try {
      const data = await apiService.getObservations({
        project_id: activeProjectId || undefined,
        item_type: selectedType !== 'all' ? selectedType : undefined,
        status: selectedStatus !== 'all' ? selectedStatus : undefined,
        discipline: selectedDiscipline !== 'all' ? selectedDiscipline : undefined,
        search: searchQuery || undefined
      });
      setObservations(data);
    } catch (err) {
      console.error('Error al cargar observaciones:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDocuments = async () => {
    try {
      const docs = await apiService.getDocuments(activeProjectId);
      setDocuments(docs);
      if (docs.length > 0) {
        setSelectedProvisionDocId(docs[0].id);
      }
    } catch (err) {
      console.error('Error cargando documentos para provisión:', err);
    }
  };

  const handleGenerateFromRun = async () => {
    if (!activeProjectId) {
      alert('Seleccione un proyecto activo para generar observaciones.');
      return;
    }
    setGenerating(true);
    try {
      const generated = await apiService.generateObservationsFromRun({
        project_id: activeProjectId
      });
      alert(`Se generaron ${generated.length} observaciones / RFIs formales a partir de los hallazgos.`);
      await loadObservations();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al generar observaciones.');
    } finally {
      setGenerating(false);
    }
  };

  const handleOpenDetail = (obs: AuditObservationItem) => {
    setSelectedObs(obs);
    setResponseText('');
    setProvisionNotes('');
    setDeltaResult(null);
    setActionError(null);
    setIsDetailOpen(true);
  };

  const handleIssue = async () => {
    if (!selectedObs) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await apiService.issueObservation(selectedObs.id, {
        notes: 'Emitido formalmente para rectificación'
      });
      setSelectedObs(updated);
      await loadObservations();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error al emitir observación.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleSubmitResponse = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedObs || !responseText.trim()) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await apiService.submitObservationResponse(selectedObs.id, {
        response_text: responseText,
        author_role: responseRole
      });
      setSelectedObs(updated);
      setResponseText('');
      await loadObservations();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error al enviar respuesta.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleProvisionEvidence = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedObs || !selectedProvisionDocId) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await apiService.provisionObservationEvidence(selectedObs.id, {
        document_id: selectedProvisionDocId,
        notes: provisionNotes
      });
      setSelectedObs(updated);
      setProvisionNotes('');
      await loadObservations();
      alert('Evidencia provisionada y promovida a Apto como Evidencia exitosamente.');
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error al provisionar evidencia.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDeltaReevaluation = async () => {
    if (!selectedObs) return;
    setActionLoading(true);
    setActionError(null);
    try {
      const result: DeltaReevaluationResult = await apiService.executeObservationDeltaReevaluation(selectedObs.id);
      setDeltaResult(result);
      // Recargar detalle actualizado
      const updated = await apiService.getObservationDetail(selectedObs.id);
      setSelectedObs(updated);
      await loadObservations();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error al ejecutar re-evaluación delta.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleReopen = async () => {
    if (!selectedObs) return;
    const reason = window.prompt('Ingrese el motivo de reapertura formal de la observación:');
    if (reason === null) return; // cancelado por usuario
    setActionLoading(true);
    setActionError(null);
    try {
      const updated = await apiService.reopenObservation(selectedObs.id, { reason });
      setSelectedObs(updated);
      await loadObservations();
      alert('Observación reabierta exitosamente.');
    } catch (err: any) {
      setActionError(err.response?.data?.detail || 'Error al reabrir observación.');
    } finally {
      setActionLoading(false);
    }
  };

  // Contadores de métricas
  const totalObs = observations.filter(o => o.item_type === 'technical_observation').length;
  const totalRfi = observations.filter(o => o.item_type === 'information_request').length;
  const totalBlk = observations.filter(o => o.item_type === 'document_blocker').length;
  const totalClosed = observations.filter(o => o.status === 'closed' || o.status === 'validated').length;

  const getTypeBadge = (type: ObservationType) => {
    switch (type) {
      case 'technical_observation':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-rose-950/80 text-rose-300 border border-rose-700/60">
            <AlertTriangle className="w-3 h-3 text-rose-400" /> OBS
          </span>
        );
      case 'information_request':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-amber-950/80 text-amber-300 border border-amber-700/60">
            <HelpCircle className="w-3 h-3 text-amber-400" /> RFI
          </span>
        );
      case 'document_blocker':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-bold bg-purple-950/80 text-purple-300 border border-purple-700/60">
            <Lock className="w-3 h-3 text-purple-400" /> BLK
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md text-xs font-medium bg-slate-800 text-slate-300 border border-slate-700">
            <Info className="w-3 h-3 text-slate-400" /> MIN
          </span>
        );
    }
  };

  const getStatusBadge = (status: ObservationStatus) => {
    switch (status) {
      case 'draft':
        return <span className="px-2 py-0.5 text-[11px] font-medium rounded bg-slate-800 text-slate-400 border border-slate-700">Borrador</span>;
      case 'issued':
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-amber-950 text-amber-300 border border-amber-700">Emitida</span>;
      case 'answered':
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-blue-950 text-blue-300 border border-blue-700">Respondida</span>;
      case 'provisioned':
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-purple-950 text-purple-300 border border-purple-700">Provisionada</span>;
      case 'validated':
      case 'closed':
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-emerald-950 text-emerald-300 border border-emerald-700">Cerrada / Resuelta</span>;
      case 'rejected':
        return <span className="px-2 py-0.5 text-[11px] font-semibold rounded bg-rose-950 text-rose-300 border border-rose-700">Rechazada</span>;
      default:
        return <span className="px-2 py-0.5 text-[11px] font-medium rounded bg-slate-800 text-slate-300">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Metrics Strip */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-rose-950/60 border border-rose-800/60 rounded-lg text-rose-400">
            <AlertTriangle className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Observaciones (OBS)</div>
            <div className="text-xl font-bold text-white mt-0.5">{totalObs}</div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-amber-950/60 border border-amber-800/60 rounded-lg text-amber-400">
            <HelpCircle className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Solicitudes (RFI)</div>
            <div className="text-xl font-bold text-white mt-0.5">{totalRfi}</div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-purple-950/60 border border-purple-800/60 rounded-lg text-purple-400">
            <Lock className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Bloqueos (BLK)</div>
            <div className="text-xl font-bold text-white mt-0.5">{totalBlk}</div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 flex items-center gap-3">
          <div className="p-2.5 bg-emerald-950/60 border border-emerald-800/60 rounded-lg text-emerald-400">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <div className="text-xs text-slate-400 font-medium uppercase tracking-wider">Cerradas / Resueltas</div>
            <div className="text-xl font-bold text-emerald-400 mt-0.5">{totalClosed}</div>
          </div>
        </div>

        <div className="p-4 rounded-xl bg-indigo-950/30 border border-indigo-800/40 flex flex-col justify-center">
          <button
            onClick={handleGenerateFromRun}
            disabled={generating}
            className="w-full py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold rounded-lg text-xs flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/30 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${generating ? 'animate-spin' : ''}`} />
            <span>{generating ? 'Generando...' : 'Generar Formales'}</span>
          </button>
          <div className="text-[10px] text-slate-400 text-center mt-1.5">
            Convierte hallazgos en OBS / RFIs
          </div>
        </div>
      </div>

      {/* Filter Toolbar */}
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-xl flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Tipo */}
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="all">Tipo: Todos</option>
            <option value="technical_observation">OBS - Observaciones Técnicas</option>
            <option value="information_request">RFI - Solicitudes de Información</option>
            <option value="document_blocker">BLK - Bloqueos Documentales</option>
            <option value="minor_missing">MIN - Faltantes Menores</option>
          </select>

          {/* Estado */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="all">Estado: Todos</option>
            <option value="draft">Borrador</option>
            <option value="issued">Emitida</option>
            <option value="answered">Respondida</option>
            <option value="provisioned">Provisionada</option>
            <option value="closed">Cerrada / Resuelta</option>
          </select>

          {/* Disciplina */}
          <select
            value={selectedDiscipline}
            onChange={(e) => setSelectedDiscipline(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-1.5 focus:outline-none focus:border-indigo-500"
          >
            <option value="all">Disciplina: Todas</option>
            <option value="architecture">Arquitectura</option>
            <option value="structural">Estructuras</option>
            <option value="electrical">Eléctrica</option>
            <option value="general">General</option>
          </select>
        </div>

        {/* Search */}
        <div className="relative">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && loadObservations()}
            placeholder="Buscar por código o título..."
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg pl-8 pr-3 py-1.5 w-64 focus:outline-none focus:border-indigo-500"
          />
        </div>
      </div>

      {/* Observations Table */}
      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
        {loading ? (
          <div className="py-12 text-center text-slate-400 text-xs flex items-center justify-center gap-2">
            <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
            <span>Cargando bandeja de observaciones y RFIs...</span>
          </div>
        ) : observations.length === 0 ? (
          <div className="py-12 text-center text-slate-400">
            <ShieldAlert className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            <p className="text-sm font-semibold text-slate-300">No hay observaciones ni RFIs registrados.</p>
            <p className="text-xs text-slate-500 mt-1">
              Ejecuta una auditoría o haz clic en «Generar Formales» para convertir los hallazgos de reglas en ítems trazables.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="bg-slate-950/80 text-slate-400 uppercase tracking-wider font-semibold border-b border-slate-800 text-[11px]">
                <tr>
                  <th className="py-3 px-4">Código / Tipo</th>
                  <th className="py-3 px-4">Título & Descripción</th>
                  <th className="py-3 px-4">Disciplina / Etapa</th>
                  <th className="py-3 px-4">Origen (Regla / Doc)</th>
                  <th className="py-3 px-4">Estado</th>
                  <th className="py-3 px-4 text-right">Acción</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {observations.map((obs) => (
                  <tr
                    key={obs.id}
                    onClick={() => handleOpenDetail(obs)}
                    className="hover:bg-slate-800/40 transition cursor-pointer"
                  >
                    <td className="py-3.5 px-4">
                      <div className="flex items-center gap-2">
                        {getTypeBadge(obs.item_type)}
                        <span className="font-mono font-bold text-slate-100">{obs.code}</span>
                      </div>
                    </td>
                    <td className="py-3.5 px-4 max-w-md">
                      <div className="font-semibold text-slate-100 line-clamp-1">{obs.title}</div>
                      <div className="text-[11px] text-slate-400 mt-0.5 line-clamp-1">{obs.description}</div>
                    </td>
                    <td className="py-3.5 px-4 font-mono">
                      <div className="capitalize text-slate-200">{obs.discipline}</div>
                      <div className="text-[10px] text-slate-400">{obs.stage}</div>
                    </td>
                    <td className="py-3.5 px-4">
                      <div className="font-mono text-indigo-300">{obs.rule_code || '—'}</div>
                      <div className="text-[10px] text-slate-400 truncate max-w-[150px]">
                        {obs.document_filename || obs.sheet_title || 'Documento general'}
                      </div>
                    </td>
                    <td className="py-3.5 px-4">
                      {getStatusBadge(obs.status)}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenDetail(obs);
                        }}
                        className="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded-lg text-xs font-semibold border border-indigo-500/40 transition"
                      >
                        Gestionar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal de Detalle, Respuestas, Provisión y Re-evaluación Delta */}
      {isDetailOpen && selectedObs && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 overflow-y-auto">
          <div className="bg-slate-900 border border-slate-700 rounded-2xl max-w-3xl w-full p-6 shadow-2xl space-y-5 animate-in fade-in zoom-in-95 duration-150">
            {/* Modal Header */}
            <div className="flex items-start justify-between border-b border-slate-800 pb-4">
              <div className="flex items-center gap-3">
                {getTypeBadge(selectedObs.item_type)}
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-lg font-bold text-white">{selectedObs.code}</span>
                    <span className="text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
                      {selectedObs.discipline}
                    </span>
                    {getStatusBadge(selectedObs.status)}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-200 mt-1">{selectedObs.title}</h3>
                </div>
              </div>

              <button
                onClick={() => setIsDetailOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-800 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {actionError && (
              <div className="p-3 bg-rose-950/40 border border-rose-700/60 rounded-lg text-rose-300 text-xs flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                <span>{actionError}</span>
              </div>
            )}

            {/* Context Details Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs bg-slate-950/60 p-4 rounded-xl border border-slate-800">
              <div>
                <span className="text-slate-400 font-medium">Descripción del Hallazgo:</span>
                <p className="text-slate-200 mt-1">{selectedObs.description}</p>
                {selectedObs.recommendation && (
                  <div className="mt-2 text-indigo-300 bg-indigo-950/30 p-2 rounded border border-indigo-800/40">
                    <strong>Recomendación:</strong> {selectedObs.recommendation}
                  </div>
                )}
              </div>

              <div className="space-y-1.5 font-mono text-[11px]">
                <div><span className="text-slate-400">Regla Origen:</span> <strong className="text-indigo-300">{selectedObs.rule_code || '—'}</strong></div>
                <div><span className="text-slate-400">Documento Inicial:</span> <span className="text-slate-200">{selectedObs.document_filename || '—'}</span></div>
                <div><span className="text-slate-400">Lámina Técnica:</span> <span className="text-slate-200">{selectedObs.sheet_title || '—'}</span></div>
                <div><span className="text-slate-400">Evidencia Provisionada:</span> <strong className="text-emerald-400">{selectedObs.provisioned_document_filename || 'Ninguna'}</strong></div>
              </div>
            </div>

            {/* Delta Re-evaluation Result Banner */}
            {deltaResult && (
              <div className={`p-4 rounded-xl border ${deltaResult.is_resolved ? 'bg-emerald-950/40 border-emerald-600 text-emerald-200' : 'bg-amber-950/40 border-amber-600 text-amber-200'} text-xs space-y-2`}>
                <div className="flex items-center justify-between font-bold text-sm">
                  <div className="flex items-center gap-2">
                    {deltaResult.is_resolved ? <CheckCircle2 className="w-5 h-5 text-emerald-400" /> : <AlertTriangle className="w-5 h-5 text-amber-400" />}
                    <span>Resultado de Re-evaluación Delta: {deltaResult.verdict_after.toUpperCase()}</span>
                  </div>
                  <span className="font-mono">{deltaResult.status_before} → {deltaResult.status_after}</span>
                </div>
                <p>{deltaResult.message}</p>
                <div className="text-[11px] opacity-80">
                  Reglas auditadas: {deltaResult.affected_rules_evaluated.join(', ')} | Láminas: {deltaResult.affected_sheets_evaluated.join(', ')}
                </div>
              </div>
            )}

            {/* Actions Toolbar */}
            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <div className="flex items-center gap-2">
                {selectedObs.status === 'draft' && (
                  <button
                    onClick={handleIssue}
                    disabled={actionLoading}
                    className="px-3.5 py-1.5 bg-amber-600 hover:bg-amber-500 text-white rounded-lg text-xs font-semibold shadow transition"
                  >
                    Emitir Formalmente
                  </button>
                )}

                {(selectedObs.status === 'closed' || selectedObs.status === 'validated') && (
                  <button
                    onClick={handleReopen}
                    disabled={actionLoading}
                    className="px-3.5 py-1.5 bg-amber-700 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold shadow transition flex items-center gap-1.5"
                  >
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>Reabrir Observación</span>
                  </button>
                )}

                <button
                  onClick={handleDeltaReevaluation}
                  disabled={actionLoading}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white rounded-lg text-xs font-bold flex items-center gap-2 shadow-lg shadow-emerald-600/30 transition"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>{actionLoading ? 'Auditando...' : 'Disparar Re-evaluación Delta'}</span>
                </button>
              </div>

              <div className="text-xs text-slate-400">
                Estado actual: <strong className="text-slate-200">{selectedObs.status}</strong>
              </div>
            </div>

            {/* Accordion / Multi-Panel: Responses & Provisioning */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              {/* Provisión de Nueva Evidencia */}
              <div className="p-4 bg-slate-950/40 rounded-xl border border-slate-800 space-y-3">
                <div className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
                  <Upload className="w-4 h-4 text-purple-400" />
                  <span>Provisionar Nueva Evidencia</span>
                </div>

                <form onSubmit={handleProvisionEvidence} className="space-y-2.5">
                  <div>
                    <label className="block text-[11px] text-slate-400 mb-1">Seleccionar Documento Cargado:</label>
                    <select
                      value={selectedProvisionDocId}
                      onChange={(e) => setSelectedProvisionDocId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
                    >
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.filename} {(d as any).discipline ? `(${(d as any).discipline})` : ''}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <input
                      type="text"
                      value={provisionNotes}
                      onChange={(e) => setProvisionNotes(e.target.value)}
                      placeholder="Notas de entrega (ej: Lámina corregida Rev B)"
                      className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
                    />
                  </div>

                  <button
                    type="submit"
                    disabled={actionLoading || !selectedProvisionDocId}
                    className="w-full py-1.5 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-xs font-semibold transition"
                  >
                    Vincular & Provisionar
                  </button>
                </form>
              </div>

              {/* Registro de Respuesta Técnica */}
              <div className="p-4 bg-slate-950/40 rounded-xl border border-slate-800 space-y-3">
                <div className="font-semibold text-xs text-slate-200 flex items-center gap-1.5">
                  <MessageSquare className="w-4 h-4 text-blue-400" />
                  <span>Aclaración / Respuesta del Contratista</span>
                </div>

                <form onSubmit={handleSubmitResponse} className="space-y-2.5">
                  <textarea
                    value={responseText}
                    onChange={(e) => setResponseText(e.target.value)}
                    rows={2}
                    placeholder="Escriba la justificación o referencia técnica..."
                    className="w-full bg-slate-900 border border-slate-700 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-indigo-500"
                  />

                  <button
                    type="submit"
                    disabled={actionLoading || !responseText.trim()}
                    className="w-full py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition"
                  >
                    Ingresar Respuesta
                  </button>
                </form>
              </div>
            </div>

            {/* Timeline & History Trace */}
            <div className="border-t border-slate-800 pt-4">
              <div className="font-semibold text-xs text-slate-300 mb-3 flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-indigo-400" />
                <span>Trazabilidad Histórica del Ciclo de Vida ({selectedObs.history_trace?.length || 0})</span>
              </div>

              <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                {selectedObs.history_trace && selectedObs.history_trace.length > 0 ? (
                  selectedObs.history_trace.map((trace, idx) => (
                    <div key={idx} className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-[11px]">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="font-mono font-bold text-slate-200">
                          Acción: {trace.action} ({trace.from_status || 'inicio'} → {trace.to_status})
                        </span>
                        <span>{new Date(trace.timestamp).toLocaleString()}</span>
                      </div>
                      <p className="text-slate-300 mt-1">{trace.notes}</p>
                    </div>
                  ))
                ) : (
                  <div className="text-slate-500 text-xs italic">Sin historial de trazabilidad aún.</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
