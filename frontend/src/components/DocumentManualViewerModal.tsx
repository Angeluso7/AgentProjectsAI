import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  X, ZoomIn, ZoomOut, RotateCcw, Hand, Crop, Image as ImageIcon,
  FileText, Sparkles, BookmarkPlus, Layers, Type, Check,
  Search, Copy, CheckCircle2, Save, AlertCircle, Wand2, Loader2,
  ExternalLink, ArrowRight, Eye, GripHorizontal, Move, Maximize2,
  Edit3, Trash2, Clock, Filter, Table, SquareCheck, RefreshCw,
  BookOpen, FileCheck
} from 'lucide-react';
import * as pdfjsLib from 'pdfjs-dist';
import pdfjsWorker from 'pdfjs-dist/build/pdf.worker.min.js?url';
import { apiService } from '../services/api';
import { ExtractedItem, ExtractedItemType, SourceExtraction, SourceAssetItem } from '../types';

// Configuración del worker de PDF.js
pdfjsLib.GlobalWorkerOptions.workerSrc = pdfjsWorker;

interface DocumentManualViewerModalProps {
  isOpen: boolean;
  sourceId?: string;
  documentTitle: string;
  documentType: string;
  discipline: string;
  authority?: string;
  onClose: () => void;
  onExtractionFinished: (extractionId: string) => void;
}

const BLACK_GRAB_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='%23000000' stroke='%23ffffff' stroke-width='1.2'><path d='M18 11V6a2 2 0 0 0-4 0v4a2 2 0 0 0-4 0v-1a2 2 0 0 0-4 0v6c0 4.4 3.6 8 8 8s8-3.6 8-8v-4a2 2 0 0 0-4 0z'/></svg>") 12 12, grab`;
const BLACK_GRABBING_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='%23000000' stroke='%23ffffff' stroke-width='1.2'><path d='M18 11V9a2 2 0 0 0-4 0v1a2 2 0 0 0-4 0v-1a2 2 0 0 0-4 0v2c0 4.4 3.6 8 8 8s8-3.6 8-8v-1a2 2 0 0 0-4 0z'/></svg>") 12 12, grabbing`;
const RED_CROSSHAIR_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23ef4444' stroke-width='2'><line x1='12' y1='2' x2='12' y2='22'/><line x1='2' y1='12' x2='22' y2='12'/><circle cx='12' cy='12' r='3.5' stroke='%23ef4444' stroke-width='1.5'/></svg>") 12 12, crosshair`;
const BLUE_CROSSHAIR_CURSOR = `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%2338bdf8' stroke-width='2'><line x1='12' y1='2' x2='12' y2='22'/><line x1='2' y1='12' x2='22' y2='12'/><circle cx='12' cy='12' r='3.5' stroke='%2338bdf8' stroke-width='1.5'/></svg>") 12 12, crosshair`;

export const DocumentManualViewerModal: React.FC<DocumentManualViewerModalProps> = ({
  isOpen,
  sourceId,
  documentTitle,
  documentType,
  discipline,
  authority,
  onClose,
  onExtractionFinished,
}) => {
  const [activeSession, setActiveSession] = useState<SourceExtraction | null>(null);
  const [sourceMeta, setSourceMeta] = useState<SourceAssetItem | null>(null);
  const [sessionItems, setSessionItems] = useState<ExtractedItem[]>([]);
  
  // Estado de PDF.js
  const [pdfDoc, setPdfDoc] = useState<pdfjsLib.PDFDocumentProxy | null>(null);
  const [totalPages, setTotalPages] = useState<number>(0);
  const [pdfLoading, setPdfLoading] = useState<boolean>(false);
  const [pdfError, setPdfError] = useState<string | null>(null);

  // Herramientas de Interacción
  const [activeTool, setActiveTool] = useState<'pan' | 'image_crop' | 'text_crop'>('image_crop');
  const [zoom, setZoom] = useState<number>(1.25);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });

  // Selección Rectangular sobre la Página del PDF Real
  const [isDrawingCrop, setIsDrawingCrop] = useState(false);
  const [cropStart, setCropStart] = useState<{ x: number; y: number } | null>(null);
  const [currentCrop, setCurrentCrop] = useState<{ x0: number; y0: number; x1: number; y1: number } | null>(null);
  const [activeCropPage, setActiveCropPage] = useState<number>(1);

  // =========================================================================
  // 1. PANEL FLOTANTE: IMAGEN & ELEMENTOS GRÁFICOS (FONDO SÓLIDO OSCURO)
  // =========================================================================
  const [showImageModal, setShowImageModal] = useState<boolean>(false);
  const [editingImageItemId, setEditingImageItemId] = useState<string | null>(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState<string | null>(null);
  const [imageTitle, setImageTitle] = useState<string>('');
  const [imageDescription, setImageDescription] = useState<string>('');
  const [imageType, setImageType] = useState<string>('imagen');
  const [imageBbox, setImageBbox] = useState<[number, number, number, number]>([0, 0, 0, 0]);
  const [imageStructuredTableText, setImageStructuredTableText] = useState<string>('');

  const [imagePanelPos, setImagePanelPos] = useState<{ x: number; y: number }>({ x: 80, y: 70 });
  const [imagePanelSize, setImagePanelSize] = useState<{ width: number; height: number }>({ width: 540, height: 600 });
  const [isDraggingImage, setIsDraggingImage] = useState(false);
  const [isResizingImage, setIsResizingImage] = useState(false);
  const imageDragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 80, posY: 70 });
  const imageResizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 540, height: 600 });

  // =========================================================================
  // 2. PANEL FLOTANTE: TEXTO / FRAGMENTO SELECCIONADO (FONDO SÓLIDO OSCURO)
  // =========================================================================
  const [showTextModal, setShowTextModal] = useState<boolean>(false);
  const [editingTextItemId, setEditingTextItemId] = useState<string | null>(null);
  const [extractedOcrText, setExtractedOcrText] = useState<string>('');
  const [ocrRunning, setOcrRunning] = useState<boolean>(false);
  const [summarizingRunning, setSummarizingRunning] = useState<boolean>(false);
  const [ruleCode, setRuleCode] = useState<string>('REG-01');
  const [ruleStatement, setRuleStatement] = useState<string>('');
  const [ruleType, setRuleType] = useState<string>('rule');
  const [textBbox, setTextBbox] = useState<[number, number, number, number]>([0, 0, 1, 1]);

  const [textPanelPos, setTextPanelPos] = useState<{ x: number; y: number }>({ x: 120, y: 60 });
  const [textPanelSize, setTextPanelSize] = useState<{ width: number; height: number }>({ width: 580, height: 640 });
  const [isDraggingText, setIsDraggingText] = useState(false);
  const [isResizingText, setIsResizingText] = useState(false);
  const textDragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 120, posY: 60 });
  const textResizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 580, height: 640 });

  // =========================================================================
  // 3. PANEL FLOTANTE: "T OCR GENERAL" (DOCUMENTO Y POR PÁGINA + RESUMEN IA)
  // =========================================================================
  const [showOcrGeneralModal, setShowOcrGeneralModal] = useState<boolean>(false);
  const [ocrMode, setOcrMode] = useState<'document' | 'page'>('document');
  const [ocrSelectedPage, setOcrSelectedPage] = useState<number>(1);
  const [ocrGeneralText, setOcrGeneralText] = useState<string>('');
  const [ocrGeneralPagesData, setOcrGeneralPagesData] = useState<Array<{ page_number: number; text_content: string }>>([]);
  const [ocrGeneralLoading, setOcrGeneralLoading] = useState<boolean>(false);
  
  // Reglas generadas desde OCR General
  const [generatedRulesList, setGeneratedRulesList] = useState<Array<{ code: string; title: string; statement: string; item_type: string; page_number: number }>>([]);
  const [isGeneratingRules, setIsGeneratingRules] = useState<boolean>(false);
  const [rulesImportMessage, setRulesImportMessage] = useState<string | null>(null);

  const [ocrGeneralPos, setOcrGeneralPos] = useState<{ x: number; y: number }>({ x: 90, y: 50 });
  const [ocrGeneralSize, setOcrGeneralSize] = useState<{ width: number; height: number }>({ width: 840, height: 700 });
  const [isDraggingOcrGeneral, setIsDraggingOcrGeneral] = useState(false);
  const [isResizingOcrGeneral, setIsResizingOcrGeneral] = useState(false);
  const ocrGeneralDragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 90, posY: 50 });
  const ocrGeneralResizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 840, height: 700 });

  // =========================================================================
  // 4. PANEL FLOTANTE: "REVISAR Y VALIDAR" (FONDO SÓLIDO OSCURO)
  // =========================================================================
  const [showReviewModal, setShowReviewModal] = useState<boolean>(false);
  const [reviewFilterStatus, setReviewFilterStatus] = useState<string>('all');
  const [reviewSearchTerm, setReviewSearchTerm] = useState<string>('');
  const [isCommitting, setIsCommitting] = useState<boolean>(false);
  const [commitMessage, setCommitMessage] = useState<string | null>(null);

  const [reviewPanelPos, setReviewPanelPos] = useState<{ x: number; y: number }>({ x: 70, y: 50 });
  const [reviewPanelSize, setReviewPanelSize] = useState<{ width: number; height: number }>({ width: 840, height: 680 });
  const [isDraggingReview, setIsDraggingReview] = useState(false);
  const [isResizingReview, setIsResizingReview] = useState(false);
  const reviewDragRef = useRef<{ startX: number; startY: number; posX: number; posY: number }>({ startX: 0, startY: 0, posX: 70, posY: 50 });
  const reviewResizeRef = useRef<{ startX: number; startY: number; width: number; height: number }>({ startX: 0, startY: 0, width: 840, height: 680 });

  const viewerContainerRef = useRef<HTMLDivElement>(null);
  const canvasRefs = useRef<{ [key: number]: HTMLCanvasElement | null }>({});
  const renderTasksRef = useRef<{ [key: number]: any }>({});

  useEffect(() => {
    if (isOpen) {
      loadDocumentAndSession();
    } else {
      if (pdfDoc) {
        pdfDoc.destroy();
        setPdfDoc(null);
      }
    }
  }, [isOpen, sourceId]);

  const loadDocumentAndSession = async () => {
    setPdfLoading(true);
    setPdfError(null);
    try {
      // 1. Crear o reanudar sesión de extracción manual
      const session = await apiService.createManualExtraction({
        title: documentTitle || 'Documento Técnico Asistido',
        document_type: documentType || 'norma',
        discipline: discipline || 'general',
        authority: authority,
        source_asset_id: sourceId,
      });
      setActiveSession(session);
      
      // Cargar items existentes de la sesión
      if (session.id) {
        try {
          const detail = await apiService.getExtractionDetail(session.id);
          if (detail && detail.items) {
            setSessionItems(detail.items);
          }
        } catch (e) {
          setSessionItems([]);
        }
      }

      // 2. Cargar metadata y bytes binarios del archivo PDF original persistido en servidor
      if (sourceId) {
        try {
          const source = await apiService.getSource(sourceId);
          setSourceMeta(source);
        } catch (e) {
          console.warn('Metadata fetch notice:', e);
        }

        const fileUrl = apiService.getSourceFileUrl(sourceId);
        
        // Cargar documento PDF real utilizando pdfjs-dist
        const loadingTask = pdfjsLib.getDocument({
          url: fileUrl,
          cMapUrl: 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/cmaps/',
          cMapPacked: true,
        });

        const loadedPdf = await loadingTask.promise;
        setPdfDoc(loadedPdf);
        setTotalPages(loadedPdf.numPages);
      } else {
        setPdfError('Identificador de documento no disponible.');
      }
    } catch (err: any) {
      console.error('Error cargando documento PDF original:', err);
      setPdfError('No se pudo cargar el archivo PDF original desde el almacenamiento persistente.');
    } finally {
      setPdfLoading(false);
    }
  };

  // Renderizar cada página en su respectivo <canvas> con escala y resolución nítida
  const renderPage = useCallback(async (pageNum: number) => {
    if (!pdfDoc) return;
    const canvas = canvasRefs.current[pageNum];
    if (!canvas) return;

    if (renderTasksRef.current[pageNum]) {
      try {
        renderTasksRef.current[pageNum].cancel();
      } catch (e) {}
    }

    try {
      const page = await pdfDoc.getPage(pageNum);
      const pixelRatio = window.devicePixelRatio || 1;
      const viewport = page.getViewport({ scale: zoom });

      canvas.width = Math.floor(viewport.width * pixelRatio);
      canvas.height = Math.floor(viewport.height * pixelRatio);
      canvas.style.width = `${Math.floor(viewport.width)}px`;
      canvas.style.height = `${Math.floor(viewport.height)}px`;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      ctx.save();
      ctx.scale(pixelRatio, pixelRatio);

      const renderContext = {
        canvasContext: ctx,
        viewport: viewport,
      };

      const renderTask = page.render(renderContext);
      renderTasksRef.current[pageNum] = renderTask;
      await renderTask.promise;
      ctx.restore();
    } catch (err: any) {
      if (err?.name !== 'RenderingCancelledException') {
        console.error(`Error renderizando pág ${pageNum}:`, err);
      }
    }
  }, [pdfDoc, zoom]);

  useEffect(() => {
    if (pdfDoc && totalPages > 0) {
      for (let i = 1; i <= totalPages; i++) {
        renderPage(i);
      }
    }
  }, [pdfDoc, totalPages, zoom, renderPage]);

  // =========================================================
  // GESTIÓN DE DRAG & RESIZE: PANEL IMAGEN
  // =========================================================
  const handleImageHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select') || (e.target as HTMLElement).closest('textarea')) return;
    e.preventDefault();
    setIsDraggingImage(true);
    imageDragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: imagePanelPos.x,
      posY: imagePanelPos.y,
    };
  };

  const handleImageResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingImage(true);
    imageResizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      width: imagePanelSize.width,
      height: imagePanelSize.height,
    };
  };

  useEffect(() => {
    if (!isDraggingImage && !isResizingImage) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingImage) {
        const dx = e.clientX - imageDragRef.current.startX;
        const dy = e.clientY - imageDragRef.current.startY;
        setImagePanelPos({
          x: Math.min(Math.max(10, imageDragRef.current.posX + dx), window.innerWidth - 320),
          y: Math.min(Math.max(10, imageDragRef.current.posY + dy), window.innerHeight - 100),
        });
      } else if (isResizingImage) {
        const dx = e.clientX - imageResizeRef.current.startX;
        const dy = e.clientY - imageResizeRef.current.startY;
        setImagePanelSize({
          width: Math.min(Math.max(420, imageResizeRef.current.width + dx), window.innerWidth - 40),
          height: Math.min(Math.max(460, imageResizeRef.current.height + dy), window.innerHeight - 60),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDraggingImage(false);
      setIsResizingImage(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingImage, isResizingImage]);

  // =========================================================
  // GESTIÓN DE DRAG & RESIZE: PANEL TEXTO (FRAGMENTO)
  // =========================================================
  const handleTextHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select') || (e.target as HTMLElement).closest('textarea')) return;
    e.preventDefault();
    setIsDraggingText(true);
    textDragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: textPanelPos.x,
      posY: textPanelPos.y,
    };
  };

  const handleTextResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingText(true);
    textResizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      width: textPanelSize.width,
      height: textPanelSize.height,
    };
  };

  useEffect(() => {
    if (!isDraggingText && !isResizingText) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingText) {
        const dx = e.clientX - textDragRef.current.startX;
        const dy = e.clientY - textDragRef.current.startY;
        setTextPanelPos({
          x: Math.min(Math.max(10, textDragRef.current.posX + dx), window.innerWidth - 320),
          y: Math.min(Math.max(10, textDragRef.current.posY + dy), window.innerHeight - 100),
        });
      } else if (isResizingText) {
        const dx = e.clientX - textResizeRef.current.startX;
        const dy = e.clientY - textResizeRef.current.startY;
        setTextPanelSize({
          width: Math.min(Math.max(460, textResizeRef.current.width + dx), window.innerWidth - 40),
          height: Math.min(Math.max(480, textResizeRef.current.height + dy), window.innerHeight - 60),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDraggingText(false);
      setIsResizingText(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingText, isResizingText]);

  // =========================================================
  // GESTIÓN DE DRAG & RESIZE: PANEL "T OCR GENERAL"
  // =========================================================
  const handleOcrGeneralHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select') || (e.target as HTMLElement).closest('textarea')) return;
    e.preventDefault();
    setIsDraggingOcrGeneral(true);
    ocrGeneralDragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: ocrGeneralPos.x,
      posY: ocrGeneralPos.y,
    };
  };

  const handleOcrGeneralResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingOcrGeneral(true);
    ocrGeneralResizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      width: ocrGeneralSize.width,
      height: ocrGeneralSize.height,
    };
  };

  useEffect(() => {
    if (!isDraggingOcrGeneral && !isResizingOcrGeneral) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingOcrGeneral) {
        const dx = e.clientX - ocrGeneralDragRef.current.startX;
        const dy = e.clientY - ocrGeneralDragRef.current.startY;
        setOcrGeneralPos({
          x: Math.min(Math.max(10, ocrGeneralDragRef.current.posX + dx), window.innerWidth - 340),
          y: Math.min(Math.max(10, ocrGeneralDragRef.current.posY + dy), window.innerHeight - 100),
        });
      } else if (isResizingOcrGeneral) {
        const dx = e.clientX - ocrGeneralResizeRef.current.startX;
        const dy = e.clientY - ocrGeneralResizeRef.current.startY;
        setOcrGeneralSize({
          width: Math.min(Math.max(560, ocrGeneralResizeRef.current.width + dx), window.innerWidth - 30),
          height: Math.min(Math.max(480, ocrGeneralResizeRef.current.height + dy), window.innerHeight - 40),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDraggingOcrGeneral(false);
      setIsResizingOcrGeneral(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingOcrGeneral, isResizingOcrGeneral]);

  // =========================================================
  // GESTIÓN DE DRAG & RESIZE: PANEL "REVISAR Y VALIDAR"
  // =========================================================
  const handleReviewHeaderMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('button') || (e.target as HTMLElement).closest('input') || (e.target as HTMLElement).closest('select') || (e.target as HTMLElement).closest('textarea')) return;
    e.preventDefault();
    setIsDraggingReview(true);
    reviewDragRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      posX: reviewPanelPos.x,
      posY: reviewPanelPos.y,
    };
  };

  const handleReviewResizeMouseDown = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsResizingReview(true);
    reviewResizeRef.current = {
      startX: e.clientX,
      startY: e.clientY,
      width: reviewPanelSize.width,
      height: reviewPanelSize.height,
    };
  };

  useEffect(() => {
    if (!isDraggingReview && !isResizingReview) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (isDraggingReview) {
        const dx = e.clientX - reviewDragRef.current.startX;
        const dy = e.clientY - reviewDragRef.current.startY;
        setReviewPanelPos({
          x: Math.min(Math.max(10, reviewDragRef.current.posX + dx), window.innerWidth - 340),
          y: Math.min(Math.max(10, reviewDragRef.current.posY + dy), window.innerHeight - 100),
        });
      } else if (isResizingReview) {
        const dx = e.clientX - reviewResizeRef.current.startX;
        const dy = e.clientY - reviewResizeRef.current.startY;
        setReviewPanelSize({
          width: Math.min(Math.max(540, reviewResizeRef.current.width + dx), window.innerWidth - 30),
          height: Math.min(Math.max(480, reviewResizeRef.current.height + dy), window.innerHeight - 40),
        });
      }
    };

    const handleMouseUp = () => {
      setIsDraggingReview(false);
      setIsResizingReview(false);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDraggingReview, isResizingReview]);

  // =========================================================
  // CONTROL DE PAN (ARRASTRE MANUAL ASISTIDO)
  // =========================================================
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (activeTool === 'pan' && e.button === 0) {
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
    setIsPanning(false);
  };

  // =========================================================
  // DIBUJO DE RECORTE SOBRE PÁGINA DEL PDF REAL
  // =========================================================
  const handlePageMouseDown = (e: React.MouseEvent<HTMLDivElement>, pageNum: number) => {
    if (activeTool === 'pan' || e.button !== 0) return;
    e.preventDefault();
    e.stopPropagation();

    const rect = e.currentTarget.getBoundingClientRect();
    const x = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const y = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    setActiveCropPage(pageNum);
    setCropStart({ x, y });
    setCurrentCrop({ x0: x, y0: y, x1: x, y1: y });
    setIsDrawingCrop(true);
  };

  const handlePageMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawingCrop || !cropStart || activeTool === 'pan') return;
    e.preventDefault();
    e.stopPropagation();

    const rect = e.currentTarget.getBoundingClientRect();
    const currentX = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    const currentY = Math.max(0, Math.min(1, (e.clientY - rect.top) / rect.height));

    setCurrentCrop({
      x0: Math.min(cropStart.x, currentX),
      y0: Math.min(cropStart.y, currentY),
      x1: Math.max(cropStart.x, currentX),
      y1: Math.max(cropStart.y, currentY),
    });
  };

  const handlePageMouseUp = async (pageNum: number) => {
    if (!isDrawingCrop || !currentCrop || activeTool === 'pan') {
      setIsDrawingCrop(false);
      return;
    }

    const w = currentCrop.x1 - currentCrop.x0;
    const h = currentCrop.y1 - currentCrop.y0;

    setIsDrawingCrop(false);

    if (w > 0.02 && h > 0.02) {
      const bboxNormalized: [number, number, number, number] = [
        currentCrop.x0,
        currentCrop.y0,
        currentCrop.x1,
        currentCrop.y1
      ];

      // A) FLUJO BOTÓN IMAGEN: Extraer recorte gráfico de alta nitidez
      if (activeTool === 'image_crop') {
        setEditingImageItemId(null);
        setImageBbox(bboxNormalized);
        setImageTitle(`Elemento Gráfico Pág. ${pageNum}`);
        setImageDescription(`Figura, tabla o detalle técnico extraído de la página ${pageNum}.`);
        setImageType('imagen');
        setImageStructuredTableText('');
        setImagePreviewUrl(null);
        setShowImageModal(true);

        generateCanvasCrop(pageNum, bboxNormalized);
      }

      // B) FLUJO BOTÓN TEXTO: Extraer OCR EXCLUSIVAMENTE del fragmento seleccionado
      else if (activeTool === 'text_crop') {
        setEditingTextItemId(null);
        setTextBbox(bboxNormalized);
        const discCode = (discipline || 'GEN').substring(0, 3).toUpperCase();
        setRuleCode(`REG-${discCode}-P${pageNum}`);
        setRuleStatement('');
        setExtractedOcrText('');
        setShowTextModal(true);

        // Extraer OCR ONLY del fragmento seleccionado
        extractTextFromFragment(pageNum, bboxNormalized);
      }
    }

    setCurrentCrop(null);
    setCropStart(null);
  };

  const generateCanvasCrop = (pageNum: number, bbox: [number, number, number, number]) => {
    const canvas = canvasRefs.current[pageNum];
    if (canvas && canvas.width > 0 && canvas.height > 0) {
      try {
        const cropCanvas = document.createElement('canvas');
        const sX = bbox[0] * canvas.width;
        const sY = bbox[1] * canvas.height;
        const sW = (bbox[2] - bbox[0]) * canvas.width;
        const sH = (bbox[3] - bbox[1]) * canvas.height;

        cropCanvas.width = Math.max(1, sW);
        cropCanvas.height = Math.max(1, sH);
        const ctx = cropCanvas.getContext('2d');
        if (ctx) {
          ctx.drawImage(canvas, sX, sY, sW, sH, 0, 0, sW, sH);
          setImagePreviewUrl(cropCanvas.toDataURL('image/png'));
        }
      } catch (e) {
        console.warn('Canvas crop generation:', e);
      }
    }
  };

  // Extraer OCR exclusivamente del fragmento seleccionado (bounding box)
  const extractTextFromFragment = async (pageNum: number, bbox: [number, number, number, number]) => {
    setOcrRunning(true);
    try {
      // 1. Intentar recortar y extraer texto exacto vía backend (PyMuPDF get_textbox sobre rect)
      if (sourceId) {
        const cropRes = await apiService.cropSourcePage(sourceId, pageNum, bbox, 'OCR Fragmento');
        if (cropRes.ocr_text && cropRes.ocr_text.trim()) {
          const fragmentText = cropRes.ocr_text.trim();
          setExtractedOcrText(fragmentText);
          setRuleStatement(`Exigencia técnica [Pág. ${pageNum}]: ${fragmentText.replace(/\n/g, ' ').substring(0, 160)}.`);
          setOcrRunning(false);
          return;
        }
      }

      // 2. Fallback de extracción de fragmento con PDF.js filtrando por coordenadas del bbox
      if (pdfDoc) {
        const page = await pdfDoc.getPage(pageNum);
        const viewport = page.getViewport({ scale: 1.0 });
        const textContent = await page.getTextContent();
        
        const minX = bbox[0] * viewport.width;
        const maxX = bbox[2] * viewport.width;
        const minY = (1 - bbox[3]) * viewport.height;
        const maxY = (1 - bbox[1]) * viewport.height;

        const fragmentItems = textContent.items.filter((item: any) => {
          if (!item.transform) return false;
          const x = item.transform[4];
          const y = item.transform[5];
          return x >= minX - 15 && x <= maxX + 15 && y >= minY - 15 && y <= maxY + 15;
        });

        if (fragmentItems.length > 0) {
          const fragmentText = fragmentItems.map((item: any) => item.str).join(' ').trim();
          if (fragmentText) {
            setExtractedOcrText(fragmentText);
            setRuleStatement(`Exigencia técnica [Pág. ${pageNum}]: ${fragmentText.substring(0, 160)}.`);
            setOcrRunning(false);
            return;
          }
        }
      }

      // 3. Fallback localizado
      const defaultSnippet = `Art. ${pageNum}.1 Disposición técnica seleccionada en el fragmento de la página ${pageNum}.`;
      setExtractedOcrText(defaultSnippet);
      setRuleStatement(`Exigencia técnica [Pág. ${pageNum}]: ${defaultSnippet}`);
    } catch (err) {
      console.warn('Aviso en extracción de fragmento:', err);
      setExtractedOcrText(`Texto extraído del fragmento seleccionado en pág. ${pageNum}.`);
      setRuleStatement('Regla técnica: Verificación del fragmento seleccionado.');
    } finally {
      setOcrRunning(false);
    }
  };

  // Resumir el fragmento seleccionado a regla técnica QA/QC
  const handleSummarizeFragment = async () => {
    if (!extractedOcrText.trim()) return;
    setSummarizingRunning(true);
    try {
      const sumRes = await apiService.summarizeRuleText(
        extractedOcrText,
        discipline,
        documentTitle,
        ruleType
      );
      if (sumRes.rule_code) setRuleCode(sumRes.rule_code);
      if (sumRes.rule_statement) setRuleStatement(sumRes.rule_statement);
    } catch (err) {
      console.warn('Fallback a resumen local de fragmento:', err);
      const firstLine = extractedOcrText.split('.')[0].trim();
      setRuleStatement(`Exigencia técnica: ${firstLine || extractedOcrText.substring(0, 120)}.`);
    } finally {
      setSummarizingRunning(false);
    }
  };

  // Guardar / Actualizar Imagen Aceptada
  const handleAcceptImage = async () => {
    if (!activeSession) return;
    try {
      const isGraphic = ['simbolo', 'foto', 'imagen', 'tabla', 'figura', 'sello', 'firma', 'leyenda', 'vineta', 'otro'].includes(imageType);
      
      const structuredTablePayload = imageType === 'tabla' && imageStructuredTableText ? {
        raw_text: imageStructuredTableText,
        extracted_at: new Date().toISOString()
      } : undefined;

      if (editingImageItemId) {
        // Modo Edición
        const updated = await apiService.updateExtractedItem(activeSession.id, editingImageItemId, {
          item_type: imageType as ExtractedItemType,
          title: imageTitle.trim() || `Elemento Gráfico Pág. ${activeCropPage}`,
          description: imageDescription.trim() || undefined,
          target_destination: isGraphic ? 'knowledge_base' : 'rules_engine',
          review_status: 'editado',
          structured_matrix: structuredTablePayload,
        });

        setSessionItems((prev) => prev.map((it) => (it.id === editingImageItemId ? updated : it)));
      } else {
        // Modo Creación
        const newItem = await apiService.addExtractedItem(activeSession.id, {
          item_type: imageType as ExtractedItemType,
          title: imageTitle.trim() || `Elemento Gráfico Pág. ${activeCropPage}`,
          description: imageDescription.trim() || undefined,
          crop_image_path: imagePreviewUrl || undefined,
          crop_image_base64: imagePreviewUrl || undefined,
          bbox_normalized: imageBbox,
          page_number: activeCropPage,
          target_destination: isGraphic ? 'knowledge_base' : 'rules_engine',
          review_status: 'draft',
          structured_matrix: structuredTablePayload,
        });

        setSessionItems((prev) => [...prev, newItem]);
      }
      setShowImageModal(false);
      setEditingImageItemId(null);
    } catch (err) {
      console.error('Error guardando elemento gráfico:', err);
    }
  };

  // Guardar / Actualizar Texto / Regla Aceptada
  const handleAcceptTextRule = async () => {
    if (!activeSession) return;
    try {
      if (editingTextItemId) {
        // Modo Edición
        const updated = await apiService.updateExtractedItem(activeSession.id, editingTextItemId, {
          item_type: ruleType as ExtractedItemType,
          title: ruleCode ? `${ruleCode}: ${ruleStatement.substring(0, 60)}` : `Regla Pág. ${activeCropPage}`,
          code_or_number: ruleCode || undefined,
          description: ruleStatement || undefined,
          ocr_text: extractedOcrText || undefined,
          content_text: ruleStatement || undefined,
          target_destination: 'rules_engine',
          review_status: 'editado',
        });

        setSessionItems((prev) => prev.map((it) => (it.id === editingTextItemId ? updated : it)));
      } else {
        // Modo Creación
        const newItem = await apiService.addExtractedItem(activeSession.id, {
          item_type: ruleType as ExtractedItemType,
          title: ruleCode ? `${ruleCode}: ${ruleStatement.substring(0, 60)}` : `Regla Pág. ${activeCropPage}`,
          code_or_number: ruleCode || undefined,
          description: ruleStatement || undefined,
          ocr_text: extractedOcrText || undefined,
          content_text: ruleStatement || undefined,
          bbox_normalized: textBbox,
          page_number: activeCropPage,
          target_destination: 'rules_engine',
          review_status: 'draft',
        });

        setSessionItems((prev) => [...prev, newItem]);
      }
      setShowTextModal(false);
      setEditingTextItemId(null);
    } catch (err) {
      console.error('Error guardando regla técnica:', err);
    }
  };

  // Abrir modal de Edición para un Item específico
  const handleEditItem = (item: ExtractedItem) => {
    const isImageCategory = ['simbolo', 'foto', 'imagen', 'tabla', 'figura', 'sello', 'firma', 'leyenda', 'vineta', 'otro', 'image', 'figure', 'symbol', 'table'].includes(item.item_type);

    if (isImageCategory) {
      setEditingImageItemId(item.id);
      setImageTitle(item.title);
      setImageDescription(item.description || '');
      setImageType(item.item_type);
      setActiveCropPage(item.page_number || 1);
      setImagePreviewUrl(item.crop_image_path || null);
      setImageBbox((item.bbox_normalized as [number, number, number, number]) || [0, 0, 1, 1]);
      setImageStructuredTableText(item.structured_matrix?.raw_text || '');
      setShowImageModal(true);
    } else {
      setEditingTextItemId(item.id);
      setRuleCode(item.code_or_number || 'REG-01');
      setRuleStatement(item.description || item.content_text || '');
      setRuleType(item.item_type || 'rule');
      setExtractedOcrText(item.ocr_text || item.content_text || '');
      setActiveCropPage(item.page_number || 1);
      setTextBbox((item.bbox_normalized as [number, number, number, number]) || [0, 0, 1, 1]);
      setShowTextModal(true);
    }
  };

  // Cambiar estado individual de un item
  const handleUpdateItemStatus = async (item: ExtractedItem, newStatus: 'por_confirmar' | 'validada' | 'eliminado') => {
    if (!activeSession) return;
    if (newStatus === 'validada' && (item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule')) {
      alert(`La regla '${item.title}' ya existe en el Motor de Reglas QA/QC y no puede validarse.`);
      return;
    }
    try {
      if (newStatus === 'eliminado') {
        await apiService.deleteExtractedItem(activeSession.id, item.id);
        setSessionItems((prev) => prev.filter((it) => it.id !== item.id));
      } else {
        const updated = await apiService.updateExtractedItem(activeSession.id, item.id, {
          review_status: newStatus
        });
        setSessionItems((prev) => prev.map((it) => (it.id === item.id ? { ...it, review_status: newStatus } : it)));
      }
    } catch (e: any) {
      console.error('Error actualizando estado del elemento:', e);
      alert(e?.response?.data?.detail || 'Error al actualizar estado.');
    }
  };

  // =========================================================
  // GESTIÓN DE OCR GENERAL Y RESUMEN IA A LISTA DE REGLAS
  // =========================================================
  const handleOpenOcrGeneralModal = async () => {
    setShowOcrGeneralModal(true);
    setRulesImportMessage(null);
    if (!ocrGeneralText) {
      fetchGeneralOcrData();
    }
  };

  const fetchGeneralOcrData = async () => {
    setOcrGeneralLoading(true);
    try {
      const res = await apiService.getDocumentOcr({ source_asset_id: sourceId });
      setOcrGeneralPagesData(res.pages || []);
      
      if (ocrMode === 'document') {
        setOcrGeneralText(res.full_text || '');
      } else {
        const pageData = res.pages?.find((p: any) => p.page_number === ocrSelectedPage);
        setOcrGeneralText(pageData?.text_content || `Texto de la página ${ocrSelectedPage} no disponible.`);
      }
    } catch (err) {
      setOcrGeneralText('Error extrayendo OCR del documento.');
    } finally {
      setOcrGeneralLoading(false);
    }
  };

  const handleOcrModeChange = (mode: 'document' | 'page') => {
    setOcrMode(mode);
    if (mode === 'document') {
      const fullText = ocrGeneralPagesData.map((p) => `=== PÁGINA ${p.page_number} ===\n${p.text_content}`).join('\n\n');
      setOcrGeneralText(fullText);
    } else {
      const pageData = ocrGeneralPagesData.find((p) => p.page_number === ocrSelectedPage);
      setOcrGeneralText(pageData?.text_content || `Texto de la página ${ocrSelectedPage} no disponible.`);
    }
  };

  const handleOcrPageSelectChange = (pageNum: number) => {
    setOcrSelectedPage(pageNum);
    const pageData = ocrGeneralPagesData.find((p) => p.page_number === pageNum);
    setOcrGeneralText(pageData?.text_content || `Texto de la página ${pageNum} no disponible.`);
  };

  // Generar Lista de Reglas estructuradas desde el texto OCR
  const handleGenerateRulesFromOcr = async () => {
    if (!ocrGeneralText.trim()) return;
    setIsGeneratingRules(true);
    setRulesImportMessage(null);
    try {
      const res = await apiService.generateRulesFromOcr({
        ocr_text: ocrGeneralText,
        discipline: discipline || 'Arquitectura',
        document_title: documentTitle,
        page_number: ocrMode === 'page' ? ocrSelectedPage : undefined
      });
      setGeneratedRulesList(res.rules || []);
    } catch (err: any) {
      console.error('Error generando reglas con IA:', err);
      alert('No se pudo generar la lista de reglas con IA.');
    } finally {
      setIsGeneratingRules(false);
    }
  };

  const handleDeleteGeneratedRule = (idx: number) => {
    setGeneratedRulesList((prev) => prev.filter((_, i) => i !== idx));
  };

  // Incorporar Reglas Generadas al Panel Lateral
  const handleImportGeneratedRulesToPanel = async () => {
    if (!activeSession || generatedRulesList.length === 0) return;
    try {
      const createdItems: ExtractedItem[] = [];
      for (const rule of generatedRulesList) {
        const item = await apiService.addExtractedItem(activeSession.id, {
          item_type: 'rule',
          title: `${rule.code}: ${rule.title}`,
          code_or_number: rule.code,
          description: rule.statement,
          content_text: rule.statement,
          ocr_text: rule.statement,
          page_number: rule.page_number || (ocrMode === 'page' ? ocrSelectedPage : 1),
          target_destination: 'rules_engine',
          review_status: 'draft',
        });
        createdItems.push(item);
      }

      setSessionItems((prev) => [...prev, ...createdItems]);
      setRulesImportMessage(`¡Se incorporaron exitosamente ${createdItems.length} reglas al panel derecho!`);
      setTimeout(() => {
        setGeneratedRulesList([]);
        setShowOcrGeneralModal(false);
        setRulesImportMessage(null);
      }, 1200);
    } catch (err) {
      console.error('Error importando reglas al panel:', err);
    }
  };

  // Confirmar y Ejecutar Commit Final de Elementos Validados
  const handleCommitValidatedItems = async () => {
    if (!activeSession) return;
    setIsCommitting(true);
    setCommitMessage(null);
    try {
      const validatedItems = sessionItems.filter((it) => it.review_status === 'validada' || it.review_status === 'accepted');
      if (validatedItems.length === 0) {
        alert('No hay elementos marcados como «Validada». Marca al menos un elemento como «Validada» para incorporarlo.');
        setIsCommitting(false);
        return;
      }

      const validatedIds = validatedItems.map((it) => it.id);
      const res = await apiService.commitExtractionToRules(activeSession.id, {
        approved_item_ids: validatedIds,
        target_rule_document_title: documentTitle,
        target_rule_document_description: `Documento normativo/fuente procesada: ${documentTitle} (${discipline}).`
      });

      setCommitMessage(res.message);
      
      setTimeout(() => {
        setShowReviewModal(false);
        onExtractionFinished(activeSession.id);
      }, 1400);

    } catch (err: any) {
      console.error('Error en commit:', err);
      alert(`Error al incorporar: ${err?.response?.data?.detail || err?.message || 'Error desconocido'}`);
    } finally {
      setIsCommitting(false);
    }
  };

  const getItemTypeBadge = (type: string) => {
    switch (type) {
      case 'simbolo': return <span className="px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800 text-[10px] font-bold">🔘 Símbolo</span>;
      case 'tabla': return <span className="px-1.5 py-0.5 rounded bg-cyan-950 text-cyan-300 border border-cyan-800 text-[10px] font-bold">📊 Tabla</span>;
      case 'figura': return <span className="px-1.5 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800 text-[10px] font-bold">📐 Figura</span>;
      case 'foto': return <span className="px-1.5 py-0.5 rounded bg-pink-950 text-pink-300 border border-pink-800 text-[10px] font-bold">📷 Foto</span>;
      case 'imagen': return <span className="px-1.5 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800 text-[10px] font-bold">🖼️ Imagen</span>;
      case 'sello': return <span className="px-1.5 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800 text-[10px] font-bold">🔖 Sello</span>;
      case 'firma': return <span className="px-1.5 py-0.5 rounded bg-teal-950 text-teal-300 border border-teal-800 text-[10px] font-bold">✍️ Firma</span>;
      case 'leyenda': return <span className="px-1.5 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 text-[10px] font-bold">📑 Leyenda</span>;
      case 'vineta': return <span className="px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800 text-[10px] font-bold">🏷️ Viñeta</span>;
      case 'rule':
      case 'regla': return <span className="px-1.5 py-0.5 rounded bg-sky-950 text-sky-300 border border-sky-800 text-[10px] font-bold">⚖️ Regla QA/QC</span>;
      case 'article': return <span className="px-1.5 py-0.5 rounded bg-violet-950 text-violet-300 border border-violet-800 text-[10px] font-bold">📜 Artículo</span>;
      default: return <span className="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-bold">{type}</span>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'validada':
      case 'accepted':
        return <span className="px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-300 border border-emerald-700 text-[10px] font-bold flex items-center gap-1">🟢 Validada</span>;
      case 'por_confirmar':
      case 'to_confirm':
        return <span className="px-2 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-700 text-[10px] font-bold flex items-center gap-1">🟡 Por confirmar</span>;
      case 'editado':
        return <span className="px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700 text-[10px] font-bold flex items-center gap-1">🔵 Editado</span>;
      case 'eliminado':
      case 'rejected':
        return <span className="px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-700 text-[10px] font-bold flex items-center gap-1">🔴 Eliminado</span>;
      default:
        return <span className="px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 text-[10px] font-medium flex items-center gap-1">⚪ Capturado</span>;
    }
  };

  const filteredReviewItems = sessionItems.filter((it) => {
    if (reviewFilterStatus !== 'all') {
      if (reviewFilterStatus === 'validada' && it.review_status !== 'validada' && it.review_status !== 'accepted') return false;
      if (reviewFilterStatus === 'por_confirmar' && it.review_status !== 'por_confirmar' && it.review_status !== 'to_confirm' && it.review_status !== 'draft') return false;
      if (reviewFilterStatus === 'editado' && it.review_status !== 'editado') return false;
    }
    if (reviewSearchTerm.trim()) {
      const q = reviewSearchTerm.toLowerCase();
      const matchTitle = it.title.toLowerCase().includes(q);
      const matchCode = it.code_or_number?.toLowerCase().includes(q);
      const matchDesc = it.description?.toLowerCase().includes(q);
      return matchTitle || matchCode || matchDesc;
    }
    return true;
  });

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex flex-col bg-slate-950 text-slate-100 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      {/* ========================================================= */}
      {/* BARRA SUPERIOR DE CONTROL: VISOR ORIGINAL (PDF REAL)      */}
      {/* ========================================================= */}
      <div className="px-5 py-3 border-b border-slate-800 bg-slate-900 flex items-center justify-between gap-4 flex-wrap z-30">
        
        {/* Identificación del Documento Original */}
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-xl bg-sky-500/10 text-sky-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-slate-100">
                {documentTitle}
              </h2>
              <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-emerald-950 text-emerald-400 border border-emerald-800">
                Documento Original Embebido • PDF Real
              </span>
            </div>
            <p className="text-[11px] text-slate-400">
              {totalPages > 0 ? `${totalPages} páginas` : 'Cargando'} • Scroll vertical continuo • Paneles flotantes sólidos oscuros
            </p>
          </div>
        </div>

        {/* Herramientas de Interacción: Pan, Recorte, Zoom Exclusivo por Botones */}
        <div className="flex items-center gap-3 flex-wrap">
          
          {/* Herramientas Principales */}
          <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setActiveTool('image_crop')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                activeTool === 'image_crop'
                  ? 'bg-rose-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
              title="Seleccionar fragmento de imagen, figura o tabla"
            >
              <Crop className="w-3.5 h-3.5" />
              <span>Recortar Imagen</span>
            </button>

            <button
              onClick={() => setActiveTool('text_crop')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                activeTool === 'text_crop'
                  ? 'bg-sky-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
              title="Seleccionar fragmento de texto para OCR y resumen"
            >
              <Type className="w-3.5 h-3.5" />
              <span>Seleccionar Texto</span>
            </button>

            <button
              onClick={() => setActiveTool('pan')}
              className={`px-3 py-1.5 text-xs font-semibold rounded-lg flex items-center gap-1.5 transition-all ${
                activeTool === 'pan'
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
              }`}
              title="Mover o arrastrar el documento (Pan)"
            >
              <Hand className="w-3.5 h-3.5" />
              <span>Pan</span>
            </button>
          </div>

          <div className="h-6 w-[1px] bg-slate-800" />

          {/* Controles de Zoom Exclusivos por Botones */}
          <div className="flex items-center gap-1 bg-slate-950 px-2 py-1 rounded-xl border border-slate-800">
            <button
              onClick={() => setZoom((prev) => Math.max(Number((prev - 0.25).toFixed(2)), 0.5))}
              className="p-1.5 text-slate-300 hover:text-white rounded hover:bg-slate-800 transition-colors"
              title="Alejar (Zoom Out -25%)"
            >
              <ZoomOut className="w-4 h-4" />
            </button>

            {/* Presets Rápidos de Zoom */}
            <select
              value={zoom}
              onChange={(e) => setZoom(parseFloat(e.target.value))}
              className="bg-slate-900 text-xs font-mono font-bold text-slate-300 px-2 py-0.5 rounded border border-slate-700 outline-none cursor-pointer hover:border-slate-500"
              title="Escala de visualización"
            >
              <option value="0.5">50%</option>
              <option value="0.75">75%</option>
              <option value="1">100%</option>
              <option value="1.25">125% (Óptimo)</option>
              <option value="1.5">150%</option>
              <option value="1.75">175%</option>
              <option value="2">200%</option>
              <option value="2.5">250%</option>
            </select>

            <button
              onClick={() => setZoom((prev) => Math.min(Number((prev + 0.25).toFixed(2)), 3.0))}
              className="p-1.5 text-slate-300 hover:text-white rounded hover:bg-slate-800 transition-colors"
              title="Acercar (Zoom In +25%)"
            >
              <ZoomIn className="w-4 h-4" />
            </button>

            <button
              onClick={() => {
                setZoom(1.25);
                setPan({ x: 0, y: 0 });
                if (viewerContainerRef.current) viewerContainerRef.current.scrollTop = 0;
              }}
              className="p-1.5 text-slate-300 hover:text-white rounded hover:bg-slate-800 transition-colors ml-1"
              title="Restablecer Escala (125%) y Posición"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          </div>

          <div className="h-6 w-[1px] bg-slate-800" />

          {/* BOTÓN REQUERIDO 4: "T OCR GENERAL" */}
          <button
            onClick={handleOpenOcrGeneralModal}
            className="px-3.5 py-1.5 text-xs font-bold text-teal-300 bg-teal-950 hover:bg-teal-900 border border-teal-700 rounded-xl transition-all flex items-center gap-1.5 shadow"
            title="Abrir ventana de OCR General (Documento completo o Por página) y Resumen con IA"
          >
            <BookOpen className="w-3.5 h-3.5 text-teal-400" />
            <span>T OCR General</span>
          </button>

          {/* Botón Cerrar */}
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-xl"
            title="Cerrar visor"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* CUERPO PRINCIPAL: VISOR VECTORIAL REAL + PANEL DERECHO   */}
      {/* ========================================================= */}
      <div className="relative flex-1 overflow-hidden flex">
        
        {/* ========================================================= */}
        {/* A) ÁREA PRINCIPAL: LIENZO CONTINUO DE PÁGINAS PDF REALES  */}
        {/* ========================================================= */}
        <div
          ref={viewerContainerRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          style={{
            cursor: activeTool === 'pan'
              ? (isPanning ? BLACK_GRABBING_CURSOR : BLACK_GRAB_CURSOR)
              : activeTool === 'image_crop'
                ? RED_CROSSHAIR_CURSOR
                : BLUE_CROSSHAIR_CURSOR,
          }}
          className="flex-1 overflow-y-auto overflow-x-auto p-8 flex flex-col items-center gap-8 bg-slate-950 select-none scroll-smooth"
        >
          {pdfLoading ? (
            <div className="flex flex-col items-center justify-center h-96 gap-3 text-slate-400">
              <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
              <p className="text-sm font-medium">Cargando y decodificando documento original...</p>
            </div>
          ) : pdfError ? (
            <div className="flex flex-col items-center justify-center h-96 gap-3 text-rose-400 max-w-md text-center p-6 bg-slate-900 border border-slate-800 rounded-2xl">
              <AlertCircle className="w-8 h-8" />
              <p className="text-sm font-semibold">{pdfError}</p>
              <p className="text-xs text-slate-500">Verifica que el archivo haya sido guardado en la carpeta persistente del sistema.</p>
            </div>
          ) : (
            <div
              style={{
                transform: `translate(${pan.x}px, ${pan.y}px)`,
                transformOrigin: 'top center',
                transition: isPanning ? 'none' : 'transform 0.1s ease-out',
              }}
              className="flex flex-col items-center gap-8 py-4"
            >
              {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((pageNum) => (
                <div
                  key={pageNum}
                  onMouseDown={(e) => handlePageMouseDown(e, pageNum)}
                  onMouseMove={handlePageMouseMove}
                  onMouseUp={() => handlePageMouseUp(pageNum)}
                  className="relative bg-white text-slate-900 border border-slate-700/80 rounded-xl shadow-2xl overflow-hidden group"
                >
                  {/* Canvas de PDF.js para renderizado vectorial exacto */}
                  <canvas
                    ref={(el) => (canvasRefs.current[pageNum] = el)}
                    className="block"
                  />

                  {/* Insignia Flotante de Número de Página */}
                  <div className="absolute top-3 right-3 bg-slate-900 text-slate-300 text-[10px] font-mono font-bold px-2 py-1 rounded-md border border-slate-700 opacity-60 group-hover:opacity-100 transition-opacity pointer-events-none">
                    Pág. {pageNum} de {totalPages}
                  </div>

                  {/* Rectángulo de Selección Dinámico Mientras se Dibuja */}
                  {isDrawingCrop && currentCrop && activeCropPage === pageNum && (
                    <div
                      style={{
                        position: 'absolute',
                        left: `${currentCrop.x0 * 100}%`,
                        top: `${currentCrop.y0 * 100}%`,
                        width: `${(currentCrop.x1 - currentCrop.x0) * 100}%`,
                        height: `${(currentCrop.y1 - currentCrop.y0) * 100}%`,
                        border: activeTool === 'image_crop' ? '2px dashed #ef4444' : '2px dashed #38bdf8',
                        background: activeTool === 'image_crop' ? 'rgba(239, 68, 68, 0.16)' : 'rgba(56, 189, 248, 0.16)',
                        pointerEvents: 'none',
                        zIndex: 60,
                        borderRadius: '2px',
                      }}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* ========================================================================= */}
        {/* B) PANEL LATERAL VERTICAL DERECHO: BOTONES & LISTA DE CAPTURADOS EN VIVO  */}
        {/* ========================================================================= */}
        <div className="w-80 border-l border-slate-800 bg-slate-900 flex flex-col justify-between shadow-2xl z-20">
          <div className="p-4 space-y-4 flex-1 overflow-y-auto">
            
            <div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-teal-400" />
                <span>Extracción Estructurada</span>
              </h3>
              <p className="text-[11px] text-slate-400 mt-1">
                Captura elementos gráficos, fragmentos de texto y reglas OCR.
              </p>
            </div>

            <div className="h-[1px] bg-slate-800" />

            {/* BOTÓN PRINCIPAL 1: IMAGEN */}
            <button
              onClick={() => {
                setActiveTool('image_crop');
                setEditingImageItemId(null);
                setShowImageModal(true);
                setImageTitle(`Elemento Gráfico Pág. ${activeCropPage}`);
                setImageDescription(`Figura, tabla o detalle técnico extraído de la página ${activeCropPage}.`);
                setImageType('imagen');
                setImageStructuredTableText('');
                generateCanvasCrop(activeCropPage, [0.1, 0.1, 0.9, 0.9]);
              }}
              className={`w-full p-3 rounded-xl border text-left transition-all flex flex-col gap-1.5 shadow-sm ${
                activeTool === 'image_crop'
                  ? 'bg-rose-950 border-rose-600 text-rose-200 ring-1 ring-rose-500'
                  : 'bg-slate-950 hover:bg-slate-800 border-slate-800 text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg ${activeTool === 'image_crop' ? 'bg-rose-900 text-rose-300' : 'bg-slate-800 text-slate-400'}`}>
                    <ImageIcon className="w-4 h-4" />
                  </div>
                  <span className="font-bold text-xs">Imagen</span>
                </div>
                {activeTool === 'image_crop' && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-rose-900 text-rose-300 border border-rose-700">
                    Activo
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 leading-snug">
                Captura símbolos, figuras, fotos, tablas, sellos o firmas.
              </p>
            </button>

            {/* BOTÓN PRINCIPAL 2: TEXTO */}
            <button
              onClick={() => {
                setActiveTool('text_crop');
                setEditingTextItemId(null);
                setShowTextModal(true);
                const discCode = (discipline || 'GEN').substring(0, 3).toUpperCase();
                setRuleCode(`REG-${discCode}-P${activeCropPage}`);
                extractTextFromFragment(activeCropPage, [0.1, 0.1, 0.9, 0.3]);
              }}
              className={`w-full p-3 rounded-xl border text-left transition-all flex flex-col gap-1.5 shadow-sm ${
                activeTool === 'text_crop'
                  ? 'bg-sky-950 border-sky-600 text-sky-200 ring-1 ring-sky-500'
                  : 'bg-slate-950 hover:bg-slate-800 border-slate-800 text-slate-200'
              }`}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className={`p-1.5 rounded-lg ${activeTool === 'text_crop' ? 'bg-sky-900 text-sky-300' : 'bg-slate-800 text-slate-400'}`}>
                    <FileText className="w-4 h-4" />
                  </div>
                  <span className="font-bold text-xs">Texto</span>
                </div>
                {activeTool === 'text_crop' && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-sky-900 text-sky-300 border border-sky-700">
                    Activo
                  </span>
                )}
              </div>
              <p className="text-[11px] text-slate-400 leading-snug">
                Selecciona un fragmento del documento para OCR y resumen de regla.
              </p>
            </button>

            <div className="h-[1px] bg-slate-800" />

            {/* LISTA DE ELEMENTOS CAPTURADOS EN VIVO */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                  <Layers className="w-3.5 h-3.5 text-slate-400" />
                  <span>Capturados en Sesión ({sessionItems.length})</span>
                </span>
                <span className="text-[10px] text-slate-400">
                  {sessionItems.filter((i) => i.review_status === 'validada' || i.review_status === 'accepted').length} listos
                </span>
              </div>

              {sessionItems.length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-center text-[11px] text-slate-500 space-y-1">
                  <p className="font-semibold text-slate-400">Sin capturas todavía</p>
                  <p>Usa «Imagen», «Texto» o «T OCR General» para registrar elementos.</p>
                </div>
              ) : (
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                  {sessionItems.map((item) => (
                    <div
                      key={item.id}
                      className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs flex flex-col gap-1.5 group hover:border-slate-700 transition-all"
                    >
                      <div className="flex items-center justify-between gap-1">
                        <div className="flex items-center gap-1.5 truncate">
                          {getItemTypeBadge(item.item_type)}
                          <span className="text-[10px] text-slate-400 font-mono">Pág. {item.page_number}</span>
                        </div>
                        {getStatusBadge(item.review_status)}
                      </div>

                      <div className="text-xs font-semibold text-slate-200 truncate" title={item.title}>
                        {item.title}
                      </div>

                      {item.description && (
                        <p className="text-[11px] text-slate-400 line-clamp-2">
                          {item.description}
                        </p>
                      )}

                      <div className="flex items-center justify-between pt-1 border-t border-slate-900 mt-0.5">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleEditItem(item)}
                            className="p-1 text-slate-400 hover:text-sky-400 hover:bg-slate-900 rounded"
                            title="Editar elemento"
                          >
                            <Edit3 className="w-3 h-3" />
                          </button>
                          <button
                            onClick={() => handleUpdateItemStatus(item, 'eliminado')}
                            className="p-1 text-slate-400 hover:text-rose-400 hover:bg-slate-900 rounded"
                            title="Eliminar elemento"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>

                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleUpdateItemStatus(item, item.review_status === 'validada' ? 'por_confirmar' : 'validada')}
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold border transition-all ${
                              item.review_status === 'validada' || item.review_status === 'accepted'
                                ? 'bg-emerald-950 text-emerald-300 border-emerald-800'
                                : 'bg-slate-900 text-slate-400 border-slate-800 hover:text-slate-200'
                            }`}
                          >
                            {item.review_status === 'validada' || item.review_status === 'accepted' ? 'Validada ✓' : 'Marcar Validada'}
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Footer del Panel Lateral con Botón "Revisar y Validar" */}
          <div className="p-4 border-t border-slate-800 bg-slate-950">
            {activeSession && (
              <button
                onClick={() => setShowReviewModal(true)}
                disabled={sessionItems.length === 0}
                className="w-full py-2.5 px-3 text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow flex items-center justify-center gap-2"
              >
                <SquareCheck className="w-4 h-4" />
                <span>Revisar y Validar ({sessionItems.length})</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* ========================================================================= */}
      {/* C) PANEL FLOTANTE: "IMAGEN" (FONDO SÓLIDO OSCURO, 100% OPACO, NO MODAL)   */}
      {/* ========================================================================= */}
      {showImageModal && (
        <div
          style={{
            position: 'fixed',
            left: `${imagePanelPos.x}px`,
            top: `${imagePanelPos.y}px`,
            width: `${imagePanelSize.width}px`,
            height: `${imagePanelSize.height}px`,
            zIndex: 60,
            maxWidth: 'calc(100vw - 30px)',
            maxHeight: 'calc(100vh - 40px)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '1rem',
            boxShadow: '0 25px 60px -12px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
            userSelect: isDraggingImage || isResizingImage ? 'none' : 'auto',
          }}
          className="overflow-hidden animate-in fade-in duration-150"
        >
          {/* Header Arrastrable (Drag Handle) */}
          <div
            onMouseDown={handleImageHeaderMouseDown}
            style={{
              cursor: isDraggingImage ? 'grabbing' : 'grab',
              backgroundColor: '#020617',
              borderBottom: '1px solid #1e293b',
            }}
            className="px-4 py-3 flex items-center justify-between select-none"
          >
            <div className="flex items-center gap-2 text-rose-400">
              <GripHorizontal className="w-4 h-4 text-slate-500" />
              <div className="p-1 rounded bg-rose-950 text-rose-400 border border-rose-800">
                <ImageIcon className="w-4 h-4" />
              </div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">
                {editingImageItemId ? 'Editar Elemento Gráfico' : `Capturar Elemento Gráfico (Pág. ${activeCropPage})`}
              </h3>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Arrastrable</span>
              <button
                onClick={() => {
                  setShowImageModal(false);
                  setEditingImageItemId(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg"
                title="Cerrar panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Contenido Flexible y Sólido */}
          <div style={{ backgroundColor: '#0f172a' }} className="p-4 space-y-3.5 text-xs flex-1 overflow-y-auto">
            
            {/* 1. Preview de la imagen recortada del PDF real */}
            <div className="flex flex-col">
              <div className="flex items-center justify-between mb-1">
                <label className="font-semibold text-slate-300">
                  Vista Previa de la Región Recortada
                </label>
                {totalPages > 1 && (
                  <div className="flex items-center gap-1 text-[11px] text-slate-400">
                    <span>Pág:</span>
                    <select
                      value={activeCropPage}
                      onChange={(e) => {
                        const p = parseInt(e.target.value);
                        setActiveCropPage(p);
                        generateCanvasCrop(p, [0.1, 0.1, 0.9, 0.9]);
                      }}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="text-slate-200 font-semibold px-1.5 py-0.5 rounded border"
                    >
                      {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
              <div
                style={{
                  height: `${Math.max(130, Math.floor(imagePanelSize.height * 0.28))}px`,
                  backgroundColor: '#020617',
                  border: '1px solid #1e293b',
                }}
                className="w-full rounded-xl flex items-center justify-center overflow-hidden p-2"
              >
                {imagePreviewUrl ? (
                  <img
                    src={imagePreviewUrl.startsWith('http') || imagePreviewUrl.startsWith('data:') ? imagePreviewUrl : (imagePreviewUrl.startsWith('/') ? imagePreviewUrl : `/${imagePreviewUrl}`)}
                    alt="Recorte seleccionado"
                    className="max-h-full max-w-full object-contain rounded shadow"
                  />
                ) : (
                  <span className="text-slate-500">Recorte de página {activeCropPage}</span>
                )}
              </div>
            </div>

            {/* 2. Renglón: Nombre o Título */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">
                Nombre o Título (Identificador del elemento)
              </label>
              <input
                type="text"
                value={imageTitle}
                onChange={(e) => setImageTitle(e.target.value)}
                placeholder="Ej: Detalle de Ancho de Pasillo / Tabla 2.A"
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-rose-500"
              />
            </div>

            {/* 3. Renglón: Descripción */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">
                Descripción
              </label>
              <textarea
                rows={2}
                value={imageDescription}
                onChange={(e) => setImageDescription(e.target.value)}
                placeholder="Descripción técnica, función o notas del elemento..."
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-rose-500"
              />
            </div>

            {/* 4. Desplegable: Tipo de elemento (10 Opciones Exactas) */}
            <div>
              <label className="block font-semibold text-slate-300 mb-1">
                Tipo de Elemento (Clasificación para Base de Apoyo y Reutilización)
              </label>
              <select
                value={imageType}
                onChange={(e) => setImageType(e.target.value)}
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-rose-500 font-medium"
              >
                <option value="simbolo">🔘 símbolo</option>
                <option value="foto">📷 foto</option>
                <option value="imagen">🖼️ imagen</option>
                <option value="tabla">📊 tabla</option>
                <option value="figura">📐 figura</option>
                <option value="sello">🔖 sello</option>
                <option value="firma">✍️ firma</option>
                <option value="leyenda">📑 leyenda</option>
                <option value="vineta">🏷️ viñeta</option>
                <option value="otro">📦 otro</option>
              </select>
            </div>

            {/* Estructura adicional si es Tabla */}
            {imageType === 'tabla' && (
              <div style={{ backgroundColor: '#020617', borderColor: '#083344' }} className="p-3 border rounded-xl space-y-1.5">
                <label className="block font-semibold text-cyan-300">
                  Estructura Tabular / Datos de Matriz (Opcional)
                </label>
                <textarea
                  rows={2}
                  value={imageStructuredTableText}
                  onChange={(e) => setImageStructuredTableText(e.target.value)}
                  placeholder="Valores de filas y columnas de la tabla para apoyo analítico..."
                  style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                  className="w-full px-2.5 py-1 rounded-lg border text-slate-200 text-xs focus:outline-none focus:border-cyan-500 font-mono"
                />
              </div>
            )}
          </div>

          {/* Footer */}
          <div
            style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
            className="px-4 py-3 flex items-center justify-between relative"
          >
            <button
              onClick={() => {
                setShowImageModal(false);
                setEditingImageItemId(null);
              }}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
            >
              Cancelar
            </button>
            <button
              onClick={handleAcceptImage}
              className="px-4 py-1.5 text-xs font-bold text-white bg-rose-600 hover:bg-rose-500 rounded-xl transition-all shadow flex items-center gap-1.5"
            >
              <Check className="w-4 h-4" />
              <span>{editingImageItemId ? 'Actualizar Elemento' : 'Aceptar e Incorporar'}</span>
            </button>

            {/* Handle Resize */}
            <div
              onMouseDown={handleImageResizeMouseDown}
              style={{ cursor: 'nwse-resize' }}
              className="absolute bottom-1 right-1 p-1 text-slate-500 hover:text-slate-300 transition-colors select-none"
              title="Arrastrar para redimensionar panel"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2L2 8M8 5L5 8M8 8L8 8" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* D) PANEL FLOTANTE: "TEXTO" (SOLO DEL FRAGMENTO SELECCIONADO, SÓLIDO OSCURO) */}
      {/* ========================================================================= */}
      {showTextModal && (
        <div
          style={{
            position: 'fixed',
            left: `${textPanelPos.x}px`,
            top: `${textPanelPos.y}px`,
            width: `${textPanelSize.width}px`,
            height: `${textPanelSize.height}px`,
            zIndex: 60,
            maxWidth: 'calc(100vw - 30px)',
            maxHeight: 'calc(100vh - 40px)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '1rem',
            boxShadow: '0 25px 60px -12px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
            userSelect: isDraggingText || isResizingText ? 'none' : 'auto',
          }}
          className="overflow-hidden animate-in fade-in duration-150"
        >
          {/* Header Arrastrable (Drag Handle) */}
          <div
            onMouseDown={handleTextHeaderMouseDown}
            style={{
              cursor: isDraggingText ? 'grabbing' : 'grab',
              backgroundColor: '#020617',
              borderBottom: '1px solid #1e293b',
            }}
            className="px-4 py-3 flex items-center justify-between select-none"
          >
            <div className="flex items-center gap-2 text-sky-400">
              <GripHorizontal className="w-4 h-4 text-slate-500" />
              <div className="p-1 rounded bg-sky-950 text-sky-400 border border-sky-800">
                <FileText className="w-4 h-4" />
              </div>
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100">
                {editingTextItemId ? 'Editar Texto / Regla de Fragmento' : `OCR y Resumen de Fragmento (Pág. ${activeCropPage})`}
              </h3>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Arrastrable</span>
              <button
                onClick={() => {
                  setShowTextModal(false);
                  setEditingTextItemId(null);
                }}
                className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg"
                title="Cerrar panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Contenido Flexible y Sólido */}
          <div style={{ backgroundColor: '#0f172a' }} className="p-4 space-y-3 text-xs flex-1 overflow-y-auto flex flex-col">
            
            {/* 1. SECCIÓN SUPERIOR: TEXTO EXTRAÍDO EXCLUSIVAMENTE DEL FRAGMENTO */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-bold text-sky-300">Texto Extraído del Fragmento Seleccionado</span>
                <span className="text-[10px] text-slate-400 font-mono">Pág. {activeCropPage}</span>
              </div>

              {/* Botón OCR Fragmento */}
              <button
                type="button"
                onClick={() => extractTextFromFragment(activeCropPage, textBbox)}
                disabled={ocrRunning}
                className="px-2.5 py-1 bg-sky-950 text-sky-300 border border-sky-700 hover:bg-sky-900 rounded-lg flex items-center gap-1.5 transition-colors font-semibold"
              >
                {ocrRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Type className="w-3.5 h-3.5" />}
                <span>Reejecutar OCR Fragmento</span>
              </button>
            </div>

            {/* Área de Texto Editable del Fragmento */}
            <div className="flex-1 min-h-[90px] flex flex-col">
              <textarea
                value={extractedOcrText}
                onChange={(e) => setExtractedOcrText(e.target.value)}
                placeholder="Texto extraído exclusivamente del fragmento recortado..."
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="w-full flex-1 min-h-[90px] p-2.5 rounded-xl border text-slate-100 font-mono text-xs focus:outline-none focus:border-sky-500 leading-relaxed resize-none"
              />
            </div>

            {/* 2. BOTÓN INTERMEDIO: RESUMIR FRAGMENTO */}
            <div className="flex justify-end pt-0.5">
              <button
                type="button"
                onClick={handleSummarizeFragment}
                disabled={summarizingRunning || !extractedOcrText.trim()}
                className="px-3.5 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-xl font-bold flex items-center gap-1.5 shadow transition-all disabled:opacity-50"
              >
                {summarizingRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Wand2 className="w-3.5 h-3.5" />}
                <span>Resumir Fragmento a Regla QA/QC</span>
              </button>
            </div>

            {/* 3. SECCIÓN INFERIOR: RESUMEN / ENUNCIADO DE LA REGLA DEL FRAGMENTO */}
            <div className="space-y-2.5 pt-2 border-t border-slate-800">
              <div className="grid grid-cols-3 gap-2.5">
                <div className="col-span-1">
                  <label className="block font-semibold text-slate-300 mb-1">
                    Código / Identificador
                  </label>
                  <input
                    type="text"
                    value={ruleCode}
                    onChange={(e) => setRuleCode(e.target.value)}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="w-full px-2.5 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500 font-mono"
                  />
                </div>

                <div className="col-span-2">
                  <label className="block font-semibold text-slate-300 mb-1">
                    Tipo de Regla
                  </label>
                  <select
                    value={ruleType}
                    onChange={(e) => setRuleType(e.target.value)}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="w-full px-2.5 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500"
                  >
                    <option value="rule">⚖️ Regla de Validación QA/QC</option>
                    <option value="article">📜 Artículo Normativo</option>
                    <option value="requirement">✅ Requisito Mandatorio</option>
                    <option value="restriction">⛔ Restricción</option>
                    <option value="text_note">📝 Nota Técnica</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-slate-300 mb-1">
                  Enunciado Resumido de la Regla (del Fragmento)
                </label>
                <textarea
                  rows={2}
                  value={ruleStatement}
                  onChange={(e) => setRuleStatement(e.target.value)}
                  placeholder="Enunciado conciso y verificable de la regla obtenido del fragmento..."
                  style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                  className="w-full px-3 py-1.5 rounded-xl border text-slate-100 focus:outline-none focus:border-sky-500"
                />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div
            style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
            className="px-4 py-3 flex items-center justify-between relative"
          >
            <button
              onClick={() => {
                setShowTextModal(false);
                setEditingTextItemId(null);
              }}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200"
            >
              Cancelar
            </button>
            <button
              onClick={handleAcceptTextRule}
              className="px-4 py-1.5 text-xs font-bold text-white bg-sky-600 hover:bg-sky-500 rounded-xl transition-all shadow flex items-center gap-1.5"
            >
              <Check className="w-4 h-4" />
              <span>{editingTextItemId ? 'Actualizar Regla' : 'Aceptar e Incorporar'}</span>
            </button>

            {/* Handle Resize */}
            <div
              onMouseDown={handleTextResizeMouseDown}
              style={{ cursor: 'nwse-resize' }}
              className="absolute bottom-1 right-1 p-1 text-slate-500 hover:text-slate-300 transition-colors select-none"
              title="Arrastrar para redimensionar panel"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2L2 8M8 5L5 8M8 8L8 8" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* E) PANEL FLOTANTE: "T OCR GENERAL" (DOCUMENTO / POR PÁGINA + RESUMEN IA)   */}
      {/* ========================================================================= */}
      {showOcrGeneralModal && (
        <div
          style={{
            position: 'fixed',
            left: `${ocrGeneralPos.x}px`,
            top: `${ocrGeneralPos.y}px`,
            width: `${ocrGeneralSize.width}px`,
            height: `${ocrGeneralSize.height}px`,
            zIndex: 65,
            maxWidth: 'calc(100vw - 20px)',
            maxHeight: 'calc(100vh - 20px)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '1rem',
            boxShadow: '0 30px 80px -15px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
            userSelect: isDraggingOcrGeneral || isResizingOcrGeneral ? 'none' : 'auto',
          }}
          className="overflow-hidden animate-in fade-in duration-150"
        >
          {/* Header Arrastrable (Drag Handle) */}
          <div
            onMouseDown={handleOcrGeneralHeaderMouseDown}
            style={{
              cursor: isDraggingOcrGeneral ? 'grabbing' : 'grab',
              backgroundColor: '#020617',
              borderBottom: '1px solid #1e293b',
            }}
            className="px-5 py-3.5 flex items-center justify-between select-none"
          >
            <div className="flex items-center gap-2.5 text-teal-400">
              <GripHorizontal className="w-4 h-4 text-slate-500" />
              <div className="p-1.5 rounded-xl bg-teal-950 text-teal-400 border border-teal-800">
                <BookOpen className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
                  <span>T OCR General del Documento</span>
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Arrastrable</span>
              <button
                onClick={() => setShowOcrGeneralModal(false)}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg"
                title="Cerrar panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Barra de Modo: Documento General vs Por Página */}
          <div
            style={{ backgroundColor: '#020617', borderBottom: '1px solid #1e293b' }}
            className="px-5 py-3 flex items-center justify-between gap-4 flex-wrap text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-semibold">Modo de Escaneo:</span>
              
              {/* Opción 1: Documento General */}
              <button
                onClick={() => handleOcrModeChange('document')}
                className={`px-3 py-1 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                  ocrMode === 'document'
                    ? 'bg-teal-950 text-teal-300 border border-teal-700 shadow'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <FileText className="w-3.5 h-3.5" />
                <span>1. Documento General ({totalPages} Págs)</span>
              </button>

              {/* Opción 2: Por Página */}
              <button
                onClick={() => handleOcrModeChange('page')}
                className={`px-3 py-1 rounded-lg font-bold transition-all flex items-center gap-1.5 ${
                  ocrMode === 'page'
                    ? 'bg-teal-950 text-teal-300 border border-teal-700 shadow'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>2. Por Página</span>
              </button>

              {/* Selector de página cuando está en modo 'page' */}
              {ocrMode === 'page' && (
                <div className="flex items-center gap-1.5 ml-2">
                  <span className="text-slate-400 font-medium">Página:</span>
                  <select
                    value={ocrSelectedPage}
                    onChange={(e) => handleOcrPageSelectChange(parseInt(e.target.value))}
                    style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                    className="px-2 py-0.5 rounded border text-slate-100 font-bold outline-none"
                  >
                    {Array.from({ length: totalPages }, (_, idx) => idx + 1).map((p) => (
                      <option key={p} value={p}>
                        Página {p}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchGeneralOcrData}
                disabled={ocrGeneralLoading}
                className="px-3 py-1 text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg flex items-center gap-1.5 border border-slate-700"
                title="Actualizar texto OCR"
              >
                <RefreshCw className={`w-3 h-3 ${ocrGeneralLoading ? 'animate-spin' : ''}`} />
                <span>Actualizar OCR</span>
              </button>
            </div>
          </div>

          {/* Cuerpo: Texto OCR + Listado de Reglas con IA */}
          <div style={{ backgroundColor: '#0f172a' }} className="p-5 flex-1 overflow-y-auto space-y-4 flex flex-col">
            
            {/* Mensaje de importación exitosa si existe */}
            {rulesImportMessage && (
              <div className="p-3 bg-emerald-950 border border-emerald-700 rounded-xl text-emerald-300 text-xs flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>{rulesImportMessage}</span>
              </div>
            )}

            {/* Visualizador del Texto OCR */}
            <div className="space-y-1.5 flex-1 flex flex-col min-h-[160px]">
              <div className="flex items-center justify-between">
                <label className="font-bold text-slate-200 text-xs">
                  Texto Extraído {ocrMode === 'document' ? '(Documento Completo)' : `(Página ${ocrSelectedPage})`}
                </label>
                <button
                  onClick={() => navigator.clipboard.writeText(ocrGeneralText)}
                  className="text-[11px] text-sky-400 hover:text-sky-300 flex items-center gap-1"
                >
                  <Copy className="w-3 h-3" />
                  <span>Copiar Texto</span>
                </button>
              </div>

              <div
                style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                className="flex-1 min-h-[140px] max-h-56 p-3 rounded-xl border overflow-y-auto font-mono text-xs text-slate-200 leading-relaxed whitespace-pre-wrap select-text"
              >
                {ocrGeneralLoading ? (
                  <div className="flex items-center gap-2 text-slate-400">
                    <Loader2 className="w-4 h-4 animate-spin text-teal-400" />
                    <span>Extrayendo texto OCR continuo...</span>
                  </div>
                ) : (
                  ocrGeneralText || 'Sin texto reconocible.'
                )}
              </div>
            </div>

            {/* BOTÓN REQUERIDO 6: RESUMIR CON IA EN LISTA DE REGLAS */}
            <div className="flex items-center justify-between pt-1">
              <div className="text-[11px] text-slate-400">
                La IA extraerá un <strong>listado de reglas estructuradas</strong> a partir del texto {ocrMode === 'document' ? 'del documento completo' : `de la página ${ocrSelectedPage}`}.
              </div>

              <button
                type="button"
                onClick={handleGenerateRulesFromOcr}
                disabled={isGeneratingRules || !ocrGeneralText.trim() || ocrGeneralLoading}
                className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white text-xs font-bold rounded-xl flex items-center gap-2 shadow-lg disabled:opacity-50 transition-all"
              >
                {isGeneratingRules ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wand2 className="w-4 h-4" />}
                <span>Generar Listado de Reglas con IA</span>
              </button>
            </div>

            {/* SECCIÓN REQUERIDA 7: LISTADO DE REGLAS GENERADAS CON BOTÓN ELIMINAR */}
            {generatedRulesList.length > 0 && (
              <div className="space-y-2 pt-3 border-t border-slate-800">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-xs text-purple-300 flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                    <span>Reglas Extraídas por IA ({generatedRulesList.length})</span>
                  </span>
                  <span className="text-[10px] text-slate-400">
                    Elimina las que no apliquen antes de incorporar
                  </span>
                </div>

                <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                  {generatedRulesList.map((rule, idx) => (
                    <div
                      key={idx}
                      style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                      className="p-3 rounded-xl border flex items-start justify-between gap-3 text-xs"
                    >
                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-950 text-purple-300 border border-purple-800">
                            {rule.code}
                          </span>
                          <span className="font-bold text-slate-200 truncate">
                            {rule.title}
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">Pág. {rule.page_number}</span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-snug">
                          {rule.statement}
                        </p>
                      </div>

                      {/* Botón Eliminar Individual de la regla */}
                      <button
                        onClick={() => handleDeleteGeneratedRule(idx)}
                        className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950 rounded-lg transition-colors shrink-0"
                        title="Eliminar regla del listado"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Footer de "T OCR General" */}
          <div
            style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
            className="px-5 py-3.5 flex items-center justify-between relative"
          >
            <button
              onClick={() => setShowOcrGeneralModal(false)}
              className="px-4 py-2 text-xs text-slate-400 hover:text-slate-200"
            >
              Cerrar
            </button>

            {generatedRulesList.length > 0 && (
              <button
                onClick={handleImportGeneratedRulesToPanel}
                className="px-5 py-2 text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 rounded-xl transition-all shadow-lg flex items-center gap-2"
              >
                <FileCheck className="w-4 h-4" />
                <span>Incorporar Reglas al Panel Lateral ({generatedRulesList.length})</span>
              </button>
            )}

            {/* Handle Resize */}
            <div
              onMouseDown={handleOcrGeneralResizeMouseDown}
              style={{ cursor: 'nwse-resize' }}
              className="absolute bottom-1 right-1 p-1 text-slate-500 hover:text-slate-300 transition-colors select-none"
              title="Arrastrar para redimensionar panel"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2L2 8M8 5L5 8M8 8L8 8" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* F) PANEL FLOTANTE: "REVISAR Y VALIDAR" (FONDO SÓLIDO OSCURO, NO MODAL)    */}
      {/* ========================================================================= */}
      {showReviewModal && (
        <div
          style={{
            position: 'fixed',
            left: `${reviewPanelPos.x}px`,
            top: `${reviewPanelPos.y}px`,
            width: `${reviewPanelSize.width}px`,
            height: `${reviewPanelSize.height}px`,
            zIndex: 70,
            maxWidth: 'calc(100vw - 20px)',
            maxHeight: 'calc(100vh - 20px)',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: '#0f172a',
            color: '#f8fafc',
            border: '1px solid #334155',
            borderRadius: '1rem',
            boxShadow: '0 30px 80px -15px rgba(0, 0, 0, 0.98), 0 0 0 1px #334155',
            userSelect: isDraggingReview || isResizingReview ? 'none' : 'auto',
          }}
          className="overflow-hidden animate-in fade-in duration-150"
        >
          {/* Header Arrastrable (Drag Handle) */}
          <div
            onMouseDown={handleReviewHeaderMouseDown}
            style={{
              cursor: isDraggingReview ? 'grabbing' : 'grab',
              backgroundColor: '#020617',
              borderBottom: '1px solid #1e293b',
            }}
            className="px-5 py-3.5 flex items-center justify-between select-none"
          >
            <div className="flex items-center gap-2.5 text-teal-400">
              <GripHorizontal className="w-4 h-4 text-slate-500" />
              <div className="p-1.5 rounded-xl bg-teal-950 text-teal-400 border border-teal-800">
                <SquareCheck className="w-4 h-4" />
              </div>
              <div>
                <h3 className="text-xs font-bold uppercase tracking-wider text-slate-100 flex items-center gap-2">
                  <span>Revisar y Validar Elementos Extraídos</span>
                  <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                    {sessionItems.length} totales
                  </span>
                </h3>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-[10px] text-slate-500 font-mono hidden sm:inline">Panel Flotante</span>
              <button
                onClick={() => setShowReviewModal(false)}
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg"
                title="Cerrar panel"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Barra de Filtros y Métricas de Estado */}
          <div
            style={{ backgroundColor: '#020617', borderBottom: '1px solid #1e293b' }}
            className="px-5 py-2.5 flex items-center justify-between gap-4 flex-wrap text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="text-slate-400 font-medium">Filtrar:</span>
              <button
                onClick={() => setReviewFilterStatus('all')}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  reviewFilterStatus === 'all'
                    ? 'bg-slate-800 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Todos ({sessionItems.length})
              </button>
              <button
                onClick={() => setReviewFilterStatus('validada')}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  reviewFilterStatus === 'validada'
                    ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🟢 Validadas ({sessionItems.filter((i) => i.review_status === 'validada' || i.review_status === 'accepted').length})
              </button>
              <button
                onClick={() => setReviewFilterStatus('por_confirmar')}
                className={`px-2.5 py-1 rounded-lg font-semibold transition-all ${
                  reviewFilterStatus === 'por_confirmar'
                    ? 'bg-amber-950 text-amber-300 border border-amber-800'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                🟡 Por confirmar ({sessionItems.filter((i) => i.review_status === 'por_confirmar' || i.review_status === 'to_confirm' || i.review_status === 'draft').length})
              </button>
            </div>

            {/* Búsqueda rápida */}
            <div className="relative w-48">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-2" />
              <input
                type="text"
                placeholder="Buscar capturas..."
                value={reviewSearchTerm}
                onChange={(e) => setReviewSearchTerm(e.target.value)}
                style={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                className="w-full pl-8 pr-3 py-1 rounded-lg text-slate-200 text-xs focus:outline-none focus:border-teal-500 border"
              />
            </div>
          </div>

          {/* Tabla / Lista de Elementos */}
          <div style={{ backgroundColor: '#0f172a' }} className="p-5 flex-1 overflow-y-auto">
            {commitMessage ? (
              <div style={{ backgroundColor: '#064e3b', borderColor: '#047857' }} className="p-6 border rounded-2xl text-center space-y-2">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto" />
                <h4 className="text-sm font-bold text-emerald-200">¡Incorporación Completada!</h4>
                <p className="text-xs text-emerald-300">{commitMessage}</p>
              </div>
            ) : filteredReviewItems.length === 0 ? (
              <div className="p-10 text-center text-slate-500 space-y-2">
                <AlertCircle className="w-8 h-8 mx-auto text-slate-600" />
                <p className="text-sm font-semibold text-slate-400">No hay elementos en este filtro</p>
              </div>
            ) : (
              <div className="space-y-3">
                {filteredReviewItems.map((item) => (
                  <div
                    key={item.id}
                    style={{ backgroundColor: '#020617', borderColor: '#334155' }}
                    className="p-4 rounded-xl border hover:border-slate-600 flex items-start justify-between gap-4 transition-all"
                  >
                    {/* Columna Izquierda: Thumbnail / Icono y Metadatos */}
                    <div className="flex items-start gap-3 flex-1 min-w-0">
                      {item.crop_image_path ? (
                        <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="w-16 h-16 border rounded-lg overflow-hidden shrink-0 flex items-center justify-center p-1">
                          <img
                            src={item.crop_image_path}
                            alt={item.title}
                            className="max-h-full max-w-full object-contain rounded"
                          />
                        </div>
                      ) : (
                        <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="w-10 h-10 border rounded-lg flex items-center justify-center shrink-0 text-sky-400">
                          <FileText className="w-5 h-5" />
                        </div>
                      )}

                      <div className="space-y-1 flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          {getItemTypeBadge(item.item_type)}
                          <span className="text-xs font-bold text-slate-200 truncate">
                            {item.title}
                          </span>
                          {(item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule') && (
                            <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-700">
                              🚫 Ya existe en Motor QA/QC ({item.best_match_rule_code || 'Existente'})
                            </span>
                          )}
                          {item.code_or_number && (
                            <span style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="font-mono text-[10px] px-1.5 py-0.5 rounded text-slate-400 border">
                              {item.code_or_number}
                            </span>
                          )}
                          <span className="text-[10px] text-slate-500 font-mono">Pág. {item.page_number}</span>
                        </div>

                        {item.description && (
                          <p className="text-xs text-slate-400 line-clamp-2">
                            {item.description}
                          </p>
                        )}

                        <div className="text-[10px] text-slate-500 flex items-center gap-2">
                          <span>Destino: <strong className="text-slate-400">{item.target_destination === 'knowledge_base' ? 'Base de Apoyo y Patrones' : 'Motor de Reglas QA/QC'}</strong></span>
                        </div>
                      </div>
                    </div>

                    {/* Columna Derecha: Estado y Botones de Acción Individual */}
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <div className="flex items-center gap-2">
                        {getStatusBadge(item.review_status)}
                      </div>

                      <div style={{ backgroundColor: '#0f172a', borderColor: '#334155' }} className="flex items-center gap-1.5 p-1 rounded-xl border">
                        {/* 1. EDITAR */}
                        <button
                          onClick={() => handleEditItem(item)}
                          className="px-2 py-1 text-[11px] font-semibold text-slate-300 hover:text-white hover:bg-slate-800 rounded-lg flex items-center gap-1 transition-all"
                          title="Editar campos y contenido"
                        >
                          <Edit3 className="w-3 h-3 text-sky-400" />
                          <span>Editar</span>
                        </button>

                        {/* 2. POR CONFIRMAR */}
                        <button
                          onClick={() => handleUpdateItemStatus(item, 'por_confirmar')}
                          className={`px-2 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                            item.review_status === 'por_confirmar' || item.review_status === 'to_confirm' || item.review_status === 'draft'
                              ? 'bg-amber-950 text-amber-300 border border-amber-800'
                              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                          }`}
                          title="Dejar pendiente para validar después"
                        >
                          <Clock className="w-3 h-3" />
                          <span>Por confirmar</span>
                        </button>

                        {/* 3. VALIDADA */}
                        <button
                          disabled={item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule'}
                          onClick={() => handleUpdateItemStatus(item, 'validada')}
                          className={`px-2 py-1 text-[11px] font-semibold rounded-lg flex items-center gap-1 transition-all ${
                            item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule'
                              ? 'text-slate-600 bg-slate-900 border border-slate-800 cursor-not-allowed opacity-40'
                              : item.review_status === 'validada' || item.review_status === 'accepted'
                              ? 'bg-emerald-950 text-emerald-300 border border-emerald-800 font-bold'
                              : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                          }`}
                          title={
                            item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule'
                              ? 'Bloqueado: Ya existe en Motor de Reglas QA/QC'
                              : 'Marcar como lista para incorporar'
                          }
                        >
                          <Check className="w-3 h-3 text-emerald-400" />
                          <span>Validada</span>
                        </button>

                        {/* 4. ELIMINAR */}
                        <button
                          onClick={() => handleUpdateItemStatus(item, 'eliminado')}
                          className="p-1 text-slate-400 hover:text-rose-400 hover:bg-rose-950 rounded-lg transition-all"
                          title="Eliminar de la lista"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer de la Ventana "Revisar y Validar" */}
          <div
            style={{ backgroundColor: '#020617', borderTop: '1px solid #1e293b' }}
            className="px-5 py-3.5 flex items-center justify-between relative"
          >
            <div className="text-xs text-slate-400">
              Solo se incorporarán los elementos en estado <strong className="text-emerald-400">«Validada»</strong>. Los que estén en <strong className="text-amber-400">«Por confirmar»</strong> quedarán pendientes.
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowReviewModal(false)}
                className="px-4 py-2 text-xs font-semibold text-slate-400 hover:text-slate-200 rounded-xl"
              >
                Cancelar
              </button>

              <button
                onClick={handleCommitValidatedItems}
                disabled={isCommitting || sessionItems.filter((i) => i.review_status === 'validada' || i.review_status === 'accepted').length === 0}
                className="px-5 py-2 text-xs font-bold text-white bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-xl transition-all shadow-lg flex items-center gap-2"
              >
                {isCommitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
                <span>
                  Aceptar e Incorporar ({sessionItems.filter((i) => i.review_status === 'validada' || i.review_status === 'accepted').length} Validadas)
                </span>
              </button>
            </div>

            {/* Handle Resize */}
            <div
              onMouseDown={handleReviewResizeMouseDown}
              style={{ cursor: 'nwse-resize' }}
              className="absolute bottom-1 right-1 p-1 text-slate-500 hover:text-slate-300 transition-colors select-none"
              title="Arrastrar para redimensionar panel"
            >
              <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M8 2L2 8M8 5L5 8M8 8L8 8" strokeLinecap="round" />
              </svg>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
