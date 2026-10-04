import React, { useState, useEffect } from 'react';
import {
  ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2, XCircle,
  RefreshCw, Layers, FileText, Lock, ChevronDown, ChevronUp, Info, HelpCircle
} from 'lucide-react';
import { apiService } from '../services/api';
import { CompletenessEvaluationItem, DeliverableType, EvidenceReadinessStatus } from '../types';

interface CompletenessGatekeeperCardProps {
  projectId: string;
  projectName: string;
  projectStage?: string;
  onDocumentClassifyClick?: (docId: string) => void;
}

export const CompletenessGatekeeperCard: React.FC<CompletenessGatekeeperCardProps> = ({
  projectId,
  projectName,
  projectStage = 'Ingeniería de Detalle',
  onDocumentClassifyClick
}) => {
  const [evaluation, setEvaluation] = useState<CompletenessEvaluationItem | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [evaluating, setEvaluating] = useState<boolean>(false);
  const [selectedStage, setSelectedStage] = useState<string>(projectStage);
  const [activeTab, setActiveTab] = useState<'matrix' | 'blocked' | 'verdicts'>('matrix');
  const [expandedRequirementId, setExpandedRequirementId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedStage(projectStage || 'Ingeniería de Detalle');
  }, [projectStage]);

  useEffect(() => {
    loadCompleteness();
  }, [projectId, selectedStage]);

  const loadCompleteness = async () => {
    setLoading(true);
    try {
      const data = await apiService.getProjectCompleteness(projectId, selectedStage);
      setEvaluation(data);
    } catch (err) {
      console.error('Error al cargar completitud:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEvaluateNow = async () => {
    setEvaluating(true);
    try {
      const data = await apiService.evaluateProjectCompleteness(projectId, selectedStage);
      setEvaluation(data);
    } catch (err) {
      console.error('Error al ejecutar evaluación:', err);
    } finally {
      setEvaluating(false);
    }
  };

  const toggleExpand = (reqId: string) => {
    setExpandedRequirementId(prev => (prev === reqId ? null : reqId));
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'eligible':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950 text-emerald-300 border border-emerald-700/60">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            Apto como Evidencia
          </span>
        );
      case 'pending_validation':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950 text-amber-300 border border-amber-700/60">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
            Pendiente Validación
          </span>
        );
      case 'missing_mandatory':
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950 text-rose-300 border border-rose-700/60">
            <XCircle className="w-3.5 h-3.5 text-rose-400" />
            Faltante Obligatorio (Bloqueante)
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-slate-800 text-slate-400 border border-slate-700">
            Faltante Opcional
          </span>
        );
    }
  };

  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl shadow-xl overflow-hidden mb-6">
      {/* Header Banner */}
      <div className="p-5 border-b border-slate-800 bg-gradient-to-r from-slate-900 via-indigo-950/20 to-slate-900 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-indigo-600/20 border border-indigo-500/30 rounded-lg text-indigo-400">
              <ShieldCheck className="w-6 h-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-white">Motor de Completitud Documental & Gatekeeper</h3>
                <span className="text-xs px-2.5 py-0.5 rounded-md bg-indigo-950 text-indigo-300 border border-indigo-800 font-medium">
                  {selectedStage}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Control de idoneidad probatoria para el proyecto <strong className="text-slate-200">{projectName}</strong>.
              </p>
            </div>
          </div>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-3">
          <select
            value={selectedStage}
            onChange={(e) => setSelectedStage(e.target.value)}
            className="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded-lg px-3 py-2 focus:outline-none focus:border-indigo-500"
          >
            <option value="Ingeniería Básica">Etapa: Ingeniería Básica</option>
            <option value="Ingeniería de Detalle">Etapa: Ingeniería de Detalle</option>
            <option value="Factibilidad">Etapa: Factibilidad</option>
            <option value="Licitación">Etapa: Licitación</option>
          </select>

          <button
            onClick={handleEvaluateNow}
            disabled={evaluating || loading}
            className="px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg flex items-center gap-2 shadow-md transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
            <span>{evaluating ? 'Evaluando...' : 'Ejecutar Chequeo'}</span>
          </button>
        </div>
      </div>

      {/* Metrics Strip */}
      {evaluation && (
        <div className="p-5 border-b border-slate-800 bg-slate-950/40">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            {/* Gatekeeper Decision */}
            <div className="col-span-2 md:col-span-1 p-3 rounded-lg border bg-slate-900/80 flex flex-col justify-center items-center text-center">
              <div className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">Gatekeeper</div>
              <div className="mt-1">
                {evaluation.is_gate_passed ? (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                    <ShieldCheck className="w-4 h-4" /> APROBADO
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-rose-500/20 text-rose-400 border border-rose-500/40">
                    <ShieldAlert className="w-4 h-4" /> BLOQUEADO
                  </span>
                )}
              </div>
              <div className="text-[10px] text-slate-500 mt-1">
                {evaluation.is_gate_passed ? 'Auditoría autorizada al 100%' : 'Faltan entregables obligatorios'}
              </div>
            </div>

            {/* Completitud */}
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60">
              <div className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">Completitud</div>
              <div className="text-xl font-bold text-white mt-1">{evaluation.completeness_percentage}%</div>
              <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-500 ${
                    evaluation.completeness_percentage === 100 ? 'bg-emerald-500' : 'bg-indigo-500'
                  }`}
                  style={{ width: `${evaluation.completeness_percentage}%` }}
                />
              </div>
            </div>

            {/* Entregables Aptos */}
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60">
              <div className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">Aptos / Requeridos</div>
              <div className="text-xl font-bold text-emerald-400 mt-1">
                {evaluation.eligible_count}{' '}
                <span className="text-xs text-slate-400 font-normal">/ {evaluation.total_required_count}</span>
              </div>
              <div className="text-[10px] text-slate-500 mt-1">Evidencias válidas</div>
            </div>

            {/* Faltantes Críticos */}
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60">
              <div className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">Faltantes Críticos</div>
              <div className="text-xl font-bold text-rose-400 mt-1">{evaluation.missing_mandatory_count}</div>
              <div className="text-[10px] text-slate-500 mt-1">Entregables bloqueantes</div>
            </div>

            {/* Reglas Bloqueadas */}
            <div className="p-3 rounded-lg border border-slate-800 bg-slate-900/60">
              <div className="text-[11px] uppercase font-semibold text-slate-400 tracking-wider">Reglas Bloqueadas</div>
              <div className="text-xl font-bold text-amber-400 mt-1">{evaluation.blocked_rules_count}</div>
              <div className="text-[10px] text-slate-500 mt-1">Pasan a NO_VERIFICABLE</div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex border-b border-slate-800 bg-slate-950/20 px-5 text-xs font-semibold">
        <button
          onClick={() => setActiveTab('matrix')}
          className={`py-3 px-4 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'matrix'
              ? 'border-indigo-500 text-indigo-400 bg-indigo-950/20'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Layers className="w-4 h-4" />
          <span>Matriz de Entregables ({evaluation?.deliverables_matrix?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('blocked')}
          className={`py-3 px-4 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'blocked'
              ? 'border-amber-500 text-amber-400 bg-amber-950/20'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Lock className="w-4 h-4" />
          <span>Reglas QA/QC Bloqueadas ({evaluation?.blocked_rules?.length || 0})</span>
        </button>

        <button
          onClick={() => setActiveTab('verdicts')}
          className={`py-3 px-4 border-b-2 transition flex items-center gap-2 ${
            activeTab === 'verdicts'
              ? 'border-indigo-500 text-indigo-400 bg-indigo-950/20'
              : 'border-transparent text-slate-400 hover:text-slate-200'
          }`}
        >
          <Info className="w-4 h-4" />
          <span>Taxonomía de 4 Veredictos</span>
        </button>
      </div>

      {/* Tab Contents */}
      <div className="p-5">
        {loading && (
          <div className="py-8 text-center text-slate-400 text-sm animate-pulse">
            Cargando evaluación de completitud documental...
          </div>
        )}

        {/* TAB 1: Matriz de Entregables */}
        {!loading && activeTab === 'matrix' && evaluation && (
          <div className="space-y-3">
            {evaluation.deliverables_matrix.map((item) => {
              const req = item.requirement;
              const isExpanded = expandedRequirementId === req.id;
              const hasProvided = item.provided_documents && item.provided_documents.length > 0;

              return (
                <div
                  key={req.id}
                  className="border border-slate-800 rounded-lg bg-slate-950/50 overflow-hidden transition"
                >
                  <div
                    onClick={() => toggleExpand(req.id)}
                    className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-slate-800/40 transition select-none"
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-1.5 bg-slate-800 rounded text-slate-300">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-slate-200">{req.title}</span>
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                            {req.discipline}
                          </span>
                          {req.is_mandatory ? (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-rose-950/60 text-rose-300 border border-rose-800/60 font-semibold">
                              Obligatorio
                            </span>
                          ) : (
                            <span className="text-[10px] px-2 py-0.5 rounded bg-slate-800 text-slate-400">
                              Opcional
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-400 mt-0.5">{req.description}</p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {getStatusBadge(item.status)}
                      <div className="text-slate-500">
                        {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                      </div>
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <div className="p-4 border-t border-slate-800/80 bg-slate-900/70 space-y-3 text-xs">
                      {/* Documentos asociados */}
                      <div>
                        <div className="font-semibold text-slate-300 mb-2">
                          Documentos Provistos ({item.provided_documents?.length || 0}):
                        </div>
                        {hasProvided ? (
                          <div className="space-y-2">
                            {item.provided_documents.map((doc) => (
                              <div
                                key={doc.document_id}
                                className="p-2.5 bg-slate-950 rounded-lg border border-slate-800 flex items-center justify-between"
                              >
                                <div>
                                  <div className="font-medium text-slate-200">{doc.document_filename}</div>
                                  <div className="text-[11px] text-slate-400 mt-0.5">
                                    Estado: <span className="font-semibold text-slate-300">{doc.readiness_status}</span>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2">
                                  {doc.is_eligible ? (
                                    <span className="px-2 py-0.5 bg-emerald-950 text-emerald-300 border border-emerald-700 rounded text-[11px] font-semibold">
                                      ✓ Apto como Evidencia
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 bg-amber-950 text-amber-300 border border-amber-700 rounded text-[11px] font-semibold">
                                      Requiere Promoción
                                    </span>
                                  )}
                                  {onDocumentClassifyClick && (
                                    <button
                                      onClick={() => onDocumentClassifyClick(doc.document_id)}
                                      className="px-2.5 py-1 bg-indigo-600/30 hover:bg-indigo-600 text-indigo-300 hover:text-white rounded border border-indigo-500/40 text-[11px] transition"
                                    >
                                      Cambiar Estado
                                    </button>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-slate-400 text-xs italic">
                            No se ha cargado ni clasificado ningún documento para este tipo de entregable ({req.deliverable_type}).
                          </div>
                        )}
                      </div>

                      {/* Reglas que bloquea si falta */}
                      {req.blocked_rule_codes && req.blocked_rule_codes.length > 0 && (
                        <div className="pt-2 border-t border-slate-800">
                          <div className="font-semibold text-amber-400 mb-1 flex items-center gap-1.5">
                            <Lock className="w-3.5 h-3.5" />
                            <span>Reglas dependientes (se bloquean si no está Apto como Evidencia):</span>
                          </div>
                          <div className="flex flex-wrap gap-1.5 mt-1">
                            {req.blocked_rule_codes.map((rc) => (
                              <span
                                key={rc}
                                className="px-2 py-0.5 bg-amber-950/60 text-amber-300 border border-amber-800/60 rounded text-[10px] font-mono font-medium"
                              >
                                {rc}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}

        {/* TAB 2: Reglas Bloqueadas */}
        {!loading && activeTab === 'blocked' && evaluation && (
          <div>
            {evaluation.blocked_rules.length === 0 ? (
              <div className="p-8 text-center bg-slate-950/40 rounded-xl border border-slate-800">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto mb-2" />
                <h4 className="text-base font-semibold text-white">¡No hay reglas bloqueadas!</h4>
                <p className="text-xs text-slate-400 mt-1">
                  Todos los entregables obligatorios están en estado <strong>Apto como Evidencia</strong>. El motor QA/QC
                  puede ejecutar la auditoría técnica completa.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="p-3 bg-amber-950/30 border border-amber-800/50 rounded-lg text-xs text-amber-300 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 flex-shrink-0 text-amber-400" />
                  <span>
                    Las siguientes <strong>{evaluation.blocked_rules.length} reglas</strong> pasarán automáticamente al
                    veredicto <strong>NO_VERIFICABLE (Bloqueo Documental)</strong> al ejecutar la auditoría técnica:
                  </span>
                </div>

                <div className="divide-y divide-slate-800 border border-slate-800 rounded-lg overflow-hidden bg-slate-950/40">
                  {evaluation.blocked_rules.map((br, idx) => (
                    <div key={idx} className="p-3.5 flex flex-col md:flex-row md:items-center justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs font-bold text-amber-400">{br.rule_code}</span>
                          <span className="text-xs font-semibold text-slate-200">— {br.rule_name}</span>
                        </div>
                        <p className="text-xs text-slate-400 mt-1">{br.detail}</p>
                      </div>

                      <div className="flex-shrink-0">
                        <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-rose-950/60 text-rose-300 border border-rose-800/60 text-xs font-medium">
                          Falta: {br.blocked_by_deliverable_title}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 3: Taxonomía de 4 Veredictos */}
        {!loading && activeTab === 'verdicts' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="p-4 bg-emerald-950/20 border border-emerald-800/40 rounded-lg">
              <div className="flex items-center gap-2 text-emerald-400 font-bold text-sm mb-1">
                <CheckCircle2 className="w-4 h-4" /> 1. CUMPLE
              </div>
              <p className="text-xs text-slate-300">
                La evidencia provista satisface al 100% el criterio normativo o regla QA/QC evaluada (conteo concordante,
                campos de viñeta completos, dimensiones normativas válidas).
              </p>
            </div>

            <div className="p-4 bg-rose-950/20 border border-rose-800/40 rounded-lg">
              <div className="flex items-center gap-2 text-rose-400 font-bold text-sm mb-1">
                <XCircle className="w-4 h-4" /> 2. NO_CUMPLE
              </div>
              <p className="text-xs text-slate-300">
                Se detecta una discrepancia o incumplimiento explícito sobre evidencia válida (e.g. ancho de puerta menor
                al mínimo normativo de 0.90 m, discrepancia numérica entre plano y cuadro).
              </p>
            </div>

            <div className="p-4 bg-amber-950/20 border border-amber-800/40 rounded-lg">
              <div className="flex items-center gap-2 text-amber-400 font-bold text-sm mb-1">
                <AlertTriangle className="w-4 h-4" /> 3. NO_VERIFICABLE (Diferenciado)
              </div>
              <p className="text-xs text-slate-300 mb-2">
                No puede emitirse veredicto determinístico. Se desglosa en 3 motivos canónicos:
              </p>
              <ul className="text-[11px] text-slate-400 space-y-1 list-disc list-inside">
                <li><strong className="text-amber-300">Faltante Menor:</strong> No bloquea pero requiere advertencia.</li>
                <li><strong className="text-amber-300">Evidencia Insuficiente:</strong> Texto borroso o incompleto.</li>
                <li><strong className="text-amber-300">Bloqueo Documental:</strong> Falta entregable obligatorio en la etapa.</li>
              </ul>
            </div>

            <div className="p-4 bg-slate-900 border border-slate-800 rounded-lg">
              <div className="flex items-center gap-2 text-slate-400 font-bold text-sm mb-1">
                <HelpCircle className="w-4 h-4" /> 4. NO_APLICA
              </div>
              <p className="text-xs text-slate-300">
                La lámina o documento no contiene elementos pertenecientes a la disciplina o alcance de la regla (e.g. regla
                de puertas en plano de fundaciones).
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
