import React, { useState, useEffect, useRef } from 'react';
import {
  Eye, Layers, ZoomIn, ZoomOut, RotateCcw, CheckCircle, AlertTriangle,
  Crosshair, Tag, Type, Play, LayoutGrid, CheckCircle2, XCircle,
  Table as TableIcon, Shapes, Sparkles, Filter, ShieldAlert, SquareCheck, AlertOctagon,
  FileText, Folder, Upload, Hand, MousePointer, Crop, Maximize2,
  BookmarkPlus, Database, Trash2, Edit3, Check, Info, ArrowUpRight,
  ScanText, X
} from 'lucide-react';
import { apiService } from '../services/api';
import {
  Project, DocumentItem, DocumentSheet, ExtractedTextItem, SheetRegionItem,
  TitleBlockExtractionItem, ExtractedTableItem, ExtractedTableCellItem,
  DetectedSymbolItem, SheetSymbolsSummaryResponse, RuleFindingItem,
  ManualAnnotation
} from '../types';
import { AnnotationClassifyModal } from '../components/AnnotationClassifyModal';
import { AnnotationConfirmModal } from '../components/AnnotationConfirmModal';
import { PlanSelectionsModal } from '../components/PlanSelectionsModal';

export type ViewerToolMode = 'select' | 'pan' | 'crop';

// =========================================================
// CURSORES PERSONALIZADOS SVG (MANO NEGRA Y CRUZ ROJA)
// =========================================================
const BLACK_GRAB_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='%23000000' stroke='%23ffffff' stroke-width='1.2'><path d='M18 11V6a2 2 0 0 0-4 0v4a2 2 0 0 0-4 0v-1a2 2 0 0 0-4 0v6c0 4.4 3.6 8 8 8s8-3.6 8-8v-4a2 2 0 0 0-4 0z'/></svg>") 12 12, grab`;
const BLACK_GRABBING_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='%23000000' stroke='%23ffffff' stroke-width='1.2'><path d='M18 11V9a2 2 0 0 0-4 0v1a2 2 0 0 0-4 0v-1a2 2 0 0 0-4 0v2c0 4.4 3.6 8 8 8s8-3.6 8-8v-1a2 2 0 0 0-4 0z'/></svg>") 12 12, grabbing`;
const RED_CROSSHAIR_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23ef4444' stroke-width='2'><line x1='12' y1='2' x2='12' y2='22'/><line x1='2' y1='12' x2='22' y2='12'/><circle cx='12' cy='12' r='3.5' stroke='%23ef4444' stroke-width='1.5'/></svg>") 12 12, crosshair`;

// =========================================================
// PALETA CROMÁTICA OFICIAL POR TIPO DE ELEMENTO
// =========================================================
export const TAXONOMY_COLORS: Record<string, { color: string; label: string }> = {
  symbol: { color: '#06b6d4', label: 'Símbolo' },
  table: { color: '#10b981', label: 'Tabla / Cuadro' },
  layout_region: { color: '#0284c7', label: 'Región / Formato' },
  text_note: { color: '#f59e0b', label: 'Texto / Nota' },
  title_block: { color: '#6366f1', label: 'Viñeta / Title Block' },
  legend: { color: '#a855f7', label: 'Leyenda' },
  view_elevation_plan: { color: '#f97316', label: 'Vista / Planta' },
  stamp_signature: { color: '#ef4444', label: 'Sello / Timbre' },
  diagram_sketch: { color: '#ec4899', label: 'Croquis / Esquema' },
  other: { color: '#94a3b8', label: 'Otro' },
};

export const getAnnotationColor = (type: string): string => {
  return TAXONOMY_COLORS[type]?.color || '#94a3b8';
};

export const PlanViewerPage: React.FC = () => {
  const [showOcr, setShowOcr] = useState(false);
  const [showRegions, setShowRegions] = useState(true);
  const [showTables, setShowTables] = useState(true);
  const [showSymbols, setShowSymbols] = useState(true);
  const [showFindings, setShowFindings] = useState(true);
  const [showManualAnnotations, setShowManualAnnotations] = useState(true);
  
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>('');
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [availableSheets, setAvailableSheets] = useState<DocumentSheet[]>([]);
  const [selectedSheet, setSelectedSheet] = useState<DocumentSheet | null>(null);
  
  const [ocrTexts, setOcrTexts] = useState<ExtractedTextItem[]>([]);
  const [regions, setRegions] = useState<SheetRegionItem[]>([]);
  const [titleBlock, setTitleBlock] = useState<TitleBlockExtractionItem | null>(null);
  const [tables, setTables] = useState<ExtractedTableItem[]>([]);
  const [selectedTable, setSelectedTable] = useState<ExtractedTableItem | null>(null);
  const [tableCells, setTableCells] = useState<ExtractedTableCellItem[]>([]);
  const [symbols, setSymbols] = useState<DetectedSymbolItem[]>([]);
  const [symbolsSummary, setSymbolsSummary] = useState<SheetSymbolsSummaryResponse | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState<DetectedSymbolItem | null>(null);
  const [findings, setFindings] = useState<RuleFindingItem[]>([]);
  const [selectedFinding, setSelectedFinding] = useState<RuleFindingItem | null>(null);
  const [manualAnnotations, setManualAnnotations] = useState<ManualAnnotation[]>([]);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [disciplineFilter, setDisciplineFilter] = useState<string>('all');
  
  // Herramientas de Interacción: Pan, Zoom, Selección
  const [activeTool, setActiveTool] = useState<ViewerToolMode>('select');
  const [zoom, setZoom] = useState<number>(1);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState<boolean>(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Selección Rectangular Manual y Recorte
  const [isDrawingCrop, setIsDrawingCrop] = useState<boolean>(false);
  const [cropStart, setCropStart] = useState<{ x: number; y: number } | null>(null);
  const [currentCrop, setCurrentCrop] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [extractedCropBase64, setExtractedCropBase64] = useState<string | null>(null);
  const [cropBboxNormalized, setCropBboxNormalized] = useState<[number, number, number, number]>([0, 0, 0, 0]);
  const [showClassifyModal, setShowClassifyModal] = useState<boolean>(false);
  const [editingAnnotation, setEditingAnnotation] = useState<ManualAnnotation | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [pendingAnnotations, setPendingAnnotations] = useState<any[]>([]);

  // Modal de Gestión de Selecciones del Proyecto
  const [showSelectionsModal, setShowSelectionsModal] = useState<boolean>(false);
  // Estado para Reselección (Redefinir Bounding Box preservando identidad)
  const [reselectingAnnotationId, setReselectingAnnotationId] = useState<string | null>(null);

  // Estado para Captura OCR de Texto desde el Plano General (para el campo Nombre o Descripción)
  const [isCapturingPlanTextForName, setIsCapturingPlanTextForName] = useState<boolean>(false);
  const [capturedPlanTextForName, setCapturedPlanTextForName] = useState<{ text: string; timestamp: number } | null>(null);

  // Menú Contextual Flotante (Click sobre Selección)
  const [selectionMenu, setSelectionMenu] = useState<{
    x: number;
    y: number;
    annotation: ManualAnnotation;
  } | null>(null);

  // Menú Contextual Flotante (Click Derecho sobre Anotación)
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    annotation: ManualAnnotation;
  } | null>(null);

  // Notificaciones flotantes en esquina superior derecha
  const [viewerToast, setViewerToast] = useState<{ message: string; type: 'info' | 'success' | 'warning' | 'error' } | null>(null);
  
  const viewportRef = useRef<HTMLDivElement>(null);
  const sheetContainerRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  useEffect(() => {
    loadInitialProjects();
  }, []);

  // Cierra los menús contextuales al hacer clic en cualquier parte de la ventana
  useEffect(() => {
    const handleGlobalClick = () => {
      setContextMenu(null);
      setSelectionMenu(null);
    };
    window.addEventListener('click', handleGlobalClick);
    return () => window.removeEventListener('click', handleGlobalClick);
  }, []);

  const showToast = (message: string, type: 'info' | 'success' | 'warning' | 'error' = 'info', duration = 3000) => {
    setViewerToast({ message, type });
    if (duration > 0) {
      setTimeout(() => {
        setViewerToast((prev) => (prev?.message === message ? null : prev));
      }, duration);
    }
  };

  const loadInitialProjects = async () => {
    try {
      const projList = await apiService.getProjects();
      setProjects(projList);

      if (projList.length > 0) {
        const storedProjectId = localStorage.getItem('active_project_id');
        const targetProj = projList.find((p) => p.id === storedProjectId) || projList[0];
        setSelectedProjectId(targetProj.id);
        localStorage.setItem('active_project_id', targetProj.id);
        await loadProjectDocuments(targetProj.id);
      } else {
        setSelectedProjectId('');
        setDocuments([]);
        setSelectedSheet(null);
        resetSheetLayers();
      }
    } catch (e) {
      console.error('Error cargando proyectos en visor:', e);
    }
  };

  const handleProjectChange = async (projectId: string) => {
    setSelectedProjectId(projectId);
    localStorage.setItem('active_project_id', projectId);
    localStorage.removeItem('viewer_target_doc_id');
    localStorage.removeItem('viewer_target_sheet_id');
    window.dispatchEvent(new CustomEvent('active-project-changed', {
      detail: { projectId }
    }));
    await loadProjectDocuments(projectId);
  };

  const loadProjectDocuments = async (projectId: string) => {
    try {
      const docs = await apiService.getDocuments(projectId);
      setDocuments(docs);

      if (docs.length > 0) {
        const targetDocId = localStorage.getItem('viewer_target_doc_id');
        const activeDoc = docs.find((d) => d.id === targetDocId) || docs[0];
        setSelectedDocId(activeDoc.id);

        let sheets = activeDoc.sheets || [];
        if (sheets.length === 0) {
          try {
            sheets = await apiService.getDocumentSheets(activeDoc.id);
          } catch {
            sheets = [];
          }
        }
        setAvailableSheets(sheets);

        if (sheets.length > 0) {
          const targetSheetId = localStorage.getItem('viewer_target_sheet_id');
          const activeSheet = sheets.find((s) => s.id === targetSheetId) || sheets[0];
          setSelectedSheet(activeSheet);
          await loadSheetData(activeSheet.id);
        } else {
          setSelectedSheet(null);
          resetSheetLayers();
        }
      } else {
        setSelectedDocId('');
        setAvailableSheets([]);
        setSelectedSheet(null);
        resetSheetLayers();
      }
    } catch (e) {
      console.error('Error cargando documentos del proyecto:', e);
    }
  };

  const handleDocChange = async (docId: string) => {
    setSelectedDocId(docId);
    localStorage.setItem('viewer_target_doc_id', docId);
    localStorage.removeItem('viewer_target_sheet_id');
    try {
      const sheets = await apiService.getDocumentSheets(docId);
      setAvailableSheets(sheets);
      if (sheets.length > 0) {
        const sheet = sheets[0];
        setSelectedSheet(sheet);
        await loadSheetData(sheet.id);
      } else {
        setSelectedSheet(null);
        resetSheetLayers();
      }
    } catch (err) {
      console.error('Error al cambiar documento:', err);
    }
  };

  const handleSheetChange = async (sheetId: string) => {
    const sheet = availableSheets.find((s) => s.id === sheetId);
    if (sheet) {
      setSelectedSheet(sheet);
      localStorage.setItem('viewer_target_sheet_id', sheet.id);
      await loadSheetData(sheet.id);
    }
  };

  const resetSheetLayers = () => {
    setOcrTexts([]);
    setRegions([]);
    setTitleBlock(null);
    setTables([]);
    setSelectedTable(null);
    setTableCells([]);
    setSymbols([]);
    setSymbolsSummary(null);
    setSelectedSymbol(null);
    setFindings([]);
    setSelectedFinding(null);
    setManualAnnotations([]);
    setSelectedEntity(null);
    setContextMenu(null);
  };

  const loadSheetData = async (sheetId: string) => {
    try {
      const [texts, sheetRegions, tb, sheetTables, sheetSymbols, symSummary, sheetFindings, anns] = await Promise.all([
        apiService.getSheetTexts(sheetId).catch(() => []),
        apiService.getSheetRegions(sheetId).catch(() => []),
        apiService.getSheetTitleBlock(sheetId).catch(() => null),
        apiService.getSheetTables(sheetId).catch(() => []),
        apiService.getSheetSymbols(sheetId).catch(() => []),
        apiService.getSheetSymbolsSummary(sheetId).catch(() => null),
        apiService.getFindings(undefined, sheetId).catch(() => []),
        apiService.getManualAnnotations(sheetId).catch(() => []),
      ]);
      setOcrTexts(texts);
      setRegions(sheetRegions);
      setTitleBlock(tb);
      setTables(sheetTables);
      setSymbols(sheetSymbols);
      setSymbolsSummary(symSummary);
      setFindings(sheetFindings);
      setManualAnnotations(anns);

      if (sheetFindings.length > 0) {
        handleSelectFinding(sheetFindings[0]);
      } else if (sheetSymbols.length > 0) {
        setSelectedSymbol(sheetSymbols[0]);
        setSelectedEntity({ type: 'symbol', data: sheetSymbols[0] });
      } else if (sheetTables.length > 0) {
        handleSelectTable(sheetTables[0]);
      } else if (tb) {
        setSelectedEntity({ type: 'title_block', data: tb });
      }
    } catch (e) {
      console.error('Error al cargar capas de la lámina:', e);
    }
  };

  const handleSelectTable = async (table: ExtractedTableItem) => {
    setSelectedTable(table);
    setSelectedEntity({ type: 'table', data: table });
    try {
      const cells = await apiService.getTableCells(table.id);
      setTableCells(cells);
    } catch (e) {
      console.error(e);
    }
  };

  const handleSelectSymbol = (sym: DetectedSymbolItem) => {
    setSelectedSymbol(sym);
    setSelectedEntity({ type: 'symbol', data: sym });
  };

  const handleSelectFinding = (f: RuleFindingItem) => {
    setSelectedFinding(f);
    setSelectedEntity({ type: 'finding', data: f });
  };

  const handleRunOcr = async () => {
    if (!selectedSheet) return;
    try {
      setLoadingAction('ocr');
      showToast('Ejecutando OCR espacial sobre lámina...', 'info', 0);
      const texts = await apiService.runSheetOcr(selectedSheet.id, true);
      setOcrTexts(texts);
      showToast(`OCR completado: ${texts.length} bloques de texto extraídos.`, 'success', 4000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error al ejecutar OCR.', 'error', 4000);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRunLayout = async () => {
    if (!selectedSheet) return;
    try {
      setLoadingAction('layout');
      showToast('Segmentando layout y extrayendo viñeta...', 'info', 0);
      const res = await apiService.runSheetLayout(selectedSheet.id, true);
      await loadSheetData(selectedSheet.id);
      showToast(`Layout procesado: ${res.regions_count} regiones detectadas. Score viñeta: ${(res.title_block?.match_score * 100).toFixed(1)}%`, 'success', 4000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error al segmentar layout.', 'error', 4000);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRunTables = async () => {
    if (!selectedSheet) return;
    try {
      setLoadingAction('tables');
      showToast('Extrayendo cuadros y tablas estructuradas...', 'info', 0);
      const res = await apiService.runSheetTables(selectedSheet.id, true);
      await loadSheetData(selectedSheet.id);
      const count = (res as any)?.tables_count ?? (Array.isArray(res) ? res.length : 0);
      showToast(`Extracción de tablas lista: ${count} tablas detectadas.`, 'success', 4000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error al extraer tablas.', 'error', 4000);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRunSymbols = async () => {
    if (!selectedSheet) return;
    try {
      setLoadingAction('symbols');
      showToast('Detectando simbología técnica...', 'info', 0);
      const res = await apiService.runSheetSymbols(selectedSheet.id, true);
      await loadSheetData(selectedSheet.id);
      const count = (res as any)?.symbols_count ?? (Array.isArray(res) ? res.length : 0);
      showToast(`Detección completada: ${count} símbolos detectados.`, 'success', 4000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error al detectar símbolos.', 'error', 4000);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleRunRules = async () => {
    if (!selectedSheet) return;
    try {
      setLoadingAction('rules');
      showToast('Ejecutando auditoría QA/QC...', 'info', 0);
      const res = await apiService.runSheetRules(selectedSheet.id);
      await loadSheetData(selectedSheet.id);
      const count = (res as any)?.findings_count ?? (Array.isArray(res) ? res.length : 0);
      showToast(`Auditoría QA/QC completada: ${count} hallazgos generados.`, 'success', 4000);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error al auditar reglas.', 'error', 4000);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleResolveFinding = async (findingId: string, resolution: 'confirmed' | 'dismissed' | 'accepted_risk') => {
    try {
      await apiService.resolveFinding(findingId, resolution, 'Resolución manual desde visor');
      if (selectedSheet) {
        const sheetFindings = await apiService.getFindings(undefined, selectedSheet.id);
        setFindings(sheetFindings);
        const updated = sheetFindings.find((f) => f.id === findingId);
        if (updated) setSelectedFinding(updated);
      }
      showToast(`Hallazgo actualizado a ${resolution}.`, 'success', 3000);
    } catch (err: any) {
      console.error('Error al resolver hallazgo:', err);
    }
  };

  const handleDeleteAnnotation = async (annotationId: string) => {
    try {
      await apiService.deleteManualAnnotation(annotationId);
      if (selectedSheet) {
        const anns = await apiService.getManualAnnotations(selectedSheet.id);
        setManualAnnotations(anns);
      }
      if (selectedEntity?.data?.id === annotationId) {
        setSelectedEntity(null);
      }
      setContextMenu(null);
      showToast('Anotación eliminada exitosamente.', 'success', 3000);
    } catch (err: any) {
      showToast('Error eliminando anotación.', 'error', 3000);
    }
  };

  // Aceptar Selección Individual y Guardar en Base de Conocimiento Guía
  const handleAcceptAnnotationToKnowledge = async (ann: ManualAnnotation) => {
    try {
      await apiService.addToKnowledgeLibrary({
        source_annotation_id: ann.id,
        entry_type: `${ann.element_type}_template`,
        name: ann.name,
        description: ann.description,
        discipline: ann.discipline,
        crop_image_path: ann.crop_image_path,
        canonical_text: ann.ocr_text,
        tags: ann.tags || [],
      });
      if (selectedSheet) {
        const anns = await apiService.getManualAnnotations(selectedSheet.id);
        setManualAnnotations(anns);
      }
      setContextMenu(null);
      showToast(`"${ann.name}" guardado en Base de Conocimiento Guía.`, 'success', 3500);
    } catch (err: any) {
      showToast(err.response?.data?.detail || 'Error guardando en Base de Conocimiento.', 'error', 3500);
    }
  };

  // Reseleccionar: Redefinir bounding box manteniendo identidad de la selección
  const handleReselectAnnotation = (ann: ManualAnnotation) => {
    setReselectingAnnotationId(ann.id);
    setActiveTool('crop');
    setSelectionMenu(null);
    setContextMenu(null);
    showToast(`Modo Reselección: Arrastra un nuevo recuadro sobre el plano para redefinir «${ann.name}».`, 'info', 4500);
  };

  // =========================================================
  // CONTROL DE ZOOM CON RUEDA DE MOUSE (SENTIDO INVERTIDO)
  // - Hacia adelante / arriba (deltaY < 0): Zoom In / aumentar
  // - Hacia atrás / abajo (deltaY > 0): Zoom Out / empequeñecer
  // =========================================================
  const handleWheel = (e: React.WheelEvent<HTMLDivElement>) => {
    e.preventDefault();
    const zoomStep = 0.15;
    if (e.deltaY < 0) {
      // Hacia adelante / arriba -> Zoom In
      setZoom((prev) => Math.min(Number((prev + zoomStep).toFixed(2)), 5.0));
    } else {
      // Hacia atrás / abajo -> Zoom Out
      setZoom((prev) => Math.max(Number((prev - zoomStep).toFixed(2)), 0.25));
    }
  };

  // =========================================================
  // CONTROL DE PAN (ARRASTRE LIBRE DEL PLANO CON MANO NEGRA)
  // =========================================================
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'pan') {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX - pan.x, y: e.clientY - pan.y });
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'pan' && isPanning) {
      e.preventDefault();
      setPan({
        x: e.clientX - panStart.x,
        y: e.clientY - panStart.y,
      });
    }
  };

  const handleMouseUp = () => {
    if (activeTool === 'pan') {
      setIsPanning(false);
    }
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  // =========================================================
  // SELECCIÓN RECTANGULAR MANUAL SOBRE EL PLANO
  // =========================================================
  const handleCropMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool !== 'crop') return;
    if (e.button !== 0) return; // Solo clic izquierdo
    e.preventDefault();
    e.stopPropagation();

    const rect = sheetContainerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    setCropStart({ x, y });
    setCurrentCrop({ x0: x, y0: y, x1: x, y1: y });
    setIsDrawingCrop(true);
  };

  const handleCropMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawingCrop || !cropStart || activeTool !== 'crop') return;
    e.preventDefault();
    e.stopPropagation();

    const rect = sheetContainerRef.current?.getBoundingClientRect();
    if (!rect) return;

    const currentX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const currentY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    setCurrentCrop({
      x0: Math.min(cropStart.x, currentX),
      y0: Math.min(cropStart.y, currentY),
      x1: Math.max(cropStart.x, currentX),
      y1: Math.max(cropStart.y, currentY),
    });
  };

  const handleCropMouseUp = async () => {
    if (!isDrawingCrop || !currentCrop || activeTool !== 'crop') {
      setIsDrawingCrop(false);
      return;
    }

    const w = currentCrop.x1 - currentCrop.x0;
    const h = currentCrop.y1 - currentCrop.y0;

    // Verificar tamaño mínimo para evitar clicks accidentales
    if (w > 0.008 && h > 0.008 && imgRef.current) {
      try {
        const img = imgRef.current;
        const canvas = document.createElement('canvas');
        const naturalW = img.naturalWidth || img.width || 2000;
        const naturalH = img.naturalHeight || img.height || 1400;

        const sx = currentCrop.x0 * naturalW;
        const sy = currentCrop.y0 * naturalH;
        const sWidth = w * naturalW;
        const sHeight = h * naturalH;

        canvas.width = sWidth;
        canvas.height = sHeight;
        const ctx = canvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(img, sx, sy, sWidth, sHeight, 0, 0, sWidth, sHeight);
          const base64 = canvas.toDataURL('image/png');

          // CASO ESPECIAL: Captura de texto directamente desde el visor principal para el campo "Nombre o Descripción"
          if (isCapturingPlanTextForName) {
            showToast('Extrayendo texto del plano general por OCR...', 'info', 2500);
            try {
              if (selectedSheet) {
                const ocrRes = await apiService.runCropOcr(base64, selectedSheet.id);
                const recognized = (ocrRes.text || '').replace(/[\r\n]+/g, ' ').replace(/\s+/g, ' ').trim();
                if (recognized) {
                  setCapturedPlanTextForName({ text: recognized, timestamp: Date.now() });
                  showToast(`✓ Texto extraído del plano general: "${recognized}"`, 'success', 3500);
                } else {
                  showToast('No se detectó texto en el área seleccionada del plano general.', 'warning', 3500);
                }
              }
            } catch (ocrErr) {
              console.error('Error al ejecutar OCR sobre el plano general:', ocrErr);
              showToast('Error al ejecutar OCR sobre el área seleccionada.', 'error', 3500);
            }
            setIsCapturingPlanTextForName(false);
            setActiveTool('select');
            setIsDrawingCrop(false);
            setCurrentCrop(null);
            setCropStart(null);
            return;
          }

          // Flujo Normal: Recorte de nuevo elemento para clasificación
          setExtractedCropBase64(base64);
          setCropBboxNormalized([currentCrop.x0, currentCrop.y0, currentCrop.x1, currentCrop.y1]);
          
          if (reselectingAnnotationId) {
            const existing = manualAnnotations.find((a) => a.id === reselectingAnnotationId);
            if (existing) {
              setEditingAnnotation({
                ...existing,
                bbox_normalized: [currentCrop.x0, currentCrop.y0, currentCrop.x1, currentCrop.y1],
              });
            }
            setReselectingAnnotationId(null);
          } else {
            setEditingAnnotation(null);
          }
          setShowClassifyModal(true);
        }
      } catch (err) {
        console.error('Error al generar recorte de canvas:', err);
      }
    }

    setIsDrawingCrop(false);
    setCurrentCrop(null);
    setCropStart(null);
  };

  // Helpers de Color
  const getRegionBorderColor = (type: string) => {
    switch (type) {
      case 'drawing_area': return '#0284c7';
      case 'title_block': return '#eab308';
      case 'table_candidate': return '#10b981';
      case 'legend': return '#a855f7';
      case 'revision_table': return '#f97316';
      default: return '#64748b';
    }
  };

  const getSymbolColor = (discipline: string) => {
    switch (discipline) {
      case 'electrical': return '#eab308';
      case 'plumbing': return '#06b6d4';
      case 'hvac': return '#a855f7';
      case 'architecture': return '#3b82f6';
      default: return '#f97316';
    }
  };

  const getSeverityBadgeClass = (sev: string) => {
    switch (sev) {
      case 'critical': return 'badge-danger';
      case 'high': return 'badge-warning';
      case 'medium': return 'badge-info';
      default: return 'badge-secondary';
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      
      {/* Barra de Control Superior */}
      <div className="card" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px', padding: '12px 18px' }}>
        
        {/* Selectores de Contexto */}
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Folder size={15} style={{ color: 'var(--primary)' }} />
            <select
              value={selectedProjectId}
              onChange={(e) => handleProjectChange(e.target.value)}
              style={{
                background: 'var(--bg-sidebar)',
                color: 'var(--text-main)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                padding: '4px 10px',
                fontSize: '12px',
                fontWeight: 600,
              }}
            >
              {projects.map((p) => (
                <option key={p.id} value={p.id}>{p.name} ({p.code})</option>
              ))}
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            {documents.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ color: 'var(--text-dim)' }}>•</span>
                <span style={{ fontSize: '12px', fontWeight: 600 }}>PDF:</span>
                <select
                  value={selectedDocId}
                  onChange={(e) => handleDocChange(e.target.value)}
                  style={{
                    background: 'var(--bg-sidebar)',
                    color: 'var(--text-main)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '12px',
                    fontWeight: 600,
                  }}
                >
                  {documents.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.filename} ({d.page_count} pág.)
                    </option>
                  ))}
                </select>
              </div>
            )}

            {/* Selector de Lámina */}
            {availableSheets.length > 0 && (
              <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                <span style={{ color: 'var(--text-dim)' }}>•</span>
                <span style={{ fontSize: '12px', fontWeight: 600 }}>Lámina:</span>
                <select
                  value={selectedSheet?.id || ''}
                  onChange={(e) => handleSheetChange(e.target.value)}
                  style={{
                    background: 'var(--bg-sidebar)',
                    color: 'var(--primary)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: '6px',
                    padding: '3px 8px',
                    fontSize: '12px',
                    fontWeight: 700,
                  }}
                >
                  {availableSheets.map((s) => (
                    <option key={s.id} value={s.id}>
                      #{s.sheet_number} ({s.sheet_code || 'S/C'}) — {s.width_px}×{s.height_px}px
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Acciones de Pipeline y Toggles de Capas */}
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="btn btn-secondary"
            onClick={handleRunOcr}
            disabled={loadingAction !== null || !selectedSheet}
            title="Dispara OCR espacial sobre la lámina"
            style={{ padding: '6px 10px', fontSize: '12px' }}
          >
            <Play size={13} className={loadingAction === 'ocr' ? 'animate-spin' : ''} />
            <span>{loadingAction === 'ocr' ? 'OCR...' : '1. OCR'}</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleRunLayout}
            disabled={loadingAction !== null || !selectedSheet}
            title="Segmenta layout y extrae metadatos de viñeta"
            style={{ padding: '6px 10px', fontSize: '12px' }}
          >
            <LayoutGrid size={13} className={loadingAction === 'layout' ? 'animate-spin' : ''} />
            <span>{loadingAction === 'layout' ? 'Layout...' : '2. Layout'}</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleRunTables}
            disabled={loadingAction !== null || !selectedSheet}
            title="Extrae tablas estructuradas sobre regiones table_candidate"
            style={{ padding: '6px 10px', fontSize: '12px' }}
          >
            <TableIcon size={13} className={loadingAction === 'tables' ? 'animate-spin' : ''} />
            <span>{loadingAction === 'tables' ? 'Tablas...' : '3. Tablas'}</span>
          </button>

          <button
            className="btn btn-secondary"
            onClick={handleRunSymbols}
            disabled={loadingAction !== null || !selectedSheet}
            title="Detecta símbolos visuales sobre drawing_area con YOLO/SAHI/Geometría"
            style={{ padding: '6px 10px', fontSize: '12px' }}
          >
            <Shapes size={13} className={loadingAction === 'symbols' ? 'animate-spin' : ''} />
            <span>{loadingAction === 'symbols' ? 'Detectando...' : '4. Símbolos'}</span>
          </button>

          <button
            className="btn btn-primary"
            onClick={handleRunRules}
            disabled={loadingAction !== null || !selectedSheet}
            title="Ejecuta motor de reglas determinísticas QA/QC y conciliación cruzada"
            style={{ background: 'linear-gradient(135deg, #f97316 0%, #ea580c 100%)', border: 'none', padding: '6px 12px', fontSize: '12px' }}
          >
            <ShieldAlert size={13} className={loadingAction === 'rules' ? 'animate-spin' : ''} />
            <span>{loadingAction === 'rules' ? 'Auditando...' : '5. QA/QC'}</span>
          </button>

          {/* Botón Lote de Confirmación si hay elementos pendientes */}
          {pendingAnnotations.length > 0 && (
            <button
              className="btn btn-primary"
              style={{ background: 'linear-gradient(135deg, #0284c7 0%, #0369a1 100%)', border: 'none', padding: '6px 12px', fontSize: '12px', display: 'flex', alignItems: 'center', gap: '5px' }}
              onClick={() => setShowConfirmModal(true)}
              title="Revisar lote de confirmación y guardar en Base de Conocimiento"
            >
              <BookmarkPlus size={13} />
              <span>Confirmar Lote ({pendingAnnotations.length})</span>
            </button>
          )}

          <div style={{ width: '1px', height: '24px', background: 'var(--border-subtle)' }} />

          {/* Toggles de Capas */}
          <div style={{ display: 'flex', gap: '4px', background: 'var(--bg-card)', padding: '3px 6px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            <button
              className={`btn ${showOcr ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => setShowOcr(!showOcr)}
            >
              <Type size={11} /> OCR ({ocrTexts.length})
            </button>

            <button
              className={`btn ${showRegions ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => setShowRegions(!showRegions)}
            >
              <LayoutGrid size={11} /> Regiones ({regions.length})
            </button>

            <button
              className={`btn ${showTables ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => setShowTables(!showTables)}
            >
              <TableIcon size={11} /> Tablas ({tables.length})
            </button>

            <button
              className={`btn ${showSymbols ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px' }}
              onClick={() => setShowSymbols(!showSymbols)}
            >
              <Shapes size={11} /> Símbolos ({symbols.length})
            </button>

            <button
              className={`btn ${showFindings ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px', background: showFindings ? '#ef4444' : undefined }}
              onClick={() => setShowFindings(!showFindings)}
            >
              <AlertTriangle size={11} /> Hallazgos ({findings.length})
            </button>

            <button
              className={`btn ${showManualAnnotations ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '3px 8px', fontSize: '11px', background: showManualAnnotations ? '#0891b2' : undefined }}
              onClick={() => setShowManualAnnotations(!showManualAnnotations)}
              title="Muestra u oculta anotaciones manuales del usuario"
            >
              <BookmarkPlus size={11} /> Anotaciones ({manualAnnotations.length})
            </button>

            {/* NUEVO BOTÓN REQUERIDO: SELECCIONES */}
            <button
              className={`btn ${showSelectionsModal ? 'btn-primary' : 'btn-secondary'}`}
              style={{
                padding: '3px 8px',
                fontSize: '11px',
                background: showSelectionsModal ? '#0284c7' : 'linear-gradient(135deg, rgba(2, 132, 199, 0.25) 0%, rgba(14, 165, 233, 0.15) 100%)',
                color: '#38bdf8',
                borderColor: '#0284c7',
                fontWeight: 700,
              }}
              onClick={() => setShowSelectionsModal(true)}
              title="Abrir ventana de gestión de selecciones documentadas del proyecto"
            >
              <SquareCheck size={11} /> Selecciones ({manualAnnotations.length})
            </button>
          </div>
        </div>
      </div>

      {/* Grid Principal: Lienzo de Plano a la Izquierda, Inspector a la Derecha */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 440px', gap: '20px' }}>
        
        {/* Contenedor del Plano y Capas Espaciales */}
        <div
          className="card"
          style={{
            position: 'relative',
            height: '720px',
            background: '#070b14',
            overflow: 'hidden',
            border: '1px solid var(--border-subtle)',
            borderRadius: '12px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          {/* Fondo Blueprint Grid */}
          <div
            style={{
              position: 'absolute',
              inset: 0,
              backgroundImage: 'linear-gradient(rgba(56, 189, 248, 0.04) 1px, transparent 1px), linear-gradient(90deg, rgba(56, 189, 248, 0.04) 1px, transparent 1px)',
              backgroundSize: '32px 32px',
              opacity: 0.7,
              pointerEvents: 'none',
            }}
          />

          {/* Barra de Herramientas Flotante del Visor (Herramientas Mutuamente Excluyentes & Zoom) */}
          {selectedSheet && (
            <div
              style={{
                position: 'absolute',
                top: '12px',
                left: '12px',
                zIndex: 50,
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                background: 'rgba(15, 23, 42, 0.90)',
                backdropFilter: 'blur(12px)',
                padding: '4px 8px',
                borderRadius: '10px',
                border: '1px solid var(--border-subtle)',
                boxShadow: '0 8px 24px rgba(0,0,0,0.5)',
              }}
            >
              {/* Grupo 1: Selector de Herramientas de Interacción */}
              <div style={{ display: 'flex', gap: '2px', background: 'rgba(2, 6, 23, 0.6)', padding: '2px', borderRadius: '6px', border: '1px solid rgba(255,255,255,0.06)' }}>
                <button
                  className={`btn ${activeTool === 'select' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '4px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: '4px' }}
                  onClick={() => setActiveTool('select')}
                  title="Modo Inspección: Click para explorar entidades de IA y hallazgos"
                >
                  <MousePointer size={12} />
                  <span>Inspeccionar</span>
                </button>

                <button
                  className={`btn ${activeTool === 'pan' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: activeTool === 'pan' ? '#0284c7' : undefined,
                  }}
                  onClick={() => setActiveTool('pan')}
                  title="Herramienta Pan: Arrastrar plano libremente con cursor mano negra"
                >
                  <Hand size={12} />
                  <span>Pan</span>
                </button>

                <button
                  className={`btn ${activeTool === 'crop' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{
                    padding: '4px 8px',
                    fontSize: '11px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    background: activeTool === 'crop' ? '#ef4444' : undefined,
                  }}
                  onClick={() => setActiveTool('crop')}
                  title="Selección Manual: Arrastrar marco rectangular fino para extraer recorte"
                >
                  <Crop size={12} />
                  <span>Selección</span>
                </button>
              </div>

              <div style={{ width: '1px', height: '18px', background: 'var(--border-subtle)' }} />

              {/* Grupo 2: Controles de Zoom y Ajuste */}
              <div style={{ display: 'flex', alignItems: 'center', gap: '3px' }}>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 6px', fontSize: '11px' }}
                  onClick={() => setZoom((prev) => Math.min(Number((prev + 0.25).toFixed(2)), 5.0))}
                  title="Acercar (Zoom In)"
                >
                  <ZoomIn size={13} />
                </button>
                <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)', display: 'flex', alignItems: 'center', minWidth: '40px', justifyContent: 'center' }}>
                  {(zoom * 100).toFixed(0)}%
                </span>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 6px', fontSize: '11px' }}
                  onClick={() => setZoom((prev) => Math.max(Number((prev - 0.25).toFixed(2)), 0.25))}
                  title="Alejar (Zoom Out)"
                >
                  <ZoomOut size={13} />
                </button>
                <button
                  className="btn btn-secondary"
                  style={{ padding: '4px 6px', fontSize: '11px' }}
                  onClick={handleResetView}
                  title="Restablecer Vista (100% y centrado)"
                >
                  <RotateCcw size={13} />
                </button>
              </div>
            </div>
          )}

          {/* Banner de Estado Unificado en Esquina Superior Derecha */}
          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '12px',
              zIndex: 50,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'flex-end',
              gap: '6px',
              pointerEvents: 'none',
            }}
          >
            {/* MENÚ CONTEXTUAL SOBRE SELECCIÓN ACTIVA */}
            {selectedEntity?.type === 'manual_annotation' && selectedEntity.data && (
              <div
                style={{
                  background: '#020617',
                  border: '1px solid #334155',
                  borderRadius: '10px',
                  padding: '6px 10px',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.8)',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  pointerEvents: 'auto',
                }}
                className="animate-in fade-in duration-150"
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', borderRight: '1px solid #334155', paddingRight: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: getAnnotationColor(selectedEntity.data.element_type) }} />
                  <span style={{ fontSize: '11px', fontWeight: 700, color: '#f8fafc', maxWidth: '140px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {selectedEntity.data.name}
                  </span>
                </div>

                {/* BOTÓN 1: RESELECCIONAR */}
                <button
                  onClick={() => handleReselectAnnotation(selectedEntity.data)}
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '11px', color: '#38bdf8', borderColor: '#0284c7', display: 'flex', alignItems: 'center', gap: '4px' }}
                  title="Redefinir el área de esta selección manteniendo sus datos"
                >
                  <Crop size={12} />
                  <span>Reseleccionar</span>
                </button>

                {/* BOTÓN 2: ELIMINAR */}
                <button
                  onClick={() => handleDeleteAnnotation(selectedEntity.data.id)}
                  className="btn btn-secondary"
                  style={{ padding: '4px 8px', fontSize: '11px', color: '#ef4444', borderColor: '#b91c1c', display: 'flex', alignItems: 'center', gap: '4px' }}
                  title="Eliminar esta selección del plano y del listado"
                >
                  <Trash2 size={12} />
                  <span>Eliminar</span>
                </button>

                <button
                  onClick={() => {
                    setSelectedEntity(null);
                    setSelectionMenu(null);
                  }}
                  style={{ background: 'none', border: 'none', color: '#64748b', cursor: 'pointer', padding: '2px' }}
                  title="Desmarcar"
                >
                  <X size={13} />
                </button>
              </div>
            )}

            {/* Mensaje de ayuda previo al recorte o captura de texto */}
            {isCapturingPlanTextForName ? (
              <div
                style={{
                  background: '#020617',
                  border: '1px solid #38bdf8',
                  color: '#e0f2fe',
                  padding: '6px 12px',
                  borderRadius: '10px',
                  fontSize: '11px',
                  fontWeight: 700,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.8), 0 0 0 1px #0284c7',
                  pointerEvents: 'auto',
                }}
                className="animate-in fade-in duration-150"
              >
                <ScanText size={14} className="text-sky-400 animate-pulse" />
                <span>Captura OCR de Texto: Arrastra un marco sobre el rótulo o código del plano</span>
                <button
                  type="button"
                  onClick={() => {
                    setIsCapturingPlanTextForName(false);
                    setActiveTool('select');
                    setIsDrawingCrop(false);
                    setCurrentCrop(null);
                  }}
                  style={{
                    background: '#1e293b',
                    border: '1px solid #475569',
                    color: '#f8fafc',
                    padding: '2px 6px',
                    borderRadius: '6px',
                    fontSize: '10px',
                    cursor: 'pointer',
                    marginLeft: '4px',
                  }}
                  title="Cancelar captura de texto"
                >
                  Cancelar
                </button>
              </div>
            ) : activeTool === 'crop' && !isDrawingCrop ? (
              <div
                style={{
                  background: '#020617',
                  border: '1px solid #ef4444',
                  color: '#fca5a5',
                  padding: '5px 10px',
                  borderRadius: '8px',
                  fontSize: '11px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
                }}
              >
                <Crosshair size={13} className="text-rose-400" />
                <span>{reselectingAnnotationId ? 'Modo Reselección: Arrastra un nuevo recuadro sobre el plano' : 'Modo Selección: Arrastra un marco sobre el plano para recortar'}</span>
              </div>
            ) : null}

            {/* Toast de acción o estado del visor */}
            {viewerToast && (
              <div
                style={{
                  background: 'rgba(15, 23, 42, 0.96)',
                  backdropFilter: 'blur(8px)',
                  border: `1px solid ${viewerToast.type === 'error' ? '#ef4444' : viewerToast.type === 'success' ? '#10b981' : '#38bdf8'}`,
                  color: viewerToast.type === 'error' ? '#fca5a5' : viewerToast.type === 'success' ? '#6ee7b7' : '#7dd3fc',
                  padding: '5px 12px',
                  borderRadius: '8px',
                  fontSize: '11px',
                  fontWeight: 600,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  boxShadow: '0 4px 16px rgba(0,0,0,0.6)',
                }}
              >
                {viewerToast.type === 'success' ? <CheckCircle size={13} /> : viewerToast.type === 'error' ? <AlertTriangle size={13} /> : <Info size={13} />}
                <span>{viewerToast.message}</span>
              </div>
            )}
          </div>

          {/* Canvas Viewport que mantiene exactamente el Aspect Ratio de la lámina */}
          <div
            ref={viewportRef}
            onWheel={handleWheel}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
            style={{
              position: 'relative',
              width: '100%',
              height: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              overflow: 'hidden',
              padding: '16px',
              cursor: activeTool === 'pan' ? (isPanning ? BLACK_GRABBING_CURSOR : BLACK_GRAB_CURSOR) : activeTool === 'crop' ? RED_CROSSHAIR_CURSOR : 'default',
              userSelect: 'none',
            }}
          >
            {selectedSheet ? (
              <div
                ref={sheetContainerRef}
                onMouseDown={handleCropMouseDown}
                onMouseMove={handleCropMouseMove}
                onMouseUp={handleCropMouseUp}
                style={{
                  position: 'relative',
                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                  transformOrigin: 'center center',
                  transition: isPanning ? 'none' : 'transform 0.12s ease-out',
                  maxWidth: '100%',
                  maxHeight: '100%',
                  aspectRatio: selectedSheet.width_px && selectedSheet.height_px
                    ? `${selectedSheet.width_px} / ${selectedSheet.height_px}`
                    : '1.414',
                  boxShadow: '0 12px 36px rgba(0, 0, 0, 0.8), 0 0 0 1px var(--border-subtle)',
                  borderRadius: '6px',
                  overflow: 'hidden',
                  background: '#080e1a',
                  pointerEvents: activeTool === 'pan' ? 'none' : 'auto',
                }}
              >
                {/* Imagen Base Rasterizada Servida Directamente por el Backend */}
                <img
                  ref={imgRef}
                  src={apiService.getSheetImageUrl(selectedSheet.id)}
                  alt={`Lámina ${selectedSheet.sheet_code || selectedSheet.sheet_number}`}
                  crossOrigin="anonymous"
                  style={{
                    width: '100%',
                    height: '100%',
                    display: 'block',
                    objectFit: 'fill',
                    position: 'relative',
                    zIndex: 1,
                    pointerEvents: 'none',
                  }}
                  onError={(e) => {
                    const target = e.currentTarget;
                    if (selectedSheet.raster_image_path && !target.dataset.fallbackTried) {
                      target.dataset.fallbackTried = 'true';
                      const fallbackUrl = `http://localhost:8000/${selectedSheet.raster_image_path.replace(/^\.\//, '')}`;
                      target.src = fallbackUrl;
                    }
                  }}
                />

                {/* Overlays de Macro-Regiones de Layout */}
                {showRegions && regions.map((reg) => {
                  const [x0, y0, x1, y1] = reg.bbox_normalized;
                  const isSelected = selectedEntity?.type === 'region' && selectedEntity?.data?.id === reg.id;
                  const borderColor = getRegionBorderColor(reg.region_type);

                  return (
                    <div
                      key={reg.id}
                      onClick={() => setSelectedEntity({ type: 'region', data: reg })}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${(x1 - x0) * 100}%`,
                        height: `${(y1 - y0) * 100}%`,
                        border: `1.5px dashed ${borderColor}`,
                        background: isSelected ? 'rgba(56, 189, 248, 0.25)' : 'rgba(0, 0, 0, 0.05)',
                        cursor: 'pointer',
                        zIndex: isSelected ? 20 : 5,
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '3px',
                      }}
                      title={`Región: ${reg.region_type} (${(reg.confidence * 100).toFixed(0)}%)`}
                    >
                      <span style={{ fontSize: '9px', background: borderColor, color: '#000', fontWeight: 800, padding: '1px 4px', borderRadius: '2px' }}>
                        {reg.region_type}
                      </span>
                    </div>
                  );
                })}

                {/* Overlays de OCR Espacial */}
                {showOcr && ocrTexts.map((txt) => {
                  const [x0, y0, x1, y1] = txt.bbox_normalized;
                  const isSelected = selectedEntity?.type === 'ocr' && selectedEntity?.data?.id === txt.id;

                  return (
                    <div
                      key={txt.id}
                      onClick={() => setSelectedEntity({ type: 'ocr', data: txt })}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${(x1 - x0) * 100}%`,
                        height: `${(y1 - y0) * 100}%`,
                        border: `1px solid ${isSelected ? '#38bdf8' : 'rgba(56, 189, 248, 0.35)'}`,
                        background: isSelected ? 'rgba(56, 189, 248, 0.3)' : 'rgba(56, 189, 248, 0.08)',
                        cursor: 'pointer',
                        zIndex: isSelected ? 25 : 6,
                      }}
                      title={`OCR: "${txt.text || (txt as any).text_content || ''}" (${(txt.confidence * 100).toFixed(0)}%)`}
                    />
                  );
                })}

                {/* Overlays de Tablas Técnicas */}
                {showTables && tables.map((tbl) => {
                  const [x0, y0, x1, y1] = tbl.bbox_normalized;
                  const isSelected = selectedEntity?.type === 'table' && selectedEntity?.data?.id === tbl.id;

                  return (
                    <div
                      key={tbl.id}
                      onClick={() => handleSelectTable(tbl)}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${(x1 - x0) * 100}%`,
                        height: `${(y1 - y0) * 100}%`,
                        border: `1.5px solid ${isSelected ? '#ffffff' : '#10b981'}`,
                        background: isSelected ? 'rgba(16, 185, 129, 0.3)' : 'rgba(16, 185, 129, 0.12)',
                        boxShadow: isSelected ? '0 0 12px #10b981' : 'none',
                        cursor: 'pointer',
                        zIndex: isSelected ? 30 : 10,
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '2px',
                      }}
                      title={`Tabla: ${tbl.title || 'Cuadro'} (${tbl.row_count}x${tbl.column_count})`}
                    >
                      <span style={{ fontSize: '8px', background: '#10b981', color: '#000', fontWeight: 800, padding: '1px 3px', borderRadius: '2px' }}>
                        📊 {tbl.title || 'TABLA'}
                      </span>
                    </div>
                  );
                })}

                {/* Overlays de Símbolos Visuales */}
                {showSymbols && symbols.map((sym) => {
                  const [x0, y0, x1, y1] = sym.bbox_normalized;
                  const isSelected = selectedEntity?.type === 'symbol' && selectedEntity?.data?.id === sym.id;
                  const color = getSymbolColor(sym.discipline);

                  return (
                    <div
                      key={sym.id}
                      onClick={() => handleSelectSymbol(sym)}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${Math.max((x1 - x0) * 100, 2)}%`,
                        height: `${Math.max((y1 - y0) * 100, 2)}%`,
                        border: `1.5px solid ${isSelected ? '#ffffff' : color}`,
                        background: isSelected ? 'rgba(249, 115, 22, 0.4)' : 'rgba(249, 115, 22, 0.18)',
                        boxShadow: isSelected ? `0 0 12px ${color}` : 'none',
                        cursor: 'pointer',
                        zIndex: isSelected ? 35 : 15,
                        borderRadius: '3px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '1px',
                      }}
                      title={`[${sym.discipline.toUpperCase()}] ${sym.symbol_type} (${(sym.confidence * 100).toFixed(0)}%)`}
                    >
                      <span style={{ fontSize: '7px', background: color, color: '#000', fontWeight: 800, padding: '0 2px', borderRadius: '2px' }}>
                        {sym.symbol_type.slice(0, 8)}
                      </span>
                    </div>
                  );
                })}

                {/* Overlays de Hallazgos QA/QC */}
                {showFindings && findings.map((f) => {
                  const loc = (f as any).primary_location?.bbox_normalized || f.bbox || [0.2, 0.2, 0.3, 0.3];
                  const [x0, y0, x1, y1] = loc;
                  const isSelected = selectedFinding?.id === f.id;

                  return (
                    <div
                      key={f.id}
                      onClick={() => handleSelectFinding(f)}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${Math.max((x1 - x0) * 100, 3)}%`,
                        height: `${Math.max((y1 - y0) * 100, 3)}%`,
                        border: `1.5px solid ${isSelected ? '#ffffff' : '#ef4444'}`,
                        background: isSelected ? 'rgba(239, 68, 68, 0.4)' : 'rgba(239, 68, 68, 0.2)',
                        boxShadow: isSelected ? '0 0 14px #ef4444' : 'none',
                        cursor: 'pointer',
                        zIndex: isSelected ? 35 : 20,
                        borderRadius: '4px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '2px',
                      }}
                      title={`[${f.severity.toUpperCase()}] ${f.title}`}
                    >
                      <span style={{ fontSize: '8px', background: '#ef4444', color: '#fff', fontWeight: 800, padding: '1px 4px', borderRadius: '2px' }}>
                        ⚠️ {f.rule_code}
                      </span>
                    </div>
                  );
                })}

                {/* Overlays de Anotaciones Manuales (Línea Continua Fina con Color por Tipo) */}
                {showManualAnnotations && manualAnnotations.map((ann) => {
                  const bbox = Array.isArray(ann.bbox_normalized) && ann.bbox_normalized.length === 4 ? ann.bbox_normalized : [0, 0, 0, 0];
                  const [x0, y0, x1, y1] = bbox;
                  const isSelected = selectedEntity?.type === 'manual_annotation' && selectedEntity?.data?.id === ann.id;
                  const color = getAnnotationColor(ann.element_type);

                  return (
                    <div
                      key={ann.id}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedEntity({ type: 'manual_annotation', data: ann });
                        setSelectionMenu({
                          x: e.clientX,
                          y: e.clientY,
                          annotation: ann,
                        });
                      }}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setSelectedEntity({ type: 'manual_annotation', data: ann });
                        setContextMenu({
                          x: e.clientX,
                          y: e.clientY,
                          annotation: ann,
                        });
                      }}
                      style={{
                        position: 'absolute',
                        left: `${x0 * 100}%`,
                        top: `${y0 * 100}%`,
                        width: `${Math.max((x1 - x0) * 100, 2)}%`,
                        height: `${Math.max((y1 - y0) * 100, 2)}%`,
                        border: isSelected ? `2px solid #ffffff` : `1.5px solid ${color}`,
                        background: isSelected ? `${color}40` : `${color}18`,
                        boxShadow: isSelected ? `0 0 14px ${color}` : 'none',
                        cursor: 'pointer',
                        zIndex: isSelected ? 40 : 25,
                        borderRadius: '3px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        padding: '2px',
                        transition: 'border 0.15s ease, background 0.15s ease',
                      }}
                      title={`[${ann.element_type.toUpperCase()}] ${ann.name} (Clic: opciones)`}
                    >
                      <span style={{ fontSize: '8px', background: color, color: '#000', fontWeight: 800, padding: '1px 4px', borderRadius: '2px', boxShadow: '0 1px 3px rgba(0,0,0,0.5)' }}>
                        {ann.name}
                      </span>
                    </div>
                  );
                })}

                {/* Marco de Selección Rectangular Mientras se Dibuja (Línea Muy Fina Segmentada 1px) */}
                {isDrawingCrop && currentCrop && (
                  <div
                    style={{
                      position: 'absolute',
                      left: `${currentCrop.x0 * 100}%`,
                      top: `${currentCrop.y0 * 100}%`,
                      width: `${(currentCrop.x1 - currentCrop.x0) * 100}%`,
                      height: `${(currentCrop.y1 - currentCrop.y0) * 100}%`,
                      border: '1px dashed #ef4444',
                      background: 'rgba(239, 68, 68, 0.12)',
                      pointerEvents: 'none',
                      zIndex: 60,
                      borderRadius: '2px',
                    }}
                  />
                )}

                {/* Marco de Selección Activa Mientras el Panel Flotante está Abierto */}
                {showClassifyModal && cropBboxNormalized && (
                  (() => {
                    const activeBbox = Array.isArray(cropBboxNormalized) && cropBboxNormalized.length === 4 ? cropBboxNormalized : [0, 0, 0, 0];
                    if (activeBbox[2] - activeBbox[0] <= 0.001) return null;
                    return (
                      <div
                        style={{
                          position: 'absolute',
                          left: `${activeBbox[0] * 100}%`,
                          top: `${activeBbox[1] * 100}%`,
                          width: `${(activeBbox[2] - activeBbox[0]) * 100}%`,
                          height: `${(activeBbox[3] - activeBbox[1]) * 100}%`,
                          border: '2px solid #38bdf8',
                          background: 'rgba(56, 189, 248, 0.15)',
                          boxShadow: '0 0 16px rgba(56, 189, 248, 0.4)',
                          pointerEvents: 'none',
                          zIndex: 60,
                          borderRadius: '3px',
                        }}
                      />
                    );
                  })()
                )}
              </div>

            ) : (
              <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: '40px 20px' }}>
                <LayoutGrid size={56} style={{ margin: '0 auto 16px', opacity: 0.3 }} />
                <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-main)', marginBottom: '6px' }}>
                  Sin documentos ni láminas para mostrar
                </h3>
                <p style={{ fontSize: '13px', maxWidth: '400px', margin: '0 auto 16px', lineHeight: '1.5' }}>
                  No se encontraron planos registrados en el proyecto activo. Ve a la pantalla de ingesta para subir tu primer plano PDF.
                </p>
                <button
                  className="btn btn-primary"
                  onClick={() => window.dispatchEvent(new CustomEvent('navigate-tab', { detail: { tab: 'projects' } }))}
                >
                  <Upload size={14} /> Ir a Ingesta de Planos
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Panel Lateral: Inspector Multidimensional, Auditoría y Leyenda */}
        <div className="card" style={{ height: '720px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
          
          {/* Sección 1: Hallazgos de Auditoría QA/QC */}
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
              <h2 style={{ fontSize: '15px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <ShieldAlert size={16} style={{ color: '#ef4444' }} />
                Hallazgos QA/QC ({findings.length})
              </h2>
            </div>

            {findings.length === 0 ? (
              <div style={{ background: 'var(--bg-sidebar)', padding: '12px', borderRadius: '8px', textAlign: 'center', color: 'var(--text-dim)', fontSize: '12px' }}>
                <CheckCircle size={24} style={{ margin: '0 auto 6px', color: '#10b981' }} />
                {selectedSheet ? (
                  <span>Sin hallazgos reportados. Pulsa <strong>"5. QA/QC"</strong> para auditar.</span>
                ) : (
                  <span>Selecciona una lámina para auditar.</span>
                )}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '180px', overflowY: 'auto' }}>
                {findings.map((f) => (
                  <div
                    key={f.id}
                    onClick={() => handleSelectFinding(f)}
                    style={{
                      background: selectedFinding?.id === f.id ? 'rgba(239, 68, 68, 0.15)' : 'var(--bg-sidebar)',
                      border: `1px solid ${selectedFinding?.id === f.id ? '#ef4444' : 'var(--border-subtle)'}`,
                      padding: '8px 10px',
                      borderRadius: '6px',
                      cursor: 'pointer',
                      fontSize: '11px',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
                      <span className={`badge ${getSeverityBadgeClass(f.severity)}`} style={{ fontSize: '9px', padding: '1px 5px' }}>
                        {f.severity.toUpperCase()}
                      </span>
                      <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>{f.status}</span>
                    </div>
                    <strong style={{ display: 'block', color: 'var(--text-main)', marginBottom: '2px' }}>{f.title}</strong>
                    <div style={{ color: 'var(--text-dim)', fontSize: '10px' }}>Regla: <code>{f.rule_code}</code></div>
                  </div>
                ))}
              </div>
            )}

            {selectedFinding && (
              <div style={{ marginTop: '10px', background: 'var(--bg-sidebar)', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-subtle)', fontSize: '11px', lineHeight: '1.5' }}>
                <div style={{ fontWeight: 700, color: '#ef4444', marginBottom: '4px' }}>{selectedFinding.title}</div>
                <div style={{ color: 'var(--text-dim)', marginBottom: '6px' }}>{selectedFinding.description}</div>
                
                {selectedFinding.recommendation && (
                  <div style={{ background: 'rgba(56, 189, 248, 0.1)', padding: '6px', borderRadius: '4px', marginBottom: '6px', color: 'var(--primary)' }}>
                    <strong>Recomendación:</strong> {selectedFinding.recommendation}
                  </div>
                )}

                {/* Acciones de Resolución */}
                <div style={{ display: 'flex', gap: '6px', marginTop: '8px' }}>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '10px', padding: '3px 6px' }}
                    onClick={() => handleResolveFinding(selectedFinding.id, 'confirmed')}
                  >
                    <CheckCircle2 size={12} /> Confirmar
                  </button>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '10px', padding: '3px 6px' }}
                    onClick={() => handleResolveFinding(selectedFinding.id, 'dismissed')}
                  >
                    <XCircle size={12} /> Descartar
                  </button>
                  <button
                    className="btn btn-secondary"
                    style={{ fontSize: '10px', padding: '3px 6px' }}
                    onClick={() => handleResolveFinding(selectedFinding.id, 'accepted_risk')}
                  >
                    <AlertOctagon size={12} /> Riesgo Aceptado
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Sección 2: Anotaciones Manuales y Conocimiento */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <BookmarkPlus size={15} style={{ color: '#06b6d4' }} />
                Anotaciones Manuales ({manualAnnotations.length})
              </h2>
            </div>

            {manualAnnotations.length === 0 ? (
              <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>
                Activa la herramienta <strong>"Selección"</strong> y arrastra sobre el plano para recortar símbolos, tablas o notas.
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '160px', overflowY: 'auto' }}>
                {manualAnnotations.map((ann) => {
                  const color = getAnnotationColor(ann.element_type);
                  const isSelected = selectedEntity?.data?.id === ann.id;
                  return (
                    <div
                      key={ann.id}
                      onClick={() => setSelectedEntity({ type: 'manual_annotation', data: ann })}
                      onContextMenu={(e) => {
                        e.preventDefault();
                        setSelectedEntity({ type: 'manual_annotation', data: ann });
                        setContextMenu({ x: e.clientX, y: e.clientY, annotation: ann });
                      }}
                      style={{
                        background: isSelected ? `${color}20` : 'var(--bg-sidebar)',
                        border: `1px solid ${isSelected ? color : 'var(--border-subtle)'}`,
                        padding: '6px 8px',
                        borderRadius: '6px',
                        cursor: 'pointer',
                        fontSize: '11px',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0 }}>
                        <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: color, flexShrink: 0 }} />
                        <span style={{ fontSize: '9px', fontWeight: 700, color: color, textTransform: 'uppercase' }}>
                          [{ann.element_type}]
                        </span>
                        <strong style={{ color: 'var(--text-main)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {ann.name}
                        </strong>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setEditingAnnotation(ann);
                            setExtractedCropBase64(null);
                            setCropBboxNormalized(ann.bbox_normalized);
                            setShowClassifyModal(true);
                          }}
                          title="Editar anotación"
                          style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', padding: '2px' }}
                        >
                          <Edit3 size={12} />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDeleteAnnotation(ann.id);
                          }}
                          title="Eliminar anotación"
                          style={{ background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '2px' }}
                        >
                          <Trash2 size={12} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Sección 3: Símbolos Visuales Detectados */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '6px' }}>
              <h2 style={{ fontSize: '14px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px' }}>
                <Shapes size={15} style={{ color: '#f97316' }} />
                Símbolos ({symbols.length})
              </h2>

              <select
                value={disciplineFilter}
                onChange={(e) => setDisciplineFilter(e.target.value)}
                style={{ background: 'var(--bg-sidebar)', color: 'var(--text-main)', border: '1px solid var(--border-subtle)', borderRadius: '6px', fontSize: '11px', padding: '2px 6px' }}
              >
                <option value="all">Todas</option>
                <option value="architecture">Arquitectura</option>
                <option value="electrical">Electricidad</option>
                <option value="plumbing">Sanitario</option>
              </select>
            </div>

            {selectedSymbol && (
              <div style={{ background: 'var(--bg-sidebar)', padding: '8px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '11px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong style={{ color: getSymbolColor(selectedSymbol.discipline) }}>{selectedSymbol.symbol_type}</strong>
                  <span>{(selectedSymbol.confidence * 100).toFixed(0)}% conf</span>
                </div>
                <div style={{ color: 'var(--text-dim)', fontSize: '10px', marginTop: '2px' }}>
                  Motor: <code>{selectedSymbol.source_engine}</code>
                </div>
              </div>
            )}
          </div>

          {/* Sección 4: Tablas Técnicas */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: 700, display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
              <TableIcon size={15} style={{ color: '#10b981' }} />
              Cuadros & Tablas ({tables.length})
            </h2>

            {selectedTable && (
              <div style={{ background: 'var(--bg-sidebar)', padding: '6px 8px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '11px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <strong>{selectedTable.title || 'Cuadro'}</strong>
                  <span>{selectedTable.row_count}×{selectedTable.column_count}</span>
                </div>
              </div>
            )}
          </div>

          {/* Sección 5: Metadatos de Viñeta */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '4px' }}>Viñeta Técnica</h2>
            {titleBlock ? (
              <div style={{ background: 'var(--bg-sidebar)', padding: '6px 8px', borderRadius: '6px', border: '1px solid var(--border-subtle)', fontSize: '11px' }}>
                <div><strong>Lámina:</strong> <span className="font-mono" style={{ color: 'var(--primary)' }}>{titleBlock.sheet_code || 'N/A'}</span> • <strong>Escala:</strong> {titleBlock.scale_text || 'N/A'}</div>
              </div>
            ) : (
              <div style={{ color: 'var(--text-dim)', fontSize: '11px' }}>Sin viñeta procesada.</div>
            )}
          </div>

          {/* Sección 6: Leyenda de Colores de Selección (Lado Inferior Derecho) */}
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '10px', marginTop: 'auto' }}>
            <h3 style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Layers size={13} />
              Leyenda de Tipos de Selección
            </h3>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '6px', background: 'rgba(2, 6, 23, 0.4)', padding: '8px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              {Object.entries(TAXONOMY_COLORS).map(([key, item]) => (
                <div key={key} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '10px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '2px', background: item.color, display: 'inline-block', flexShrink: 0 }} />
                  <span style={{ color: 'var(--text-dim)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {item.label}
                  </span>
                </div>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* Menú Contextual Flotante para Clic Derecho sobre Selección */}
      {contextMenu && (
        <div
          style={{
            position: 'fixed',
            top: `${contextMenu.y}px`,
            left: `${contextMenu.x}px`,
            zIndex: 100,
            background: 'rgba(15, 23, 42, 0.96)',
            backdropFilter: 'blur(12px)',
            border: '1px solid rgba(255, 255, 255, 0.15)',
            borderRadius: '10px',
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.8), 0 0 0 1px rgba(0,0,0,0.5)',
            padding: '8px',
            minWidth: '220px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            animation: 'fade-in 0.15s ease-out',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Cabecera del elemento */}
          <div style={{ padding: '4px 6px', borderBottom: '1px solid var(--border-subtle)', marginBottom: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: getAnnotationColor(contextMenu.annotation.element_type),
                }}
              />
              <span style={{ fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', color: getAnnotationColor(contextMenu.annotation.element_type) }}>
                {contextMenu.annotation.element_type}
              </span>
            </div>
            <strong style={{ display: 'block', fontSize: '11px', color: 'var(--text-main)', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {contextMenu.annotation.name}
            </strong>
          </div>

          {/* Acciones */}
          <button
            onClick={() => {
              setEditingAnnotation(contextMenu.annotation);
              setExtractedCropBase64(null);
              setCropBboxNormalized(contextMenu.annotation.bbox_normalized);
              setContextMenu(null);
              setShowClassifyModal(true);
            }}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Edit3 size={13} style={{ color: '#38bdf8' }} />
            <span>Editar datos</span>
          </button>

          <button
            onClick={() => handleReselectAnnotation(contextMenu.annotation)}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#38bdf8',
            }}
          >
            <Crop size={13} style={{ color: '#38bdf8' }} />
            <span>Reseleccionar área</span>
          </button>

          <button
            onClick={() => handleAcceptAnnotationToKnowledge(contextMenu.annotation)}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Check size={13} style={{ color: '#10b981' }} />
            <span>Aceptar (Base de Conocimiento)</span>
          </button>

          <button
            onClick={() => handleDeleteAnnotation(contextMenu.annotation.id)}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#ef4444',
            }}
          >
            <Trash2 size={13} style={{ color: '#ef4444' }} />
            <span>Eliminar selección</span>
          </button>
        </div>
      )}

      {/* Menú Contextual Flotante para Click Izquierdo sobre Selección */}
      {selectionMenu && (
        <div
          style={{
            position: 'fixed',
            top: `${selectionMenu.y}px`,
            left: `${selectionMenu.x}px`,
            zIndex: 100,
            backgroundColor: '#020617',
            border: '1px solid #334155',
            borderRadius: '10px',
            boxShadow: '0 12px 32px rgba(0, 0, 0, 0.9), 0 0 0 1px #334155',
            padding: '8px',
            minWidth: '200px',
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
            animation: 'fade-in 0.15s ease-out',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ padding: '4px 6px', borderBottom: '1px solid #1e293b', marginBottom: '4px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <span
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  background: getAnnotationColor(selectionMenu.annotation.element_type),
                }}
              />
              <span style={{ fontSize: '9px', fontWeight: 800, textTransform: 'uppercase', color: getAnnotationColor(selectionMenu.annotation.element_type) }}>
                {selectionMenu.annotation.element_type}
              </span>
            </div>
            <strong style={{ display: 'block', fontSize: '11px', color: '#f8fafc', marginTop: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {selectionMenu.annotation.name}
            </strong>
          </div>

          {/* Opción 1: Editar datos */}
          <button
            onClick={() => {
              setEditingAnnotation(selectionMenu.annotation);
              setExtractedCropBase64(null);
              setCropBboxNormalized(
                Array.isArray(selectionMenu.annotation.bbox_normalized) && selectionMenu.annotation.bbox_normalized.length === 4
                  ? selectionMenu.annotation.bbox_normalized
                  : [0, 0, 0, 0]
              );
              setSelectionMenu(null);
              setShowClassifyModal(true);
            }}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#38bdf8',
            }}
          >
            <Edit3 size={13} />
            <span>Editar datos</span>
          </button>

          {/* Opción 2: Reseleccionar */}
          <button
            onClick={() => handleReselectAnnotation(selectionMenu.annotation)}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#38bdf8',
            }}
          >
            <Crop size={13} />
            <span>Reseleccionar</span>
          </button>

          {/* Opción 3: Eliminar */}
          <button
            onClick={() => {
              handleDeleteAnnotation(selectionMenu.annotation.id);
              setSelectionMenu(null);
            }}
            className="btn btn-secondary"
            style={{
              justifyContent: 'flex-start',
              padding: '6px 8px',
              fontSize: '11px',
              border: 'none',
              borderRadius: '6px',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              color: '#ef4444',
            }}
          >
            <Trash2 size={13} />
            <span>Eliminar</span>
          </button>
        </div>
      )}

      {/* Modal 1: Clasificación / Edición de Elemento y OCR */}
      {selectedSheet && (
        <AnnotationClassifyModal
          isOpen={showClassifyModal}
          cropImageBase64={extractedCropBase64}
          bboxNormalized={cropBboxNormalized}
          sheetId={selectedSheet.id}
          projectId={selectedProjectId}
          documentId={selectedDocId}
          initialData={editingAnnotation}
          onRequestPlanTextCapture={() => {
            if (isCapturingPlanTextForName) {
              setIsCapturingPlanTextForName(false);
              setActiveTool('select');
              showToast('Modo captura de texto cancelado.', 'info', 2500);
            } else {
              setIsCapturingPlanTextForName(true);
              setActiveTool('crop');
              showToast('Arrastra un marco sobre el rótulo o texto en el plano general para extraer su nombre.', 'info', 4000);
            }
          }}
          isCapturingPlanText={isCapturingPlanTextForName}
          externalCapturedText={capturedPlanTextForName}
          onClose={() => {
            setShowClassifyModal(false);
            setExtractedCropBase64(null);
            setEditingAnnotation(null);
            setIsCapturingPlanTextForName(false);
            setCapturedPlanTextForName(null);
          }}
          onSaved={(savedAnn) => {
            setManualAnnotations((prev) => {
              const existingIdx = prev.findIndex((a) => a.id === savedAnn.id);
              if (existingIdx >= 0) {
                const next = [...prev];
                next[existingIdx] = savedAnn;
                return next;
              }
              return [savedAnn, ...prev];
            });
            setSelectedEntity({ type: 'manual_annotation', data: savedAnn });
            setShowClassifyModal(false);
            setCapturedPlanTextForName(null);
            showToast(`Selección "${savedAnn.name}" guardada en la lista del proyecto.`, 'success', 3000);
          }}
          onAddToList={(item) => {
            setPendingAnnotations((prev) => [...prev, item]);
            setShowClassifyModal(false);
            setCapturedPlanTextForName(null);
            showToast(`Elemento añadido al lote (${pendingAnnotations.length + 1}).`, 'info', 2500);
          }}
        />
      )}

      {/* Modal 2: Confirmación de Lote y Guardado en Base de Conocimiento / Active Learning */}
      <AnnotationConfirmModal
        isOpen={showConfirmModal}
        pendingItems={pendingAnnotations}
        onClose={() => setShowConfirmModal(false)}
        onRemoveItem={(idx) => {
          setPendingAnnotations((prev) => prev.filter((_, i) => i !== idx));
        }}
        onEditItem={(idx) => {
          const item = pendingAnnotations[idx];
          setExtractedCropBase64(item.crop_image_base64 || null);
          setCropBboxNormalized(item.bbox_normalized);
          setEditingAnnotation(item);
          setPendingAnnotations((prev) => prev.filter((_, i) => i !== idx));
          setShowConfirmModal(false);
          setShowClassifyModal(true);
        }}
        onCompleteSave={() => {
          setPendingAnnotations([]);
          if (selectedSheet) {
            loadSheetData(selectedSheet.id);
          }
          showToast('Lote de anotaciones guardado en Base de Conocimiento.', 'success', 4000);
        }}
      />

      {/* Modal 3: Gestión de Selecciones del Proyecto */}
      <PlanSelectionsModal
        isOpen={showSelectionsModal}
        projectId={selectedProjectId}
        projectName={projects.find((p) => p.id === selectedProjectId)?.name || 'Proyecto Actual'}
        projectCode={projects.find((p) => p.id === selectedProjectId)?.code || 'PRJ'}
        selections={manualAnnotations}
        availableSheets={availableSheets}
        onClose={() => setShowSelectionsModal(false)}
        onEdit={(sel) => {
          setShowSelectionsModal(false);
          setEditingAnnotation(sel);
          setExtractedCropBase64(null);
          setCropBboxNormalized(sel.bbox_normalized);
          setShowClassifyModal(true);
        }}
        onDelete={(selId) => {
          handleDeleteAnnotation(selId);
        }}
        onValidate={async (selId) => {
          const target = manualAnnotations.find((s) => s.id === selId);
          if (!target) return;
          const nextStatus = target.status === 'validada' ? 'draft' : 'validada';
          try {
            await apiService.updateManualAnnotation(selId, { status: nextStatus });
            setManualAnnotations((prev) =>
              prev.map((s) => (s.id === selId ? { ...s, status: nextStatus } : s))
            );
            const projName = projects.find((p) => p.id === selectedProjectId)?.name || 'Proyecto';
            showToast(
              nextStatus === 'validada'
                ? `«${target.name}» validada para Información basada en proyecto ${projName}.`
                : `«${target.name}» regresada a capturada/borrador.`,
              'success',
              3500
            );
          } catch (err) {
            showToast('Error al actualizar estado de la selección.', 'error', 3000);
          }
        }}
        onIncorporateSuccess={(res) => {
          if (selectedSheet) {
            loadSheetData(selectedSheet.id);
          }
          showToast(res.message, 'success', 5000);
        }}
      />
    </div>
  );
};
