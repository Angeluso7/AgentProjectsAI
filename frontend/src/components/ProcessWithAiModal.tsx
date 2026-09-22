import React, { useState } from 'react';
import {
  X, Sparkles, Globe, FileText, ArrowRight, ArrowLeft, Search,
  ShieldAlert, BookOpen, Layers, CheckCircle2, AlertCircle,
  HelpCircle, Compass, Lightbulb, ExternalLink, Link2, ShieldCheck,
  CheckSquare, Square, Filter, CheckCircle, Loader2
} from 'lucide-react';
import { apiService } from '../services/api';
import { formatApiError } from '../utils/errorHandler';
import { BASE_DISCIPLINES } from '../pages/SourcesPage';

interface ProcessWithAiModalProps {
  isOpen: boolean;
  projectId?: string;
  initialTitle?: string;
  initialDiscipline?: string;
  initialDocType?: string;
  initialAuthority?: string;
  initialTextContent?: string;
  initialSourceAssetId?: string;
  availableDisciplines?: string[];
  onClose: () => void;
  onExtractionCreated: (extractionId: string) => void;
}

type AiProcessStep =
  | 'select_mode'
  | 'form_document'
  | 'form_manual_url'
  | 'form_manual_url_preview'
  | 'form_web'
  | 'form_web_sources_selection';

const QUICK_RESEARCH_PROMPTS = [
  {
    title: 'Accesibilidad Universal OGUC',
    prompt: 'Investigar criterios de accesibilidad universal, rampas, anchos de puertas y pasillos según OGUC',
    discipline: 'Arquitectura',
  },
  {
    title: 'Vías y Escaleras de Evacuación',
    prompt: 'Requisitos de diseño, anchos mínimos y puertas de escape para escaleras de evacuación',
    discipline: 'Arquitectura',
  },
  {
    title: 'Resistencia al Fuego (Muros Cortafuego)',
    prompt: 'Exigencias de resistencia al fuego F-60 / F-120 para muros cortafuego y elementos estructurales',
    discipline: 'Estructuras',
  },
  {
    title: 'Instalaciones Sanitarias (RIDAA)',
    prompt: 'Criterios de dimensionamiento de redes de agua potable, alcantarillado y ventilaciones según RIDAA',
    discipline: 'Mecánica',
  },
  {
    title: 'Cálculo Sísmico NCh433',
    prompt: 'Parámetros de diseño sísmico de edificios, factores de modificación de respuesta y derivas según NCh433',
    discipline: 'Estructuras',
  },
  {
    title: 'Instalaciones Eléctricas RIC / SEC',
    prompt: 'Pliegos técnicos normativos RIC para tableros eléctricos, canalizaciones y protecciones diferenciales SEC',
    discipline: 'Eléctrica',
  },
];

export const ProcessWithAiModal: React.FC<ProcessWithAiModalProps> = ({
  isOpen,
  projectId,
  initialTitle = 'Ordenanza General de Urbanismo y Construcciones (OGUC)',
  initialDiscipline = 'Arquitectura',
  initialDocType = 'norma',
  initialAuthority = 'MINVU',
  initialTextContent = '',
  initialSourceAssetId,
  availableDisciplines = BASE_DISCIPLINES,
  onClose,
  onExtractionCreated,
}) => {
  const [step, setStep] = useState<AiProcessStep>('select_mode');
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Formulario Documento
  const [docTitle, setDocTitle] = useState(initialTitle);
  const [docType, setDocType] = useState(initialDocType);
  const [docDiscipline, setDocDiscipline] = useState(initialDiscipline);
  const [docAuthority, setDocAuthority] = useState(initialAuthority);
  const [docTextContent, setDocTextContent] = useState(initialTextContent);

  // Formulario Ingreso Manual de URL (Flujo Principal Web)
  const [manualUrl, setManualUrl] = useState('https://www.wermac.org/documents/pid_symbols.html');
  const [manualDiscipline, setManualDiscipline] = useState(initialDiscipline);
  const [manualDocType, setManualDocType] = useState('norma');
  const [manualAuthority, setManualAuthority] = useState('');
  const [manualSearchPrompt, setManualSearchPrompt] = useState('Simbología piping ISA S5.1 y diagramas P&ID');
  const [manualInspection, setManualInspection] = useState<any | null>(null);
  const [selectedSublinks, setSelectedSublinks] = useState<Set<string>>(new Set());

  // Formulario Búsqueda en Internet Asistida (Modo Secundario)
  const [webPrompt, setWebPrompt] = useState('Investigar criterios de accesibilidad universal para edificios residenciales');
  const [webDiscipline, setWebDiscipline] = useState(initialDiscipline);
  const [webDocType, setWebDocType] = useState('any_web_doc');
  const [webAuthority, setWebAuthority] = useState('');
  const [webFocusAreas, setWebFocusAreas] = useState<string>('accesibilidad, rampas, anchos_minimos, puertas');
  const [webSources, setWebSources] = useState<any[]>([]);
  const [selectedWebSources, setSelectedWebSources] = useState<Set<string>>(new Set());
  
  // Opciones de Traducción y Límites
  const [translateToSpanish, setTranslateToSpanish] = useState<boolean>(true);
  const [sourceLangPref, setSourceLangPref] = useState<string>('auto');
  const [targetLangPref, setTargetLangPref] = useState<string>('es');
  const [maxRules, setMaxRules] = useState(5);
  const [maxTables, setMaxTables] = useState(3);
  const [maxImages, setMaxImages] = useState(3);
  const [maxSymbols, setMaxSymbols] = useState(3);
  const [maxEquipment, setMaxEquipment] = useState(3);
  const [maxTotal, setMaxTotal] = useState(15);

  if (!isOpen) return null;

  const handleResetAndClose = () => {
    setStep('select_mode');
    setError(null);
    onClose();
  };

  // Submit Opción Documento
  const handleSubmitDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!docTitle.trim()) {
      setError('El título del documento es obligatorio.');
      return;
    }

    setProcessing(true);
    setError(null);
    try {
      const res = await apiService.processDocumentWithAi({
        extraction_mode: 'ai_document',
        title: docTitle.trim(),
        document_type: docType,
        authority: docAuthority.trim() || undefined,
        discipline: docDiscipline,
        source_asset_id: initialSourceAssetId,
        project_id: projectId,
        type_limits: {
          rules: Number(maxRules) || 5,
          tables: Number(maxTables) || 3,
          images: Number(maxImages) || 3,
          symbols: Number(maxSymbols) || 3,
          equipment: Number(maxEquipment) || 3,
        },
        max_total: Number(maxTotal) || 15,
        translation: {
          enabled: true,
          source_language: sourceLangPref,
          target_language: targetLangPref,
          mode: 'during_extraction',
        },
      });
      handleResetAndClose();
      onExtractionCreated(res.id);
    } catch (err: any) {
      console.error(err);
      setError(formatApiError(err));
    } finally {
      setProcessing(false);
    }
  };

  // Submit Opción Manual URL: Paso 1 (Inspección y Validación Profunda)
  const handleInspectManualUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualUrl.trim()) {
      setError('Por favor ingresa una URL válida (ej: https://dominio.com/pagina).');
      return;
    }

    setProcessing(true);
    setError(null);
    try {
      const inspection = await apiService.inspectManualUrl({
        url: manualUrl.trim(),
        discipline: manualDiscipline,
        document_type: manualDocType,
        authority: manualAuthority.trim() || undefined,
        search_prompt: manualSearchPrompt.trim() || undefined,
        max_internal_links: 15,
        project_id: projectId,
      });

      if (inspection.inspection_status === 'invalid') {
        setError(inspection.message || 'La URL ingresada no es válida o no es accesible.');
        return;
      }

      setManualInspection(inspection);
      // Por defecto, pre-seleccionar los subenlaces con alta o media coincidencia
      const defaultSelected = new Set<string>();
      if (inspection.internal_links && inspection.internal_links.length > 0) {
        inspection.internal_links.slice(0, 3).forEach((link: any) => {
          defaultSelected.add(link.url);
        });
      }
      setSelectedSublinks(defaultSelected);
      setStep('form_manual_url_preview');
    } catch (err: any) {
      console.error(err);
      setError(formatApiError(err));
    } finally {
      setProcessing(false);
    }
  };

  // Submit Opción Manual URL: Paso 2 (Extracción de Página Principal + Sublinks)
  const handleSubmitManualExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualInspection || !manualInspection.main_source) {
      setError('No hay información de página principal validada.');
      return;
    }

    setProcessing(true);
    setError(null);
    try {
      const chosenSublinks = (manualInspection.internal_links || []).filter((sub: any) =>
        selectedSublinks.has(sub.url)
      );

      const res = await apiService.processManualUrl({
        main_source: manualInspection.main_source,
        selected_sublinks: chosenSublinks,
        discipline: manualDiscipline,
        document_type: manualDocType,
        authority: manualAuthority.trim() || undefined,
        project_id: projectId,
        search_prompt: manualSearchPrompt.trim() || undefined,
        type_limits: {
          rules: Number(maxRules) || 5,
          tables: Number(maxTables) || 3,
          images: Number(maxImages) || 3,
          symbols: Number(maxSymbols) || 3,
          equipment: Number(maxEquipment) || 3,
        },
        max_total: Number(maxTotal) || 15,
        translate_to_spanish: translateToSpanish,
        translation: {
          enabled: true,
          source_language: sourceLangPref,
          target_language: targetLangPref,
          mode: 'during_extraction',
        },
      });

      handleResetAndClose();
      onExtractionCreated(res.id);
    } catch (err: any) {
      console.error(err);
      setError(formatApiError(err));
    } finally {
      setProcessing(false);
    }
  };

  // Submit Opción Búsqueda en Internet: Paso 1
  const handleSubmitWebResearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!webPrompt.trim()) return;

    setProcessing(true);
    setError(null);
    try {
      const sources = await apiService.searchWebSources({
        search_prompt: webPrompt.trim(),
        discipline: webDiscipline,
        document_type: webDocType,
        authority: webAuthority.trim() || undefined,
        max_results: 10,
      });
      setWebSources(sources);
      setSelectedWebSources(new Set(sources.map((s: any) => s.url)));
      setStep('form_web_sources_selection');
    } catch (err: any) {
      console.error(err);
      setError(formatApiError(err));
    } finally {
      setProcessing(false);
    }
  };

  // Submit Opción Búsqueda en Internet: Paso 2
  const handleSubmitWebExtraction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedWebSources.size === 0) return;

    setProcessing(true);
    setError(null);
    try {
      const focusList = webFocusAreas
        .split(',')
        .map((f) => f.trim())
        .filter((f) => f.length > 0);

      const sourcesToProcess = webSources.filter((s) => selectedWebSources.has(s.url));

      const res = await apiService.processWebResearch({
        search_prompt: webPrompt.trim(),
        selected_sources: sourcesToProcess,
        discipline: webDiscipline,
        document_type: webDocType,
        authority: webAuthority.trim() || undefined,
        focus_areas: focusList.length > 0 ? focusList : undefined,
        type_limits: {
          rules: Number(maxRules) || 5,
          tables: Number(maxTables) || 3,
          images: Number(maxImages) || 3,
          symbols: Number(maxSymbols) || 3,
          equipment: Number(maxEquipment) || 3,
        },
        max_total: Number(maxTotal) || 15,
        translate_to_spanish: translateToSpanish,
        translation: {
          enabled: true,
          source_language: sourceLangPref,
          target_language: targetLangPref,
          mode: 'during_extraction',
        },
      });
      handleResetAndClose();
      onExtractionCreated(res.id);
    } catch (err: any) {
      console.error(err);
      setError(formatApiError(err));
    } finally {
      setProcessing(false);
    }
  };

  const toggleSublink = (url: string) => {
    const next = new Set(selectedSublinks);
    if (next.has(url)) next.delete(url);
    else next.add(url);
    setSelectedSublinks(next);
  };

  const toggleSourceSelection = (url: string) => {
    const nextSet = new Set(selectedWebSources);
    if (nextSet.has(url)) nextSet.delete(url);
    else nextSet.add(url);
    setSelectedWebSources(nextSet);
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-4xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100">
                  Procesar Fuentes & Incorporar Conocimiento con IA
                </h2>
                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-teal-950 text-teal-300 border border-teal-800">
                  Asistido por IA
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {step === 'select_mode' && 'Paso 1: Selecciona el método de incorporación y procedencia de la información'}
                {step === 'form_manual_url' && 'Paso 2: Ingresa y valida la URL específica para inspección profunda'}
                {step === 'form_manual_url_preview' && 'Paso 3: Revisa la página principal y selecciona subenlaces internos para extracción'}
                {step === 'form_document' && 'Paso 2: Configura el análisis y extracción estructurada desde el documento cargado'}
                {step === 'form_web' && 'Paso 2: Define el tema de investigación técnica y búsqueda en Internet'}
                {step === 'form_web_sources_selection' && 'Paso 3: Selecciona y valida las fuentes web antes de extraer'}
              </p>
            </div>
          </div>
          <button
            onClick={handleResetAndClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Cuerpo del Modal */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/50 border border-rose-800/80 text-rose-300 text-xs flex items-center gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 text-rose-400" />
              <span>{error}</span>
            </div>
          )}

          {/* ========================================================= */}
          {/* PASO 1: SELECCIÓN DE ESTRATEGIA (3 MODOS) */}
          {/* ========================================================= */}
          {step === 'select_mode' && (
            <div className="space-y-4">
              <div className="text-center max-w-xl mx-auto mb-6">
                <h3 className="text-sm font-semibold text-slate-200">
                  ¿Cómo deseas incorporar el conocimiento técnico?
                </h3>
                <p className="text-xs text-slate-400 mt-1">
                  Selecciona el método más adecuado. La herramienta extraerá candidatos estructurados para tu validación humana en el panel unificado.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* TARJETA 1: INGRESO MANUAL DE URL (FLUJO PRINCIPAL WEB) */}
                <button
                  type="button"
                  onClick={() => setStep('form_manual_url')}
                  className="flex flex-col text-left p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-sky-950/40 border-2 border-sky-600/50 hover:border-sky-400 hover:shadow-lg hover:shadow-sky-950/50 transition-all group relative overflow-hidden"
                >
                  <div className="absolute top-2 right-2">
                    <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-sky-900/80 text-sky-200 border border-sky-500">
                      ⭐ Recomendado
                    </span>
                  </div>

                  <div className="flex items-center justify-between w-full mb-3">
                    <div className="p-2.5 rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/30 group-hover:scale-110 transition-transform">
                      <Link2 className="w-6 h-6" />
                    </div>
                  </div>

                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-sky-300 transition-colors flex items-center gap-1.5">
                    Ingresar URL Manualmente
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-sky-400" />
                  </h4>

                  <p className="text-xs text-slate-400 mt-2 leading-relaxed flex-1">
                    Inspección profunda, validación de acceso en vivo, descubrimiento de enlaces internos reales del mismo dominio y extracción estructurada sin adivinaciones.
                  </p>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <ShieldCheck className="w-3.5 h-3.5 text-sky-400" /> Flujo Web Confiable
                    </span>
                    <span className="text-sky-400 font-semibold group-hover:underline">Comenzar →</span>
                  </div>
                </button>

                {/* TARJETA 2: EN BASE AL DOCUMENTO CARGADO */}
                <button
                  type="button"
                  onClick={() => setStep('form_document')}
                  className="flex flex-col text-left p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-teal-950/30 border-2 border-slate-800 hover:border-teal-500/70 hover:shadow-lg hover:shadow-teal-950/40 transition-all group"
                >
                  <div className="flex items-center justify-between w-full mb-3">
                    <div className="p-2.5 rounded-xl bg-teal-500/10 text-teal-400 border border-teal-500/20 group-hover:scale-110 transition-transform">
                      <FileText className="w-6 h-6" />
                    </div>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-teal-900/60 text-teal-300 border border-teal-700">
                      Documento Local
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-teal-300 transition-colors flex items-center gap-1.5">
                    Documento Cargado
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-teal-400" />
                  </h4>

                  <p className="text-xs text-slate-400 mt-2 leading-relaxed flex-1">
                    Analiza un archivo cargado (PDF, CAD, plano, imagen o texto). OCR semántico, desglose de capítulos, tablas, figuras y reglas oficiales.
                  </p>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5 text-teal-400" /> Archivo Interno
                    </span>
                    <span className="text-slate-300 font-medium group-hover:underline">Configurar →</span>
                  </div>
                </button>

                {/* TARJETA 3: BÚSQUEDA EN INTERNET ASISTIDA (MODO SECUNDARIO) */}
                <button
                  type="button"
                  onClick={() => setStep('form_web')}
                  className="flex flex-col text-left p-5 rounded-2xl bg-gradient-to-br from-slate-900 via-slate-900 to-indigo-950/30 border-2 border-slate-800 hover:border-indigo-500/70 hover:shadow-lg hover:shadow-indigo-950/40 transition-all group"
                >
                  <div className="flex items-center justify-between w-full mb-3">
                    <div className="p-2.5 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 group-hover:scale-110 transition-transform">
                      <Globe className="w-6 h-6" />
                    </div>
                    <span className="text-[9px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-full bg-indigo-900/60 text-indigo-300 border border-indigo-700">
                      Asistido / Opcional
                    </span>
                  </div>

                  <h4 className="text-sm font-bold text-slate-100 group-hover:text-indigo-300 transition-colors flex items-center gap-1.5">
                    Búsqueda Asistida
                    <ArrowRight className="w-4 h-4 opacity-0 group-hover:opacity-100 -translate-x-1 group-hover:translate-x-0 transition-all text-indigo-400" />
                  </h4>

                  <p className="text-xs text-slate-400 mt-2 leading-relaxed flex-1">
                    Investiga externamente un tema o norma mediante un prompt temático. Descubre fuentes con coincidencia de términos y validación HTTP profunda.
                  </p>

                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                    <span className="flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-400" /> Modo Secundario
                    </span>
                    <span className="text-slate-300 font-medium group-hover:underline">Buscar →</span>
                  </div>
                </button>
              </div>

              {/* PANEL DE PREFERENCIA DE IDIOMA Y TRADUCCIÓN */}
              <div className="mt-6 p-4 rounded-2xl bg-slate-900/90 border border-slate-800 shadow-sm space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Globe className="w-4 h-4 text-sky-400" />
                    <div>
                      <h4 className="text-xs font-bold text-slate-200">Política de Traducción e Idioma</h4>
                      <p className="text-[11px] text-slate-400">
                        Configura la política de idioma para el procesamiento.
                      </p>
                    </div>
                  </div>

                  {/* Selectores de Idioma */}
                  <div className="flex items-center gap-2">
                    <select
                      value={sourceLangPref}
                      onChange={(e) => setSourceLangPref(e.target.value)}
                      className="text-xs bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-sky-500"
                    >
                      <option value="auto">Detectar automáticamente</option>
                      <option value="en">Inglés (EN)</option>
                      <option value="es">Español (ES)</option>
                      <option value="pt">Portugués (PT)</option>
                      <option value="de">Alemán (DE)</option>
                      <option value="fr">Francés (FR)</option>
                    </select>

                    <span className="text-slate-500 font-bold">⇄</span>

                    <select
                      value={targetLangPref}
                      onChange={(e) => {
                        setTargetLangPref(e.target.value);
                        setTranslateToSpanish(e.target.value === 'es');
                      }}
                      className="text-xs bg-slate-800 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-sky-500"
                    >
                      <option value="es">Traducir a: Español</option>
                      <option value="en">Traducir a: Inglés</option>
                      <option value="pt">Traducir a: Portugués</option>
                    </select>
                  </div>
                </div>

                <div className="pt-2 border-t border-slate-800/60 flex items-center justify-between">
                  <span className="text-[11px] text-slate-400 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                    La detección de idioma y la traducción se ejecutarán durante la extracción. El texto original se conservará como referencia.
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* ========================================================= */}
          {/* PASO 2: INGRESO MANUAL DE URL (FORMULARIO) */}
          {/* ========================================================= */}
          {step === 'form_manual_url' && (
            <form id="ai-manual-url-form" onSubmit={handleInspectManualUrl} className="space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('select_mode')}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a selección de método
                </button>
                <span className="text-[11px] text-sky-400 font-semibold bg-sky-950/70 border border-sky-800/60 px-2.5 py-0.5 rounded-full flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5" /> Validación Anti-SSRF y Anti-Soft404 Activa
                </span>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    URL de la Página o Documento Web Técnico <span className="text-rose-400">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type="url"
                      required
                      value={manualUrl}
                      onChange={(e) => setManualUrl(e.target.value)}
                      placeholder="https://www.ejemplo.org/normas/simbologia-piping-isa51.html"
                      className="w-full pl-9 pr-4 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500 focus:border-transparent transition-all font-mono"
                    />
                    <Link2 className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Solo se permiten protocolos HTTP/HTTPS públicos. Se bloquean IPs internas, loopback y páginas con errores visibles.
                  </p>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Disciplina Técnica Asociada
                    </label>
                    <select
                      value={manualDiscipline}
                      onChange={(e) => setManualDiscipline(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    >
                      {availableDisciplines.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Tipo Documental Estimado
                    </label>
                    <select
                      value={manualDocType}
                      onChange={(e) => setManualDocType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    >
                      <option value="norma">Norma Técnica Oficial</option>
                      <option value="manual">Manual de Buenas Prácticas / Diseño</option>
                      <option value="estandar">Estándar Técnico Internacional (ISA / NFPA / ASME)</option>
                      <option value="ley">Ley o Decreto Regulador</option>
                      <option value="any_web_doc">Documento Técnico Abierto</option>
                    </select>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Autoridad u Organismo Emisor (Opcional)
                    </label>
                    <input
                      type="text"
                      value={manualAuthority}
                      onChange={(e) => setManualAuthority(e.target.value)}
                      placeholder="Ej: ISA / MINVU / SEC / ASTM"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Foco Temático / Términos de Cobertura (Opcional)
                    </label>
                    <input
                      type="text"
                      value={manualSearchPrompt}
                      onChange={(e) => setManualSearchPrompt(e.target.value)}
                      placeholder="Ej: Simbología piping ISA S5.1 y válvulas"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-500"
                    />
                  </div>
                </div>
              </div>
            </form>
          )}

          {/* ========================================================= */}
          {/* PASO 3: VISTA PREVIA DE URL MANUAL Y SELECCIÓN DE SUBLINKS */}
          {/* ========================================================= */}
          {step === 'form_manual_url_preview' && manualInspection && (
            <form id="ai-manual-extraction-form" onSubmit={handleSubmitManualExtraction} className="space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('form_manual_url')}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a editar URL
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] font-semibold px-2.5 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-700 flex items-center gap-1">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400" /> Página Principal Validada
                  </span>
                </div>
              </div>

              {/* TARJETA DE LA PÁGINA PRINCIPAL */}
              {manualInspection.main_source && (
                <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-700/80 shadow-md space-y-2.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800">
                          {manualInspection.main_source.domain}
                        </span>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded ${
                          manualInspection.main_source.detected_language === 'es'
                            ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                            : 'bg-blue-950 text-blue-300 border border-blue-800'
                        }`}>
                          {manualInspection.main_source.detected_language?.toUpperCase()}
                        </span>
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                          🎯 {manualInspection.main_source.match_bucket}
                        </span>
                      </div>

                      <h4 className="text-sm font-bold text-slate-100">
                        {manualInspection.main_source.title}
                      </h4>
                    </div>

                    <a
                      href={manualInspection.main_source.validated_content_url || manualInspection.main_source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="p-1.5 text-slate-400 hover:text-sky-300 hover:bg-slate-800 rounded-lg transition-colors shrink-0"
                      title="Abrir URL validada en nueva pestaña"
                    >
                      <ExternalLink className="w-4 h-4" />
                    </a>
                  </div>

                  <p className="text-xs text-slate-300 bg-slate-900/70 p-2.5 rounded-lg border border-slate-800/80 leading-relaxed font-mono">
                    {manualInspection.main_source.snippet}
                  </p>

                  <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                    <span className="truncate max-w-md text-slate-500 font-mono">
                      URL: {manualInspection.main_source.resolved_url}
                    </span>
                    <span className="text-emerald-400 font-semibold flex items-center gap-1">
                      <CheckCircle2 className="w-3.5 h-3.5" /> {manualInspection.main_source.subpage_selection_reason || 'Contenido validado'}
                    </span>
                  </div>
                </div>
              )}

              {/* SECCIÓN DE SUBLINKS INTERNOS DESCUBIERTOS */}
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                    <Layers className="w-4 h-4 text-sky-400" />
                    Subenlaces Internos Relevantes del Mismo Dominio ({manualInspection.internal_links?.length || 0})
                  </h4>
                  <div className="flex items-center gap-2 text-[11px]">
                    <button
                      type="button"
                      onClick={() => {
                        const allUrls = (manualInspection.internal_links || []).map((l: any) => l.url);
                        setSelectedSublinks(new Set(allUrls));
                      }}
                      className="text-sky-400 hover:underline"
                    >
                      Seleccionar Todos
                    </button>
                    <span className="text-slate-600">|</span>
                    <button
                      type="button"
                      onClick={() => setSelectedSublinks(new Set())}
                      className="text-slate-400 hover:underline"
                    >
                      Deseleccionar
                    </button>
                  </div>
                </div>

                {(!manualInspection.internal_links || manualInspection.internal_links.length === 0) ? (
                  <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800 text-center text-xs text-slate-400">
                    No se detectaron subenlaces internos adicionales en esta página. Se extraerá la información únicamente desde la URL principal validada.
                  </div>
                ) : (
                  <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
                    {manualInspection.internal_links.map((sub: any) => {
                      const isSelected = selectedSublinks.has(sub.url);
                      return (
                        <div
                          key={sub.url}
                          onClick={() => toggleSublink(sub.url)}
                          className={`p-3 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                            isSelected
                              ? 'bg-sky-950/30 border-sky-500/70 shadow-sm shadow-sky-950/30'
                              : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                          }`}
                        >
                          <button
                            type="button"
                            className="mt-0.5 text-sky-400 shrink-0"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleSublink(sub.url);
                            }}
                          >
                            {isSelected ? (
                              <CheckSquare className="w-4 h-4 text-sky-400" />
                            ) : (
                              <Square className="w-4 h-4 text-slate-500" />
                            )}
                          </button>

                          <div className="flex-1 min-w-0">
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-xs font-bold text-slate-200 truncate">
                                {sub.title}
                              </span>
                              <span className="text-[9px] font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-300 shrink-0">
                                {sub.match_bucket || 'MEDIUM_MATCH'}
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400 truncate font-mono mt-0.5">
                              {sub.url}
                            </p>
                          </div>

                          <a
                            href={sub.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 text-slate-500 hover:text-sky-300 transition-colors"
                          >
                            <ExternalLink className="w-3.5 h-3.5" />
                          </a>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* OPCIONES DE TRADUCCIÓN Y LÍMITES */}
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 flex items-center justify-between flex-wrap gap-3">
                <label className="flex items-center gap-2 cursor-pointer text-xs text-slate-200">
                  <input
                    type="checkbox"
                    checked={translateToSpanish}
                    onChange={(e) => setTranslateToSpanish(e.target.checked)}
                    className="w-4 h-4 text-sky-600 rounded bg-slate-900 border-slate-700 focus:ring-sky-500"
                  />
                  <span>Traducir al español preservando textos originales para trazabilidad</span>
                </label>

                <div className="flex items-center gap-2 text-[11px] text-slate-400">
                  <span>Límite máximo de ítems:</span>
                  <select
                    value={maxTotal}
                    onChange={(e) => setMaxTotal(Number(e.target.value))}
                    className="px-2 py-1 bg-slate-900 border border-slate-700 rounded text-slate-200 text-xs"
                  >
                    <option value={10}>10 ítems</option>
                    <option value={15}>15 ítems</option>
                    <option value={20}>20 ítems</option>
                    <option value={30}>30 ítems</option>
                  </select>
                </div>
              </div>
            </form>
          )}

          {/* ========================================================= */}
          {/* PASO 2: FORMULARIO DOCUMENTO CARGADO */}
          {/* ========================================================= */}
          {step === 'form_document' && (
            <form id="ai-document-form" onSubmit={handleSubmitDocument} className="space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('select_mode')}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a selección de método
                </button>
                <span className="text-[11px] text-slate-400">Extracción Local con OCR Semántico</span>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Título de la Norma o Documento <span className="text-rose-400">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    value={docTitle}
                    onChange={(e) => setDocTitle(e.target.value)}
                    placeholder="Ej: Ordenanza General de Urbanismo y Construcciones (OGUC)"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Disciplina
                    </label>
                    <select
                      value={docDiscipline}
                      onChange={(e) => setDocDiscipline(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      {availableDisciplines.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Tipo de Documento
                    </label>
                    <select
                      value={docType}
                      onChange={(e) => setDocType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-teal-500"
                    >
                      <option value="norma">Norma Técnica Oficial</option>
                      <option value="ley">Ley o Decreto Supremo</option>
                      <option value="manual">Manual de Diseño / Guía</option>
                      <option value="especificacion">Especificación Técnica</option>
                      <option value="criterio_experto">Criterio Experto</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Autoridad u Organismo Emisor
                  </label>
                  <input
                    type="text"
                    value={docAuthority}
                    onChange={(e) => setDocAuthority(e.target.value)}
                    placeholder="Ej: MINVU, SEC, INN, MOP, etc."
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500"
                  />
                </div>
              </div>
            </form>
          )}

          {/* ========================================================= */}
          {/* PASO 2: FORMULARIO BÚSQUEDA EN INTERNET ASISTIDA */}
          {/* ========================================================= */}
          {step === 'form_web' && (
            <form id="ai-web-form" onSubmit={handleSubmitWebResearch} className="space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('select_mode')}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver a selección de método
                </button>
                <span className="text-[11px] text-indigo-400 font-semibold">Búsqueda Asistida Multiconsulta</span>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Prompt o Tema Técnico a Investigar en Internet <span className="text-rose-400">*</span>
                  </label>
                  <div className="relative">
                    <input
                      type="text"
                      required
                      value={webPrompt}
                      onChange={(e) => setWebPrompt(e.target.value)}
                      placeholder="Ej: Requisitos de resistencia al fuego F-120 para muros cortafuego"
                      className="w-full pl-9 pr-4 py-2.5 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
                    />
                    <Search className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Disciplina Asociada
                    </label>
                    <select
                      value={webDiscipline}
                      onChange={(e) => setWebDiscipline(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      {availableDisciplines.map((d) => (
                        <option key={d} value={d}>{d}</option>
                      ))}
                    </select>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-300 mb-1">
                      Alcance del Documento Web
                    </label>
                    <select
                      value={webDocType}
                      onChange={(e) => setWebDocType(e.target.value)}
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="any_web_doc">Cualquier documento técnico web</option>
                      <option value="norma">Norma Técnica Oficial</option>
                      <option value="ley">Ley / Decreto</option>
                      <option value="manual">Manual de Diseño</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1">
                    Autoridad o Fuente de Referencia Preferente (Opcional)
                  </label>
                  <input
                    type="text"
                    value={webAuthority}
                    onChange={(e) => setWebAuthority(e.target.value)}
                    placeholder="Ej: MINVU, SEC, NFPA, ASME, INN"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>
              </div>
            </form>
          )}

          {/* ========================================================= */}
          {/* PASO 3: SELECCIÓN DE FUENTES WEB (MODO ASISTIDO) */}
          {/* ========================================================= */}
          {step === 'form_web_sources_selection' && (
            <form id="ai-web-extraction-form" onSubmit={handleSubmitWebExtraction} className="space-y-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setStep('form_web')}
                  className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" /> Volver al prompt
                </button>
                <div className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400">
                    {selectedWebSources.size} de {webSources.length} fuentes seleccionadas
                  </span>
                </div>
              </div>

              <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
                {webSources.map((source) => {
                  const isSelected = selectedWebSources.has(source.url);
                  return (
                    <div
                      key={source.url}
                      onClick={() => toggleSourceSelection(source.url)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-start gap-3 ${
                        isSelected
                          ? 'bg-indigo-950/30 border-indigo-500/70 shadow-sm shadow-indigo-950/40'
                          : 'bg-slate-950/40 border-slate-800 hover:border-slate-700'
                      }`}
                    >
                      <button
                        type="button"
                        className="mt-0.5 text-indigo-400 shrink-0"
                        onClick={(e) => {
                          e.stopPropagation();
                          toggleSourceSelection(source.url);
                        }}
                      >
                        {isSelected ? (
                          <CheckSquare className="w-4 h-4 text-indigo-400" />
                        ) : (
                          <Square className="w-4 h-4 text-slate-500" />
                        )}
                      </button>

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center justify-between gap-2 flex-wrap">
                          <span className="text-xs font-bold text-slate-100 truncate">
                            {source.title}
                          </span>
                          <div className="flex items-center gap-1.5">
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                              {source.match_bucket || 'MATCH'}
                            </span>
                            <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                              {source.detected_language?.toUpperCase() || 'ES'}
                            </span>
                          </div>
                        </div>

                        <p className="text-[11px] text-slate-300 line-clamp-2 mt-1">
                          {source.snippet}
                        </p>

                        <div className="flex items-center justify-between text-[10px] text-slate-400 mt-2 font-mono">
                          <span className="truncate max-w-sm text-slate-500">{source.domain}</span>
                          <a
                            href={source.validated_content_url || source.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            onClick={(e) => e.stopPropagation()}
                            className="text-sky-400 hover:underline flex items-center gap-1"
                          >
                            Ver página activa <ExternalLink className="w-3 h-3" />
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </form>
          )}
        </div>

        {/* Pie del Modal */}
        <div className="px-6 py-4 border-t border-slate-800 flex items-center justify-between bg-slate-950/80">
          <button
            type="button"
            onClick={handleResetAndClose}
            disabled={processing}
            className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl transition-colors disabled:opacity-50"
          >
            Cancelar
          </button>

          {step === 'select_mode' && (
            <span className="text-xs text-slate-400">
              Selecciona una tarjeta para continuar
            </span>
          )}

          {step === 'form_manual_url' && (
            <button
              type="submit"
              form="ai-manual-url-form"
              disabled={processing || !manualUrl.trim()}
              className="px-5 py-2 bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-sky-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <div className="w-4 h-4 border-2 border-slate-950/30 border-t-slate-950 rounded-full animate-spin" />
                  <span>Inspeccionando y Validando URL...</span>
                </>
              ) : (
                <>
                  <Link2 className="w-4 h-4 text-slate-950" />
                  <span>Inspeccionar y Validar URL</span>
                </>
              )}
            </button>
          )}

          {step === 'form_manual_url_preview' && (
            <button
              type="submit"
              form="ai-manual-extraction-form"
              disabled={processing || !manualInspection?.main_source}
              className="px-5 py-2 bg-gradient-to-r from-sky-500 to-emerald-600 hover:from-sky-400 hover:to-emerald-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-sky-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <Sparkles className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Extrayendo Datos Estructurados...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950" />
                  <span>
                    Extraer Información (Página Principal
                    {selectedSublinks.size > 0 ? ` + ${selectedSublinks.size} subenlaces` : ''})
                  </span>
                </>
              )}
            </button>
          )}

          {step === 'form_document' && (
            <button
              type="submit"
              form="ai-document-form"
              disabled={processing || !docTitle.trim()}
              className="px-5 py-2 bg-gradient-to-r from-teal-500 to-emerald-600 hover:from-teal-400 hover:to-emerald-500 text-slate-950 font-bold text-xs rounded-xl shadow-lg shadow-teal-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <Sparkles className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Procesando Documento...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-slate-950" />
                  <span>Iniciar Procesamiento de Documento</span>
                </>
              )}
            </button>
          )}

          {step === 'form_web' && (
            <button
              type="submit"
              form="ai-web-form"
              disabled={processing || !webPrompt.trim()}
              className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Buscando Fuentes...
                </>
              ) : (
                <>
                  <Search className="w-4 h-4" /> Buscar Fuentes Web
                </>
              )}
            </button>
          )}

          {step === 'form_web_sources_selection' && (
            <button
              type="submit"
              form="ai-web-extraction-form"
              disabled={processing || selectedWebSources.size === 0}
              className="px-5 py-2 bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold text-xs rounded-xl shadow-lg shadow-indigo-950/50 transition-all flex items-center gap-2 disabled:opacity-50"
            >
              {processing ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Extrayendo Datos...
                </>
              ) : (
                <>
                  <Globe className="w-4 h-4" /> Extraer de Fuentes ({selectedWebSources.size})
                </>
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
