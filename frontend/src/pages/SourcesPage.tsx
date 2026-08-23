import React, { useEffect, useState } from 'react';
import {
  FileText, Globe, CheckCircle2, XCircle, ArrowRight,
  Filter, Plus, RefreshCw, ShieldAlert, ShieldCheck, Database,
  Sparkles, AlertCircle, Check, X, Tag, BookOpen, Layers,
  HardDrive, UploadCloud, Trash2, Paperclip, ExternalLink,
  Search, Eye, HelpCircle, Archive, Bot
} from 'lucide-react';
import { apiService } from '../services/api';
import { SourceAssetItem, SourceType, ApprovalStatus, ResearchQueryItem } from '../types';
import { SourceExtractionReviewModal } from '../components/SourceExtractionReviewModal';
import { DocumentManualViewerModal } from '../components/DocumentManualViewerModal';
import { ProcessWithAiModal } from '../components/ProcessWithAiModal';
import { DeleteSourceModal } from '../components/DeleteSourceModal';
import { AssistantCopilotDrawer } from '../components/AssistantCopilotDrawer';

export const BASE_DISCIPLINES = [
  'Arquitectura',
  'Estructuras',
  'Mecánica',
  'Eléctrica',
  'Instrumentación',
  'Piping'
];

const STORAGE_KEY_CUSTOM_DISCIPLINES = 'plan_review_custom_disciplines';

export const getStoredCustomDisciplines = (): string[] => {
  try {
    const raw = localStorage.getItem(STORAGE_KEY_CUSTOM_DISCIPLINES);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
};

export const saveCustomDiscipline = (newDisc: string): string[] => {
  try {
    const current = getStoredCustomDisciplines();
    if (!current.some((d) => d.trim().toLowerCase() === newDisc.trim().toLowerCase())) {
      const updated = [...current, newDisc.trim()];
      localStorage.setItem(STORAGE_KEY_CUSTOM_DISCIPLINES, JSON.stringify(updated));
      return updated;
    }
    return current;
  } catch (e) {
    console.error('Error al guardar disciplina personalizada en localStorage:', e);
    return [];
  }
};

export const SourcesPage: React.FC = () => {
  const [sources, setSources] = useState<SourceAssetItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [approvalFilter, setApprovalFilter] = useState<string>('');
  const [disciplineFilter, setDisciplineFilter] = useState<string>('');
  
  // Pestaña activa (Fuentes Documentales vs Investigaciones Web)
  const [activeTab, setActiveTab] = useState<'sources' | 'research'>('sources');

  // Investigaciones Web Persistidas
  const [researchQueries, setResearchQueries] = useState<ResearchQueryItem[]>([]);
  const [loadingResearch, setLoadingResearch] = useState(false);
  
  // Listado unificado de disciplinas (Base + LocalStorage + Backend)
  const [availableDisciplines, setAvailableDisciplines] = useState<string[]>(() => {
    const custom = getStoredCustomDisciplines();
    const merged = [...BASE_DISCIPLINES];
    custom.forEach((c) => {
      if (!merged.some((m) => m.toLowerCase() === c.toLowerCase())) {
        merged.push(c);
      }
    });
    return merged;
  });

  // Modal de registro con archivo local
  const [showModal, setShowModal] = useState(false);
  const [registrationMode, setRegistrationMode] = useState<'file' | 'web' | 'manual'>('file');
  const [newTitle, setNewTitle] = useState('');
  const [newType, setNewType] = useState<SourceType>('normative_document');
  const [newDiscipline, setNewDiscipline] = useState('Arquitectura');
  const [prevDiscipline, setPrevDiscipline] = useState('Arquitectura');
  const [newAuthority, setNewAuthority] = useState('MINVU');
  const [newUrl, setNewUrl] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [creating, setCreating] = useState(false);

  // Flujo para "Otros" (Crear nueva disciplina personalizada)
  const [isCreatingCustomDiscipline, setIsCreatingCustomDiscipline] = useState(false);
  const [customDisciplineInput, setCustomDisciplineInput] = useState('');
  const [customDisciplineError, setCustomDisciplineError] = useState<string | null>(null);

  // Modal de Eliminación segura
  const [sourceToDelete, setSourceToDelete] = useState<SourceAssetItem | null>(null);

  // Modales de Extracción de Conocimiento (CON IA y SIN IA)
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);
  const [showAiModal, setShowAiModal] = useState(false);
  const [aiTitle, setAiTitle] = useState('Ordenanza General de Urbanismo y Construcciones (OGUC)');
  const [aiDocType, setAiDocType] = useState('norma');
  const [aiDiscipline, setAiDiscipline] = useState('Arquitectura');
  const [aiAuthority, setAiAuthority] = useState('MINVU');
  const [aiTextContent, setAiTextContent] = useState('');
  const [aiSourceAssetId, setAiSourceAssetId] = useState<string | undefined>(undefined);

  // Modal Manual Sin IA (Visor continuo asistido)
  const [showManualModal, setShowManualModal] = useState(false);
  const [manualTitle, setManualTitle] = useState('Manual Técnico de Instalaciones y Evacuación');
  const [manualDocType, setManualDocType] = useState('manual');
  const [manualDiscipline, setManualDiscipline] = useState('Arquitectura');
  const [manualAuthority, setManualAuthority] = useState('MINVU / SEC');
  const [manualSourceId, setManualSourceId] = useState<string | undefined>(undefined);

  // Modal de Revisión y Validación de Extracciones
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [activeExtractionId, setActiveExtractionId] = useState<string | null>(null);

  // Notificación de éxito
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  useEffect(() => {
    loadSources();
    loadRemoteDisciplines();
    loadResearchQueries();
  }, [typeFilter, approvalFilter, disciplineFilter]);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 5000);
  };

  const loadRemoteDisciplines = async () => {
    try {
      const remote = await apiService.getDisciplines();
      if (Array.isArray(remote) && remote.length > 0) {
        setAvailableDisciplines((prev) => {
          const merged = [...prev];
          remote.forEach((r) => {
            if (r && !merged.some((m) => m.toLowerCase() === r.toLowerCase())) {
              merged.push(r);
            }
          });
          return merged;
        });
      }
    } catch (err) {
      console.warn('No se pudo cargar disciplinas remotas de intake:', err);
    }
  };

  const loadSources = async () => {
    try {
      setLoading(true);
      const data = await apiService.getSources({
        source_type: typeFilter || undefined,
        approval_status: approvalFilter || undefined,
        discipline: disciplineFilter || undefined,
      });
      setSources(data);

      if (Array.isArray(data)) {
        setAvailableDisciplines((prev) => {
          const merged = [...prev];
          data.forEach((s) => {
            if (s.discipline && !merged.some((m) => m.toLowerCase() === s.discipline.toLowerCase())) {
              merged.push(s.discipline);
            }
          });
          return merged;
        });
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const loadResearchQueries = async () => {
    try {
      setLoadingResearch(true);
      const queries = await apiService.getResearchQueries();
      setResearchQueries(queries);
    } catch (e) {
      console.warn('Error cargando investigaciones web:', e);
    } finally {
      setLoadingResearch(false);
    }
  };

  const handleOpenModal = () => {
    setIsCreatingCustomDiscipline(false);
    setCustomDisciplineInput('');
    setCustomDisciplineError(null);
    setSelectedFile(null);
    setRegistrationMode('file');
    setNewType('normative_document');
    setNewTitle('');
    setNewUrl('');
    setNewDescription('');
    setNewAuthority('MINVU');
    if (!newDiscipline || newDiscipline === '__OTHER__') {
      setNewDiscipline(availableDisciplines[0] || 'Arquitectura');
    }
    setPrevDiscipline(newDiscipline || 'Arquitectura');
    setShowModal(true);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      if (!newTitle.trim()) {
        // Auto-asignar nombre limpio del archivo como título sugerido
        const cleanName = file.name.replace(/\.[^/.]+$/, '').replace(/[_-]/g, ' ');
        setNewTitle(cleanName);
      }
    }
  };

  const handleDisciplineChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const value = e.target.value;
    if (value === '__OTHER__') {
      setPrevDiscipline(newDiscipline);
      setIsCreatingCustomDiscipline(true);
      setCustomDisciplineInput('');
      setCustomDisciplineError(null);
    } else {
      setNewDiscipline(value);
      setPrevDiscipline(value);
    }
  };

  const handleConfirmCustomDiscipline = () => {
    const trimmed = customDisciplineInput.trim();
    if (!trimmed) {
      setCustomDisciplineError('El nombre de la disciplina no puede estar vacío.');
      return;
    }

    const duplicateMatch = availableDisciplines.find(
      (d) => d.toLowerCase() === trimmed.toLowerCase()
    );
    if (duplicateMatch) {
      setCustomDisciplineError(`La disciplina "${duplicateMatch}" ya existe en el listado.`);
      return;
    }

    saveCustomDiscipline(trimmed);
    setAvailableDisciplines((prev) => [...prev, trimmed]);
    setNewDiscipline(trimmed);
    setPrevDiscipline(trimmed);
    setIsCreatingCustomDiscipline(false);
    setCustomDisciplineInput('');
    setCustomDisciplineError(null);
  };

  const handleCancelCustomDiscipline = () => {
    setIsCreatingCustomDiscipline(false);
    setCustomDisciplineInput('');
    setCustomDisciplineError(null);
    setNewDiscipline(prevDiscipline || availableDisciplines[0] || 'Arquitectura');
  };

  const handleApprove = async (sourceId: string, approved: boolean) => {
    try {
      await apiService.approveSource(
        sourceId,
        approved,
        approved ? 'Aprobado por auditor técnico en interfaz de gobierno.' : 'Rechazado por auditor.',
        'auditor_qa'
      );
      showToast(approved ? 'Fuente APROBADA exitosamente.' : 'Fuente RECHAZADA.');
      loadSources();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al actualizar aprobación.');
    }
  };

  const handleIngest = async (source: SourceAssetItem) => {
    try {
      const res = await apiService.ingestSource(source.id);
      showToast(`Ingesta completada: ${res.message}`);
      loadSources();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error durante la ingestión.');
    }
  };

  // Crear Fuente (Local con Archivo o JSON)
  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTitle.trim()) return;

    let finalDiscipline = newDiscipline;

    if (isCreatingCustomDiscipline) {
      const trimmed = customDisciplineInput.trim();
      if (!trimmed) {
        setCustomDisciplineError('Por favor ingrese el nombre de la disciplina o presione Cancelar.');
        return;
      }
      const duplicateMatch = availableDisciplines.find(
        (d) => d.toLowerCase() === trimmed.toLowerCase()
      );
      if (duplicateMatch) {
        finalDiscipline = duplicateMatch;
      } else {
        saveCustomDiscipline(trimmed);
        setAvailableDisciplines((prev) => [...prev, trimmed]);
        finalDiscipline = trimmed;
      }
      setIsCreatingCustomDiscipline(false);
      setCustomDisciplineInput('');
      setCustomDisciplineError(null);
      setNewDiscipline(finalDiscipline);
    }

    try {
      setCreating(true);

      if (registrationMode === 'file') {
        if (!selectedFile) {
          alert('Por favor seleccione un archivo local desde su equipo antes de guardar, o cambie al modo Manual / Web.');
          setCreating(false);
          return;
        }
        // Carga física de archivo local en volumen persistente
        const formData = new FormData();
        formData.append('file', selectedFile);
        formData.append('title', newTitle.trim());
        formData.append('source_type', newType);
        formData.append('discipline', finalDiscipline);
        formData.append('document_type', newType === 'analysis_document' ? 'blueprint_pdf' : 'standard_doc');
        formData.append('authority', newAuthority.trim() || 'Organismo Técnico');
        if (newDescription.trim()) {
          formData.append('description', newDescription.trim());
        }

        const res = await apiService.uploadSourceFile(formData);
        showToast(`Documento local '${res.title}' guardado físicamente en volumen persistente.`);
      } else {
        if (registrationMode === 'web' && !newUrl.trim()) {
          alert('Por favor ingrese la URL de la fuente normativa web.');
          setCreating(false);
          return;
        }
        // Registro de fuente Web o Manual
        await apiService.registerSource({
          source_type: newType,
          title: newTitle.trim(),
          discipline: finalDiscipline as any,
          source_origin: registrationMode === 'web' ? 'web_scrape' : 'manual_entry',
          source_url: newUrl.trim() || undefined,
          description: newDescription.trim() || undefined,
          metadata_payload: {
            authority: newAuthority.trim() || 'MINVU / Regulador'
          }
        });
        showToast('Nueva fuente registrada en intake con éxito.');
      }

      setShowModal(false);
      setSelectedFile(null);
      setNewTitle('');
      setNewUrl('');
      setNewDescription('');
      setIsCreatingCustomDiscipline(false);
      loadSources();
      loadRemoteDisciplines();
    } catch (err: any) {
      console.error(err);
      alert(err.response?.data?.detail || 'Error al registrar fuente.');
    } finally {
      setCreating(false);
    }
  };

  // Disparar procesamiento con IA desde fila de tabla usando el archivo persistido
  const handleProcessRowWithAi = (s: SourceAssetItem) => {
    setAiTitle(s.title);
    setAiDocType(s.source_type === 'normative_document' ? 'norma' : 'manual');
    setAiDiscipline(s.discipline || 'Arquitectura');
    setAiAuthority((s.metadata_payload?.authority as string) || 'MINVU');
    setAiTextContent(s.description || '');
    setAiSourceAssetId(s.id);
    setShowAiModal(true);
  };

  // Disparar procesamiento sin IA desde fila de tabla usando el archivo persistido
  const handleProcessRowWithoutAi = (s: SourceAssetItem) => {
    setManualTitle(s.title);
    setManualDocType(s.source_type === 'normative_document' ? 'norma' : 'manual');
    setManualDiscipline(s.discipline || 'Arquitectura');
    setManualAuthority((s.metadata_payload?.authority as string) || 'MINVU');
    setManualSourceId(s.id);
    setShowManualModal(true);
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes || bytes <= 0) return '';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  const getApprovalBadge = (status: ApprovalStatus) => {
    switch (status) {
      case 'approved':
        return <span className="badge badge-success">✓ Aprobado</span>;
      case 'rejected':
        return <span className="badge badge-critical">✕ Rechazado</span>;
      case 'pending_review':
        return <span className="badge badge-medium">⏳ Pendiente Revisión</span>;
      default:
        return <span className="badge badge-info">No requerida</span>;
    }
  };

  return (
    <div className="page-container">
      
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

      {/* Cabecera Principal con los 3 Botones de Acción */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '24px', fontWeight: 800, display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Database size={24} style={{ color: 'var(--primary)' }} />
            Intake & Incorporación de Fuentes
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px', marginTop: '4px' }}>
            Almacenamiento persistente de documentos locales y repositorio estructurado de conocimiento investigado en Internet.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
          {/* Botón 1: Registrar Fuente */}
          <button className="btn btn-secondary" onClick={handleOpenModal} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <Plus size={16} />
            <span>Registrar Nueva Fuente</span>
          </button>

          {/* Botón 2: Procesar con IA */}
          <button
            className="btn btn-primary"
            onClick={() => {
              setAiTitle('Ordenanza General de Urbanismo y Construcciones (OGUC)');
              setAiDocType('norma');
              setAiDiscipline('Arquitectura');
              setAiAuthority('MINVU');
              setAiTextContent('');
              setAiSourceAssetId(undefined);
              setShowAiModal(true);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, #0d9488 0%, #059669 100%)',
              border: 'none',
              boxShadow: '0 4px 14px rgba(13, 148, 136, 0.35)'
            }}
          >
            <Sparkles size={16} />
            <span>Procesar con IA</span>
          </button>

          {/* Botón 3: Procesar sin IA */}
          <button
            className="btn btn-secondary"
            onClick={() => {
              setManualTitle('Manual Técnico de Instalaciones y Evacuación');
              setManualDocType('manual');
              setManualDiscipline('Arquitectura');
              setManualAuthority('MINVU / SEC');
              setManualSourceId(undefined);
              setShowManualModal(true);
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              borderColor: '#0284c7',
              color: '#38bdf8'
            }}
          >
            <BookOpen size={16} />
            <span>Procesar sin IA</span>
          </button>

          {/* Botón 4: Asistente Copilot RAG */}
          <button
            className="btn btn-primary"
            onClick={() => setIsCopilotOpen(true)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              background: 'linear-gradient(135deg, var(--primary), var(--accent))',
              fontWeight: 700
            }}
          >
            <Bot size={16} />
            <span>Asistente Copilot</span>
          </button>
        </div>
      </div>

      <AssistantCopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        initialTaskType="normative_query"
      />

      {/* Selector de Pestañas Principales */}
      <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '20px' }}>
        <button
          onClick={() => setActiveTab('sources')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: 600,
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'sources' ? '2px solid var(--primary)' : '2px solid transparent',
            color: activeTab === 'sources' ? 'var(--primary)' : 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <HardDrive size={16} />
          <span>Documentos & Fuentes Registradas ({sources.length})</span>
        </button>

        <button
          onClick={() => setActiveTab('research')}
          style={{
            padding: '10px 18px',
            fontSize: '13px',
            fontWeight: 600,
            background: 'none',
            border: 'none',
            borderBottom: activeTab === 'research' ? '2px solid #818cf8' : '2px solid transparent',
            color: activeTab === 'research' ? '#818cf8' : 'var(--text-muted)',
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            gap: '8px'
          }}
        >
          <Globe size={16} />
          <span>Investigaciones en Internet Persistidas ({researchQueries.length})</span>
        </button>
      </div>

      {/* ========================================================= */}
      {/* VISTA 1: FUENTES Y DOCUMENTOS REGISTRADOS */}
      {/* ========================================================= */}
      {activeTab === 'sources' && (
        <>
          {/* Barra de Filtros */}
          <div className="card" style={{ marginBottom: '20px', display: 'flex', gap: '16px', alignItems: 'center', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Filter size={16} color="var(--text-dim)" />
              <span style={{ fontSize: '13px', fontWeight: 600 }}>Filtros:</span>
            </div>

            <div>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value)}
                style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
              >
                <option value="">Todos los tipos</option>
                <option value="analysis_document">Documento de Análisis (Plano)</option>
                <option value="normative_document">Documento Normativo</option>
                <option value="template_document">Plantilla de Viñeta</option>
                <option value="symbol_reference">Catálogo de Símbolos</option>
                <option value="web_normative_source">Norma Web</option>
              </select>
            </div>

            <div>
              <select
                value={approvalFilter}
                onChange={(e) => setApprovalFilter(e.target.value)}
                style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
              >
                <option value="">Todos los estados de aprobación</option>
                <option value="pending_review">Pendiente de Revisión</option>
                <option value="approved">Aprobado</option>
                <option value="rejected">Rechazado</option>
                <option value="not_required">No requerida</option>
              </select>
            </div>

            <div>
              <select
                value={disciplineFilter}
                onChange={(e) => setDisciplineFilter(e.target.value)}
                style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '6px 12px', borderRadius: '6px', fontSize: '13px' }}
              >
                <option value="">Todas las disciplinas</option>
                {availableDisciplines.map((d) => (
                  <option key={d} value={d}>{d}</option>
                ))}
              </select>
            </div>

            <button className="btn btn-secondary" onClick={loadSources} style={{ marginLeft: 'auto', padding: '6px 12px' }}>
              <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
              <span>Actualizar</span>
            </button>
          </div>

          {/* Tabla de Fuentes Registradas */}
          <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
              <thead>
                <tr style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                  <th style={{ padding: '12px 16px' }}>Título / Documento</th>
                  <th style={{ padding: '12px 16px' }}>Almacenamiento / Archivo</th>
                  <th style={{ padding: '12px 16px' }}>Tipo</th>
                  <th style={{ padding: '12px 16px' }}>Disciplina</th>
                  <th style={{ padding: '12px 16px' }}>Memoria Destino</th>
                  <th style={{ padding: '12px 16px' }}>Aprobación</th>
                  <th style={{ padding: '12px 16px' }}>Estado</th>
                  <th style={{ padding: '12px 16px', textAlign: 'right' }}>Acciones & Extracción</th>
                </tr>
              </thead>
              <tbody>
                {sources.length > 0 ? (
                  sources.map((s) => (
                    <tr key={s.id} style={{ borderBottom: '1px solid var(--border-subtle)', transition: 'background 0.15s' }}>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{s.title}</div>
                        {s.description && (
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {s.description}
                          </div>
                        )}
                        <div style={{ fontSize: '10px', color: 'var(--text-dim)', marginTop: '2px', fontFamily: 'monospace' }}>
                          ID: {s.id.slice(0, 8)} • v{s.version}
                        </div>
                      </td>

                      {/* Almacenamiento / Archivo Local */}
                      <td style={{ padding: '14px 16px' }}>
                        {s.file_path ? (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', background: 'rgba(59, 130, 246, 0.1)', border: '1px solid rgba(59, 130, 246, 0.3)', padding: '3px 8px', borderRadius: '4px', fontSize: '11px', color: '#93c5fd' }}>
                            <HardDrive size={13} style={{ color: '#60a5fa' }} />
                            <span style={{ fontWeight: 500 }}>
                              {s.original_filename || 'Archivo Local'}
                            </span>
                            {s.file_size_bytes ? (
                              <span style={{ color: 'var(--text-dim)', fontSize: '10px' }}>
                                ({formatBytes(s.file_size_bytes)})
                              </span>
                            ) : null}
                          </div>
                        ) : s.source_url ? (
                          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: '#a5b4fc', fontSize: '11px' }}>
                            <Globe size={13} />
                            <a href={s.source_url} target="_blank" rel="noreferrer" style={{ color: '#a5b4fc', textDecoration: 'underline' }}>
                              Enlace Web
                            </a>
                          </div>
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>✍️ Entrada Manual</span>
                        )}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span className="badge badge-medium" style={{ fontSize: '11px' }}>{s.source_type}</span>
                      </td>

                      <td style={{ padding: '14px 16px', color: 'var(--text-muted)' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', background: 'rgba(255,255,255,0.05)', padding: '2px 8px', borderRadius: '4px', fontWeight: 500 }}>
                          <Tag size={11} color="var(--primary)" />
                          {s.discipline}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span style={{ fontWeight: 600, fontSize: '12px', color: s.linked_memory_target === 'document_memory' ? 'var(--primary)' : s.linked_memory_target === 'normative_memory' ? '#10b981' : '#a855f7' }}>
                          {s.linked_memory_target}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        {getApprovalBadge(s.approval_status)}
                      </td>

                      <td style={{ padding: '14px 16px' }}>
                        <span className={`badge ${s.status === 'ingested' ? 'badge-success' : s.status === 'extracted' ? 'badge-info' : s.status === 'archived' ? 'badge-neutral' : s.status === 'rejected' ? 'badge-critical' : 'badge-medium'}`}>
                          {s.status === 'extracted' ? '✨ Extraído' : s.status === 'ingested' ? '✓ Ingestado' : s.status === 'archived' ? '📦 Archivado' : s.status}
                        </span>
                      </td>

                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end', flexWrap: 'wrap' }}>
                          
                          {/* Botón rápido: Procesar con IA (reutiliza el archivo local guardado) */}
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px', color: '#2dd4bf', borderColor: 'rgba(45, 212, 191, 0.4)' }}
                            onClick={() => handleProcessRowWithAi(s)}
                            title="Extraer estructuradamente normas y reglas con IA desde el archivo persistido"
                          >
                            <Sparkles size={12} />
                            <span>Con IA</span>
                          </button>

                          {/* Botón rápido: Procesar sin IA (visor manual asistido) */}
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '11px', color: '#38bdf8', borderColor: 'rgba(56, 189, 248, 0.4)' }}
                            onClick={() => handleProcessRowWithoutAi(s)}
                            title="Abrir visor continuo asistido sin IA"
                          >
                            <BookOpen size={12} />
                            <span>Sin IA</span>
                          </button>

                          {s.approval_status === 'pending_review' && (
                            <>
                              <button
                                className="btn btn-primary"
                                style={{ padding: '4px 8px', fontSize: '11px', background: 'var(--success)' }}
                                onClick={() => handleApprove(s.id, true)}
                                title="Aprobar fuente para alimentar memoria"
                              >
                                Aprobar
                              </button>
                              <button
                                className="btn btn-secondary"
                                style={{ padding: '4px 8px', fontSize: '11px', color: 'var(--danger)' }}
                                onClick={() => handleApprove(s.id, false)}
                                title="Rechazar fuente"
                              >
                                Rechazar
                              </button>
                            </>
                          )}

                          {(s.approval_status === 'approved' || s.approval_status === 'not_required') && s.status === 'registered' && (
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '4px 8px', fontSize: '11px' }}
                              onClick={() => handleIngest(s)}
                              title="Direccionar e ingestar hacia memoria objetivo"
                            >
                              <Database size={12} />
                              <span>Ingestar</span>
                            </button>
                          )}

                          {/* Botón Eliminar: Modal Seguro */}
                          <button
                            className="btn btn-secondary"
                            style={{ padding: '4px 7px', fontSize: '11px', color: '#f87171', borderColor: 'rgba(239, 68, 68, 0.3)' }}
                            onClick={() => setSourceToDelete(s)}
                            title="Eliminar o archivar fuente de intake y storage"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr>
                    <td colSpan={8} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
                      No se encontraron fuentes con los filtros seleccionados.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* ========================================================= */}
      {/* VISTA 2: HISTÓRICO DE INVESTIGACIONES EN INTERNET */}
      {/* ========================================================= */}
      {activeTab === 'research' && (
        <div className="card" style={{ padding: '0', overflow: 'hidden' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', margin: 0 }}>
                Repositorio Estructurado de Investigaciones Web
              </h3>
              <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: '2px 0 0 0' }}>
                Consultas, citas recuperadas y reglas técnicas de apoyo listas para revisión y re-extracción.
              </p>
            </div>
            <button className="btn btn-secondary" onClick={loadResearchQueries} style={{ padding: '5px 12px', fontSize: '12px' }}>
              <RefreshCw size={13} className={loadingResearch ? 'animate-spin' : ''} />
              <span>Actualizar</span>
            </button>
          </div>

          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
            <thead>
              <tr style={{ background: 'var(--bg-sidebar)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-muted)' }}>
                <th style={{ padding: '12px 16px' }}>Prompt / Tema Investigado</th>
                <th style={{ padding: '12px 16px' }}>Disciplina</th>
                <th style={{ padding: '12px 16px' }}>Áreas de Enfoque</th>
                <th style={{ padding: '12px 16px' }}>Fuentes Web</th>
                <th style={{ padding: '12px 16px' }}>Reglas Propuestas</th>
                <th style={{ padding: '12px 16px' }}>Fecha</th>
                <th style={{ padding: '12px 16px', textAlign: 'right' }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {researchQueries.length > 0 ? (
                researchQueries.map((rq) => (
                  <tr key={rq.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ fontWeight: 600, color: 'var(--text-main)' }}>{rq.search_prompt}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '2px' }}>
                        Autoridad: {rq.authority || 'MINVU / Web Research'}
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span className="badge badge-info font-mono" style={{ fontSize: '11px' }}>{rq.discipline}</span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <div style={{ display: 'flex', gap: '4px', flexWrap: 'wrap' }}>
                        {rq.focus_areas && rq.focus_areas.length > 0 ? (
                          rq.focus_areas.map((f, i) => (
                            <span key={i} style={{ background: 'rgba(255,255,255,0.06)', padding: '2px 6px', borderRadius: '4px', fontSize: '10px' }}>
                              {f}
                            </span>
                          ))
                        ) : (
                          <span style={{ color: 'var(--text-dim)', fontSize: '11px' }}>General</span>
                        )}
                      </div>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ color: '#60a5fa', fontWeight: 600, fontSize: '12px' }}>
                        🌐 {rq.total_sources_count} citas
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px' }}>
                      <span style={{ color: '#34d399', fontWeight: 600, fontSize: '12px' }}>
                        ⚡ {rq.total_items_count} elementos
                      </span>
                    </td>
                    <td style={{ padding: '14px 16px', color: 'var(--text-muted)', fontSize: '11px' }}>
                      {new Date(rq.created_at).toLocaleDateString()}
                    </td>
                    <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                      <button
                        className="btn btn-secondary"
                        style={{ padding: '4px 10px', fontSize: '11px', color: '#a5b4fc', borderColor: 'rgba(165, 180, 252, 0.4)' }}
                        onClick={() => {
                          setAiTitle(`Investigación: ${rq.search_prompt}`);
                          setAiDocType(rq.document_type || 'norma');
                          setAiDiscipline(rq.discipline);
                          setAiAuthority(rq.authority || 'MINVU');
                          setShowAiModal(true);
                        }}
                        title="Re-ejecutar o afinar investigación"
                      >
                        <RefreshCw size={11} />
                        <span>Re-analizar</span>
                      </button>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={7} style={{ padding: '30px', textAlign: 'center', color: 'var(--text-dim)' }}>
                    No hay investigaciones web guardadas aún. Utilice «Procesar con IA → Opción 2» para generar nuevas investigaciones.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL: REGISTRAR NUEVA FUENTE CON CARGA DE ARCHIVO LOCAL */}
      {/* ========================================================= */}
      {showModal && (
        <div className="modal-overlay">
          <div className="modal-content" style={{ maxWidth: '560px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <HardDrive size={20} style={{ color: 'var(--primary)' }} />
                <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0 }}>Registrar Nueva Fuente</h2>
              </div>
              <button onClick={() => setShowModal(false)} style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateSource}>
              
              {/* Selector de Modo de Incorporación */}
              <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                <button
                  type="button"
                  onClick={() => setRegistrationMode('file')}
                  style={{
                    flex: 1,
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: registrationMode === 'file' ? 'rgba(59, 130, 246, 0.15)' : 'var(--bg-sidebar)',
                    border: `1px solid ${registrationMode === 'file' ? 'rgba(59, 130, 246, 0.5)' : 'var(--border-subtle)'}`,
                    color: registrationMode === 'file' ? '#93c5fd' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <Paperclip size={14} />
                  <span>Documento Local (Archivo)</span>
                </button>

                <button
                  type="button"
                  onClick={() => setRegistrationMode('web')}
                  style={{
                    flex: 1,
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: registrationMode === 'web' ? 'rgba(129, 140, 248, 0.15)' : 'var(--bg-sidebar)',
                    border: `1px solid ${registrationMode === 'web' ? 'rgba(129, 140, 248, 0.5)' : 'var(--border-subtle)'}`,
                    color: registrationMode === 'web' ? '#a5b4fc' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <Globe size={14} />
                  <span>Norma Web / URL</span>
                </button>

                <button
                  type="button"
                  onClick={() => setRegistrationMode('manual')}
                  style={{
                    flex: 1,
                    padding: '8px',
                    borderRadius: '6px',
                    fontSize: '12px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    background: registrationMode === 'manual' ? 'rgba(255, 255, 255, 0.08)' : 'var(--bg-sidebar)',
                    border: `1px solid ${registrationMode === 'manual' ? 'rgba(255, 255, 255, 0.2)' : 'var(--border-subtle)'}`,
                    color: registrationMode === 'manual' ? 'var(--text-main)' : 'var(--text-muted)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '6px'
                  }}
                >
                  <span>✍️ Manual</span>
                </button>
              </div>

              {/* Selector de Archivo Físico (File Picker) */}
              {registrationMode === 'file' && (
                <div style={{
                  marginBottom: '16px',
                  padding: '16px',
                  border: '2px dashed rgba(59, 130, 246, 0.4)',
                  borderRadius: '8px',
                  background: 'rgba(59, 130, 246, 0.04)',
                  textAlign: 'center'
                }}>
                  <input
                    type="file"
                    id="intakeFileInput"
                    accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                    onChange={handleFileChange}
                    style={{ display: 'none' }}
                  />
                  <label htmlFor="intakeFileInput" style={{ cursor: 'pointer', display: 'block' }}>
                    <UploadCloud size={28} style={{ color: '#60a5fa', margin: '0 auto 6px auto' }} />
                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-main)' }}>
                      {selectedFile ? selectedFile.name : 'Haz clic para seleccionar un documento local'}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
                      {selectedFile ? (
                        <span style={{ color: '#34d399', fontWeight: 500 }}>
                          Archivo listo para persistir en volumen ({formatBytes(selectedFile.size)})
                        </span>
                      ) : (
                        'Formatos soportados: PDF, DOC/DOCX, PNG, JPG (Se guardará en /data/intake_sources/)'
                      )}
                    </div>
                  </label>
                </div>
              )}

              {/* Título de la Fuente */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Título / Nombre de la Fuente
                </label>
                <input
                  type="text"
                  required
                  placeholder="Ej: OGUC Título 4 - Seguridad Contra Incendios"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                />
              </div>

              {/* Tipo de Fuente */}
              <div style={{ marginBottom: '14px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Tipo de Fuente</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value as SourceType)}
                  style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                >
                  <option value="normative_document">Documento Normativo (Norma / Decreto / Manual)</option>
                  <option value="analysis_document">Documento de Análisis (Plano PDF)</option>
                  <option value="template_document">Plantilla de Viñeta / Cajetín</option>
                  <option value="symbol_reference">Catálogo / Simbología</option>
                  <option value="web_normative_source">Norma Web (IA Scraper)</option>
                </select>
              </div>

              {registrationMode === 'web' && (
                <div style={{ marginBottom: '14px' }}>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>URL de la Fuente Web</label>
                  <input
                    type="url"
                    placeholder="https://www.minvu.gob.cl/oguc-capitulo-4"
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                  />
                </div>
              )}

              {/* Autoridad & Disciplina */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '14px' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Autoridad / Emisor</label>
                  <input
                    type="text"
                    placeholder="MINVU, SEC, INN, etc."
                    value={newAuthority}
                    onChange={(e) => setNewAuthority(e.target.value)}
                    style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                  />
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Disciplina</label>
                  <select
                    value={isCreatingCustomDiscipline ? '__OTHER__' : newDiscipline}
                    onChange={handleDisciplineChange}
                    style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                  >
                    {availableDisciplines.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                    <option value="__OTHER__">+ Otra disciplina (especificar)...</option>
                  </select>
                </div>
              </div>

              {isCreatingCustomDiscipline && (
                <div style={{ marginBottom: '14px', padding: '12px', background: 'rgba(56, 189, 248, 0.06)', border: '1px solid rgba(56, 189, 248, 0.3)', borderRadius: '8px' }}>
                  <label style={{ display: 'block', fontSize: '11px', fontWeight: 600, color: 'var(--primary)', marginBottom: '6px' }}>
                    Especifique el nombre de la nueva disciplina:
                  </label>
                  <input
                    type="text"
                    autoFocus
                    placeholder="Ej: Seguridad y Salud Ocupacional"
                    value={customDisciplineInput}
                    onChange={(e) => {
                      setCustomDisciplineInput(e.target.value);
                      if (customDisciplineError) setCustomDisciplineError(null);
                    }}
                    style={{
                      width: '100%',
                      background: 'var(--bg-sidebar)',
                      color: 'var(--text-main)',
                      border: customDisciplineError ? '1px solid #ef4444' : '1px solid var(--border-subtle)',
                      padding: '8px',
                      borderRadius: '6px',
                      fontSize: '13px',
                      marginBottom: customDisciplineError ? '6px' : '10px'
                    }}
                  />
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                    <button type="button" className="btn btn-secondary" onClick={handleCancelCustomDiscipline} style={{ padding: '5px 12px', fontSize: '12px' }}>
                      Cancelar
                    </button>
                    <button type="button" className="btn btn-primary" onClick={handleConfirmCustomDiscipline} style={{ padding: '5px 14px', fontSize: '12px' }}>
                      Aceptar
                    </button>
                  </div>
                </div>
              )}

              {/* Descripción */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Descripción / Notas</label>
                <textarea
                  rows={2}
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Observaciones técnicas o contexto..."
                  style={{ width: '100%', background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', padding: '8px', borderRadius: '6px', fontSize: '13px' }}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
                <button type="button" className="btn btn-secondary" onClick={() => setShowModal(false)}>
                  Cancelar
                </button>
                <button type="submit" className="btn btn-primary" disabled={creating}>
                  {creating ? 'Guardando en Almacenamiento...' : 'Guardar y Registrar Fuente'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* MODAL: ELIMINAR FUENTE (HIGIENE Y CONSISTENCIA) */}
      {/* ========================================================= */}
      {sourceToDelete && (
        <DeleteSourceModal
          source={sourceToDelete}
          onClose={() => setSourceToDelete(null)}
          onSuccess={(msg) => {
            showToast(msg);
            loadSources();
          }}
        />
      )}

      {/* Modal: Procesar con IA (Flujo de Dos Opciones: Documento vs Búsquedas en Internet) */}
      <ProcessWithAiModal
        isOpen={showAiModal}
        initialTitle={aiTitle}
        initialDocType={aiDocType}
        initialDiscipline={aiDiscipline}
        initialAuthority={aiAuthority}
        initialTextContent={aiTextContent}
        initialSourceAssetId={aiSourceAssetId}
        availableDisciplines={availableDisciplines}
        onClose={() => setShowAiModal(false)}
        onExtractionCreated={(extractionId) => {
          setShowAiModal(false);
          setActiveExtractionId(extractionId);
          setShowReviewModal(true);
        }}
      />

      {/* Modal: Procesar sin IA (Visor continuo asistido) */}
      <DocumentManualViewerModal
        isOpen={showManualModal}
        sourceId={manualSourceId}
        documentTitle={manualTitle}
        documentType={manualDocType}
        discipline={manualDiscipline}
        authority={manualAuthority}
        onClose={() => setShowManualModal(false)}
        onExtractionFinished={(extractionId) => {
          setShowManualModal(false);
          setActiveExtractionId(extractionId);
          setShowReviewModal(true);
        }}
      />

      {/* Modal Reutilizable: Revisión, Edición y Validación de Extracciones */}
      <SourceExtractionReviewModal
        isOpen={showReviewModal}
        extractionId={activeExtractionId}
        onClose={() => setShowReviewModal(false)}
        onCommitted={() => {
          showToast('¡Elementos incorporados exitosamente al Motor de Reglas QA/QC!');
          loadSources();
        }}
      />
    </div>
  );
};
