import React, { useState, useEffect } from 'react';
import {
  X, Check, Trash2, Edit3, ShieldAlert, Sparkles, BookOpen,
  Filter, Layers, CheckCircle2, AlertCircle, Clock, Eye,
  Table as TableIcon, Shapes, FileText, BookmarkPlus, ArrowRight,
  Database, HelpCircle, Globe, ExternalLink, ShieldCheck, Link2,
  ShieldX, Ban, AlertTriangle, Compass, Maximize2, ArrowDownToLine, Loader2
} from 'lucide-react';
import { apiService } from '../services/api';
import { translationService } from '../services/translationService';
import { formatApiError } from '../utils/errorHandler';
import { SourceExtraction, ExtractedItem, ExtractedItemType, ItemNatureType, WebCitation } from '../types';
import { getDisplayField, hasActiveTranslation, deduplicateText } from '../utils/translationResolver';
import { ItemCropLightboxModal } from './ItemCropLightboxModal';
import { ItemContextViewerModal } from './ItemContextViewerModal';
import { SymbolCurationStudioModal } from './SymbolCurationStudioModal';

interface SourceExtractionReviewModalProps {
  isOpen: boolean;
  extractionId: string | null;
  ruleDocumentId?: string | null;
  readOnly?: boolean;
  onClose: () => void;
  onCommitted?: () => void;
}

export const SourceExtractionReviewModal: React.FC<SourceExtractionReviewModalProps> = ({
  isOpen,
  extractionId,
  ruleDocumentId,
  readOnly = false,
  onClose,
  onCommitted,
}) => {
  const [extraction, setExtraction] = useState<SourceExtraction | null>(null);
  const [items, setItems] = useState<ExtractedItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [committing, setCommitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [originFilter, setOriginFilter] = useState<'all' | 'document' | 'web'>('all');
  const [editingItem, setEditingItem] = useState<ExtractedItem | null>(null);
  const [showCitations, setShowCitations] = useState<boolean>(false);

  // Modales de Revisión Asistida Multimodal
  const [lightboxItem, setLightboxItem] = useState<ExtractedItem | null>(null);
  const [contextModalItem, setContextModalItem] = useState<ExtractedItem | null>(null);
  const [enrichingItemId, setEnrichingItemId] = useState<string | null>(null);
  const [isSymbolStudioOpen, setIsSymbolStudioOpen] = useState<boolean>(false);

  // Formulario de edición
  const [editTitle, setEditTitle] = useState('');
  const [editCode, setEditCode] = useState('');
  const [editDesc, setEditDesc] = useState('');
  const [editOcr, setEditOcr] = useState('');
  const [editDestination, setEditDestination] = useState<'rules_engine' | 'knowledge_base' | 'both'>('rules_engine');
  const [editType, setEditType] = useState<ExtractedItemType>('rule');
  const [editNature, setEditNature] = useState<ItemNatureType>('official_rule');
  const [editSourceRef, setEditSourceRef] = useState('');

  // Filtros de completitud, revisión y parches de campo
  const [completenessFilter, setCompletenessFilter] = useState<string>('all');
  const [reviewStatusFilter, setReviewStatusFilter] = useState<string>('all');
  const [fieldPatchingId, setFieldPatchingId] = useState<string | null>(null);

  // Preferencias y visualización de traducción IA (Tri-State Viewer)
  const [translationViewMode, setTranslationViewMode] = useState<'original' | 'translation' | 'both'>('original');
  const [selectedTargetLang, setSelectedTargetLang] = useState<string>('es');
  const [translationsCache, setTranslationsCache] = useState<Record<string, Record<string, string>>>({});
  const [translatingItemIds, setTranslatingItemIds] = useState<Set<string>>(new Set());
  const [selectedItemIds, setSelectedItemIds] = useState<Set<string>>(new Set());
  const [translatingBatch, setTranslatingBatch] = useState<boolean>(false);

  useEffect(() => {
    if (isOpen) {
      if (extractionId) {
        loadExtractionData(extractionId);
      } else if (ruleDocumentId) {
        loadRuleDocumentItems(ruleDocumentId);
      }
    }
  }, [isOpen, extractionId, ruleDocumentId]);

  const loadExtractionData = async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await apiService.getExtractionDetail(id);
      setExtraction(data);
      const loadedItems = data.items || [];
      setItems(loadedItems);

      // Cargar traducciones pre-generadas por el job en el caché de traducción
      const initialCache: Record<string, Record<string, string>> = {};
      let hasTranslations = false;
      loadedItems.forEach((item: any) => {
        const tr = item.translated_fields || item.metadata_payload?.translated_fields;
        if (tr && Object.keys(tr).length > 0) {
          initialCache[item.id] = tr;
          hasTranslations = true;
        }
      });
      if (hasTranslations) {
        setTranslationsCache((prev) => ({ ...initialCache, ...prev }));
        setTranslationViewMode('translation');
      }
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const loadRuleDocumentItems = async (docId: string) => {
    setLoading(true);
    setError(null);
    try {
      const doc = await apiService.getRuleDocumentDetail(docId);
      const isWeb = doc.source_origin === 'con_ia_web';
      setExtraction({
        id: doc.id,
        organization_id: doc.organization_id,
        extraction_mode: doc.source_origin === 'con_ia_web' ? 'ai_web_research' : doc.source_origin === 'con_ia_documento' ? 'ai_document' : 'without_ai',
        source_origin: isWeb ? 'web' : 'document',
        search_query: doc.metadata_info?.search_query,
        search_citations: doc.metadata_info?.search_citations,
        title: doc.title,
        document_type: doc.document_type,
        authority: doc.authority,
        discipline: doc.discipline,
        status: doc.status as any,
        summary: doc.description,
        total_items: doc.items_count,
        created_at: doc.created_at,
        updated_at: doc.updated_at,
      });
      // Mapear items de rule document a extracted items para visualización uniforme
      const mapped: ExtractedItem[] = (doc.items || []).map((it: any) => ({
        id: it.id,
        extraction_id: doc.id,
        item_type: it.item_type as ExtractedItemType,
        title: it.title,
        code_or_number: it.code_or_number,
        description: it.description,
        content_text: it.content_text,
        ocr_text: it.ocr_text,
        crop_image_path: it.crop_image_path,
        bbox_normalized: [],
        page_number: 1,
        target_destination: it.target_destination as any,
        review_status: 'accepted',
        source_origin: (it.source_origin as any) || (isWeb ? 'web' : 'document'),
        source_reference: it.source_reference,
        item_nature: (it.item_nature as ItemNatureType) || (isWeb ? 'proposed_rule' : 'official_rule'),
        governance_note: isWeb ? 'Incorporado desde investigación en Internet' : undefined,
        created_at: it.created_at,
        updated_at: it.created_at,
      }));
      setItems(mapped);
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setLoading(false);
    }
  };

  const handleStatusChange = async (item: ExtractedItem, newStatus: 'to_confirm' | 'accepted' | 'rejected') => {
    if (!extractionId) return;
    if (newStatus === 'accepted' && (item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule')) {
      setError(`La regla '${item.title}' ya existe en el Motor de Reglas QA/QC y no puede aceptarse.`);
      return;
    }
    try {
      await apiService.updateExtractedItem(extractionId, item.id, { review_status: newStatus });
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, review_status: newStatus } : i)));
      setError(null);
    } catch (err: any) {
      setError(formatApiError(err));
    }
  };

  const handleDeleteItem = async (itemId: string) => {
    if (!extractionId) return;
    try {
      await apiService.deleteExtractedItem(extractionId, itemId);
      setItems((prev) => prev.filter((i) => i.id !== itemId));
    } catch (err) {
      console.error('Error eliminando item:', err);
    }
  };

  const handleStartEdit = (item: ExtractedItem) => {
    setEditingItem(item);
    const tr = translationsCache[item.id] || item.translated_fields || item.metadata_payload?.translated_fields;
    const hasTrans = hasActiveTranslation(item, tr);
    const titleField = getDisplayField(item, 'title', translationViewMode, tr);
    const descField = getDisplayField(item, 'description', translationViewMode, tr);

    if (translationViewMode === 'translation' && hasTrans) {
      setEditTitle(titleField.translated || titleField.value || item.title);
      const rawDesc = descField.translated || descField.value || item.description || item.content_text || '';
      setEditDesc(deduplicateText(rawDesc));
    } else {
      setEditTitle(titleField.value || item.title);
      const rawDesc = descField.value || item.description || item.content_text || '';
      setEditDesc(deduplicateText(rawDesc));
    }

    setEditCode(item.code_or_number || '');
    setEditOcr(item.ocr_text || '');
    setEditDestination(item.target_destination);
    setEditType(item.item_type);
    setEditNature(item.item_nature || (item.source_origin === 'web' ? 'proposed_rule' : 'official_rule'));
    setEditSourceRef(item.source_reference || '');
  };

  const handleSaveEdit = async () => {
    if (!editingItem || !extractionId) return;
    try {
      const updated = await apiService.updateExtractedItem(extractionId, editingItem.id, {
        title: editTitle.trim(),
        code_or_number: editCode.trim() || undefined,
        description: editDesc.trim() || undefined,
        ocr_text: editOcr.trim() || undefined,
        target_destination: editDestination,
        item_type: editType,
        item_nature: editNature,
        source_reference: editSourceRef.trim() || undefined,
      });
      setItems((prev) => prev.map((i) => (i.id === editingItem.id ? { ...i, ...updated } : i)));
      setEditingItem(null);
    } catch (err: any) {
      setError(formatApiError(err));
    }
  };

  const handleEnrichItem = async (item: ExtractedItem) => {
    if (!extractionId) return;
    setEnrichingItemId(item.id);
    setError(null);
    try {
      const tr = translationsCache[item.id] || item.translated_fields || item.metadata_payload?.translated_fields || {};
      const eff = {
        title: tr.title || item.effective_fields?.title || item.title,
        description: tr.description || item.effective_fields?.description || item.description || item.content_text,
        content_text: tr.content_text || item.effective_fields?.content_text || item.content_text,
        technical_function: tr.technical_function || item.effective_fields?.technical_function
      };
      const src = item.source_fields || {
        title: item.title,
        description: item.description,
        content_text: item.content_text
      };

      const res = await apiService.enrichExtractedItem(extractionId, item.id, {
        presentation_language: selectedTargetLang || 'es',
        source_fields: src,
        translated_fields: tr,
        effective_fields: eff,
        candidate_type: item.candidate_type || item.item_type,
        title: eff.title || item.title,
        caption_or_context: item.caption_or_context,
        ocr_text: item.ocr_text,
        discipline: item.discipline || 'general',
        page_number: item.page_number || 1,
        force_web_search: true,
      });
      setItems((prev) => prev.map((i) => {
        if (i.id === item.id) {
          return {
            ...i,
            enrichment_status: res.enrichment_status,
            completeness_status: res.completeness_status,
            match_confidence: res.match_confidence,
            suggested_title: res.suggested_title,
            suggested_description: res.suggested_description,
            suggested_function: res.suggested_function,
            suggested_source_label: res.suggested_source_label,
            suggested_source_url: res.suggested_source_url,
            enrichment_method: res.enrichment_method,
            requires_validation: res.requires_validation,
            enriched_from_web: res.enriched_from_web,
            effective_fields: res.effective_fields || i.effective_fields,
          };
        }
        return i;
      }));
      if (editingItem && editingItem.id === item.id) {
        setEditingItem((prev) => prev ? {
          ...prev,
          suggested_title: res.suggested_title,
          suggested_description: res.suggested_description,
          suggested_function: res.suggested_function,
          enrichment_status: res.enrichment_status
        } : null);
      }
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setEnrichingItemId(null);
    }
  };

  const handleApplySuggestion = async (item: ExtractedItem) => {
    if (!extractionId) return;
    try {
      const updated = await apiService.applyItemSuggestion(extractionId, item.id);
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...updated } : i)));
    } catch (err: any) {
      setError(formatApiError(err));
    }
  };

  const handleItemUpdated = (updatedItem: ExtractedItem) => {
    setItems((prev) => prev.map((i) => (i.id === updatedItem.id ? { ...i, ...updatedItem } : i)));
    if (editingItem && editingItem.id === updatedItem.id) {
      setEditingItem(updatedItem);
      setEditTitle(updatedItem.title);
      setEditCode(updatedItem.code_or_number || '');
      setEditDesc(updatedItem.description || updatedItem.content_text || '');
    }
  };

  const handleOpenOccurrenceContext = (item: ExtractedItem, occ: any) => {
    setContextModalItem({
      ...item,
      page_number: occ.page_number || item.page_number,
      bbox_normalized: occ.cell_bbox || occ.bbox_normalized || item.bbox_normalized,
      crop_image_path: occ.crop_image_path || item.crop_image_path,
      source_reference: occ.source_reference || item.source_reference
    });
  };

  const handleCommitAll = async () => {
    if (!extractionId) return;
    setCommitting(true);
    setError(null);
    try {
      const approvedIds = items
        .filter((i) => i.review_status === 'accepted' && !i.blocked_from_acceptance && i.duplicate_status !== 'exact_match_existing_rule')
        .map((i) => i.id);

      await apiService.commitExtractionToRules(extractionId, {
        approved_item_ids: approvedIds.length > 0 ? approvedIds : undefined,
      });
      if (onCommitted) onCommitted();
      onClose();
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setCommitting(false);
    }
  };

  const handleAcceptField = async (item: ExtractedItem, fieldName: string, acceptedValue: string, acceptedFrom = 'suggested_value') => {
    if (!extractionId) return;
    setFieldPatchingId(`${item.id}_${fieldName}`);
    try {
      const updated = await apiService.acceptItemField(extractionId, item.id, {
        field_name: fieldName,
        accepted_value: acceptedValue,
        accepted_from: acceptedFrom,
        user_id: 'auditor_humano'
      });
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...updated } : i)));
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setFieldPatchingId(null);
    }
  };

  const handleTranslateSingleItem = async (item: ExtractedItem) => {
    setTranslatingItemIds((prev) => new Set(prev).add(item.id));
    setError(null);
    try {
      const sourceFields: Record<string, string> = {
        title: (item.source_fields?.title || item.title || '').trim(),
      };
      const desc = (item.source_fields?.description || item.description || item.content_text || '').trim();
      if (desc) sourceFields.description = desc;
      const content = (item.source_fields?.content_text || item.content_text || '').trim();
      if (content && content !== desc) sourceFields.content_text = content;

      const res = await translationService.translateEntity({
        source_entity_type: 'extracted_item',
        source_entity_id: item.id,
        target_language: selectedTargetLang,
        source_language: item.source_language || 'auto',
        fields_to_translate: sourceFields,
        organization_id: extraction?.organization_id || localStorage.getItem('active_org_id') || undefined
      });

      const transFields = res.translated_fields || {};
      const transStatus = res.translation_status || res.status || 'completed';

      setTranslationsCache((prev) => ({
        ...prev,
        [item.id]: transFields
      }));

      setItems((prev) => prev.map((it) => {
        if (it.id === item.id) {
          return {
            ...it,
            translated_fields: transFields,
            effective_fields: {
              ...it.effective_fields,
              ...transFields,
            },
            translation_status: transStatus as any,
            target_language: selectedTargetLang,
          };
        }
        return it;
      }));

      // Si este ítem está siendo editado actualmente en el modal de edición, actualizarlo de inmediato
      if (editingItem && editingItem.id === item.id) {
        setEditingItem((prev) => prev ? {
          ...prev,
          translated_fields: transFields,
          effective_fields: {
            ...prev.effective_fields,
            ...transFields
          },
          translation_status: transStatus as any
        } : null);
        if (transFields.title) setEditTitle(transFields.title);
        if (transFields.description) setEditDesc(deduplicateText(transFields.description));
      }
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setTranslatingItemIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
    }
  };

  const handleTranslateSelected = async () => {
    if (selectedItemIds.size === 0) return;
    setTranslatingBatch(true);
    setError(null);
    try {
      const selectedItems = items.filter((it) => selectedItemIds.has(it.id));
      const reqItems = selectedItems.map((it) => {
        const fields: Record<string, string> = {
          title: (it.source_fields?.title || it.title || '').trim(),
        };
        const d = (it.source_fields?.description || it.description || it.content_text || '').trim();
        if (d) fields.description = d;
        const c = (it.source_fields?.content_text || it.content_text || '').trim();
        if (c && c !== d) fields.content_text = c;

        return {
          source_entity_type: 'extracted_item',
          source_entity_id: it.id,
          target_language: selectedTargetLang,
          source_language: it.source_language || 'auto',
          fields_to_translate: fields,
          organization_id: extraction?.organization_id || localStorage.getItem('active_org_id') || undefined
        };
      });

      const res = await translationService.translateBatch({
        items: reqItems,
        target_language: selectedTargetLang
      });

      const transMap: Record<string, Record<string, string>> = {};
      const statusMap: Record<string, string> = {};
      for (const t of res.translations) {
        const id = t.source_entity_id || t.entity_id;
        if (id) {
          transMap[id] = t.translated_fields;
          statusMap[id] = t.translation_status || t.status || 'completed';
        }
      }

      setTranslationsCache((prev) => ({ ...prev, ...transMap }));
      setItems((prev) => prev.map((it) => {
        if (transMap[it.id]) {
          return {
            ...it,
            translated_fields: transMap[it.id],
            effective_fields: {
              ...it.effective_fields,
              ...transMap[it.id],
            },
            translation_status: (statusMap[it.id] || 'completed') as any,
            target_language: selectedTargetLang,
          };
        }
        return it;
      }));
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setTranslatingBatch(false);
    }
  };

  const handleTranslateDocument = async () => {
    if (items.length === 0) return;
    setTranslatingBatch(true);
    setError(null);
    try {
      const reqItems = items.map((it) => {
        const fields: Record<string, string> = {
          title: (it.source_fields?.title || it.title || '').trim(),
        };
        const d = (it.source_fields?.description || it.description || it.content_text || '').trim();
        if (d) fields.description = d;
        const c = (it.source_fields?.content_text || it.content_text || '').trim();
        if (c && c !== d) fields.content_text = c;

        return {
          source_entity_type: 'extracted_item',
          source_entity_id: it.id,
          target_language: selectedTargetLang,
          source_language: it.source_language || 'auto',
          fields_to_translate: fields,
          organization_id: extraction?.organization_id || localStorage.getItem('active_org_id') || undefined
        };
      });

      const res = await translationService.translateBatch({
        items: reqItems,
        target_language: selectedTargetLang
      });

      const transMap: Record<string, Record<string, string>> = {};
      const statusMap: Record<string, string> = {};
      for (const t of res.translations) {
        const id = t.source_entity_id || t.entity_id;
        if (id) {
          transMap[id] = t.translated_fields;
          statusMap[id] = t.translation_status || t.status || 'completed';
        }
      }

      setTranslationsCache((prev) => ({ ...prev, ...transMap }));
      setItems((prev) => prev.map((it) => {
        if (transMap[it.id]) {
          return {
            ...it,
            translated_fields: transMap[it.id],
            effective_fields: {
              ...it.effective_fields,
              ...transMap[it.id],
            },
            translation_status: (statusMap[it.id] || 'completed') as any,
            target_language: selectedTargetLang,
          };
        }
        return it;
      }));
    } catch (err: any) {
      setError(formatApiError(err));
    } finally {
      setTranslatingBatch(false);
    }
  };

  const isSymbolItem = (it: any) => {
    const isFig = (
      it.graphic_classification === 'figure' ||
      it.graphic_classification === 'table_graphic' ||
      it.content_class === 'figure' ||
      it.content_class === 'table_graphic' ||
      it.metadata_payload?.content_class === 'figure' ||
      it.metadata_payload?.content_class === 'table_graphic' ||
      it.item_type === 'figure' ||
      it.item_type === 'image'
    );
    if (isFig) return false;
    return (
      ['symbol', 'simbolo', 'leyenda', 'symbol_candidate'].includes(it.item_type) ||
      it.candidate_type === 'symbol_candidate' ||
      it.category === 'symbol'
    );
  };

  const filteredItems = items.filter((it) => {
    // Filtro por procedencia
    if (originFilter !== 'all' && (it.source_origin || 'document') !== originFilter) {
      return false;
    }
    // Filtro por estado de revisión
    if (reviewStatusFilter !== 'all') {
      if (reviewStatusFilter === 'accepted' && it.review_status !== 'accepted' && it.review_status !== 'validada') return false;
      if (reviewStatusFilter === 'to_confirm' && it.review_status !== 'to_confirm' && it.review_status !== 'por_confirmar' && it.review_status !== 'draft') return false;
      if (reviewStatusFilter === 'rejected' && it.review_status !== 'rejected' && it.review_status !== 'eliminado') return false;
    }
    // Filtro por completitud
    if (completenessFilter !== 'all') {
      if (completenessFilter === 'complete' && it.completeness_status !== 'complete') return false;
      if (completenessFilter === 'partial' && it.completeness_status !== 'partial') return false;
      if (completenessFilter === 'missing_data' && it.completeness_status !== 'missing_data' && it.completeness_status !== 'needs_visual_crop') return false;
      if (completenessFilter === 'web_suggested' && it.completeness_status !== 'web_suggested' && it.enrichment_status !== 'suggestion_found') return false;
    }
    // Filtro por tipo de elemento
    if (filterType === 'all') return true;
    if (filterType === 'rules') return ['rule', 'restriction', 'requirement'].includes(it.item_type);
    if (filterType === 'equipment') return ['equipment', 'equipo', 'instrument', 'instrumento'].includes(it.item_type);
    if (filterType === 'symbols') return isSymbolItem(it);
    if (filterType === 'articles') return ['article', 'chapter'].includes(it.item_type);
    if (filterType === 'tables') return ['table', 'tabla'].includes(it.item_type);
    if (filterType === 'figures') {
      return (
        ['figure', 'image', 'foto', 'table_graphic'].includes(it.item_type) ||
        it.graphic_classification === 'figure' ||
        it.graphic_classification === 'table_graphic' ||
        it.content_class === 'figure' ||
        it.content_class === 'table_graphic' ||
        it.metadata_payload?.content_class === 'figure' ||
        it.metadata_payload?.content_class === 'table_graphic'
      );
    }
    if (filterType === 'notes') return ['text_note', 'definition', 'procedure', 'concept', 'reference'].includes(it.item_type);
    return true;
  });

  const getItemTypeBadge = (type: string, nature?: string, origin?: string, item?: any) => {
    const gClass = item?.graphic_classification || item?.metadata_payload?.graphic_classification;
    const cClass = item?.content_class || item?.metadata_payload?.content_class;
    if (gClass === 'figure' || cClass === 'figure' || type === 'figure' || type === 'image') {
      return { label: 'FIGURA / ESQUEMA TÉCNICO', bg: 'bg-violet-500/10 text-violet-400 border-violet-800/40' };
    }
    if (gClass === 'table_graphic' || cClass === 'table_graphic') {
      return { label: 'GRÁFICO TABULAR / ESQUEMA', bg: 'bg-cyan-500/10 text-cyan-400 border-cyan-800/40' };
    }
    if (origin === 'web' || nature === 'proposed_rule') {
      if (type === 'rule' || type === 'restriction' || type === 'requirement') {
        return { label: 'REGLA PROPUESTA (WEB)', bg: 'bg-amber-500/10 text-amber-300 border-amber-800/60' };
      }
    }
    switch (type) {
      case 'rule':
      case 'restriction':
      case 'requirement':
        return { label: 'REGLA QA/QC OFICIAL', bg: 'bg-rose-500/10 text-rose-400 border-rose-800/40' };
      case 'article':
      case 'chapter':
        return { label: 'ARTÍCULO / CAPÍTULO', bg: 'bg-sky-500/10 text-sky-400 border-sky-800/40' };
      case 'table':
        return { label: 'TABLA DE PARÁMETROS', bg: 'bg-emerald-500/10 text-emerald-400 border-emerald-800/40' };
      case 'symbol':
      case 'simbolo':
      case 'symbol_candidate':
        if (gClass === 'figure' || gClass === 'table_graphic' || cClass === 'figure' || cClass === 'table_graphic') {
          return { label: 'FIGURA / ESQUEMA TÉCNICO', bg: 'bg-violet-500/10 text-violet-400 border-violet-800/40' };
        }
        return { label: 'SÍMBOLO TÉCNICO', bg: 'bg-purple-500/10 text-purple-400 border-purple-800/40' };
      case 'figure':
      case 'image':
        return { label: 'FIGURA / ESQUEMA', bg: 'bg-violet-500/10 text-violet-400 border-violet-800/40' };
      case 'definition':
      case 'concept':
      case 'procedure':
      case 'text_note':
        return { label: 'CONCEPTO / PROCEDIMIENTO', bg: 'bg-indigo-500/10 text-indigo-300 border-indigo-800/40' };
      case 'reference':
        return { label: 'REFERENCIA WEB / LEGAL', bg: 'bg-slate-700/20 text-slate-300 border-slate-700' };
      default:
        return { label: 'OTRO', bg: 'bg-slate-700/20 text-slate-400 border-slate-700' };
    }
  };

  const isWebExtraction = extraction?.source_origin === 'web' || extraction?.extraction_mode === 'ai_web_research';

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/85 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-5xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        
        {/* Encabezado */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/70">
          <div className="flex items-center space-x-3">
            <div className={`p-2 rounded-xl ${isWebExtraction ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20' : 'bg-teal-500/10 text-teal-400 border border-teal-500/20'}`}>
              {isWebExtraction ? <Globe className="w-5 h-5" /> : extraction?.extraction_mode === 'with_ai' || extraction?.extraction_mode === 'ai_document' ? <Sparkles className="w-5 h-5" /> : <BookOpen className="w-5 h-5 text-sky-400" />}
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-base font-bold text-slate-100">
                  {extraction ? extraction.title : 'Revisión y Validación de Contenido Estructurado'}
                </h2>
                
                {/* Badge de Procedencia */}
                {isWebExtraction ? (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700 flex items-center gap-1">
                    <Globe className="w-3 h-3" /> Origen: Búsqueda en Internet
                  </span>
                ) : (
                  <span className="text-[10px] font-bold uppercase px-2.5 py-0.5 rounded-full bg-teal-950 text-teal-300 border border-teal-700 flex items-center gap-1">
                    <FileText className="w-3 h-3" /> Origen: Documento Interno
                  </span>
                )}

                <span className="text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {extraction?.document_type || 'Norma'}
                </span>
                {extraction?.authority && (
                  <span className="text-[10px] font-medium text-slate-400">
                    • {extraction.authority}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                Valida, edita o descarta elementos antes de incorporarlos al Motor de Reglas QA/QC y a la Base de Conocimiento
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Desplegable de Fuentes / Citaciones Web */}
        {showCitations && extraction?.search_citations && (
          <div className="px-6 py-3.5 bg-slate-950/90 border-b border-indigo-900/40 text-xs space-y-2 max-h-48 overflow-y-auto animate-in slide-in-from-top-2">
            <div className="font-bold text-indigo-300 flex items-center gap-2">
              <Globe className="w-4 h-4 text-indigo-400" />
              <span>Fuentes Web Consultadas y Citadas:</span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {extraction.search_citations.map((cite, idx) => (
                <a
                  key={idx}
                  href={cite.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-lg bg-slate-900/80 border border-slate-800 hover:border-indigo-600 transition-all flex items-start gap-2 text-[11px] group"
                >
                  <ExternalLink className="w-3.5 h-3.5 text-indigo-400 shrink-0 mt-0.5 group-hover:text-indigo-300" />
                  <div className="min-w-0">
                    <div className="font-semibold text-slate-200 truncate group-hover:text-indigo-200">{cite.title || cite.domain}</div>
                    <div className="text-slate-400 text-[10px] truncate">{cite.url}</div>
                  </div>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Barra de Filtros Visibles y Contadores en Tiempo Real */}
        <div className="px-6 py-3 border-b border-slate-800/80 bg-slate-900/60 flex flex-col gap-2.5">
          {/* Fila 1: Filtros de Tipo */}
          <div className="flex items-center justify-between flex-wrap gap-2">
            <div className="flex items-center space-x-1.5 overflow-x-auto py-0.5 scrollbar-thin">
              <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 mr-1">
                <Filter className="w-3 h-3" /> Tipo:
              </span>
              <button
                onClick={() => setFilterType('all')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'all' ? 'bg-teal-600 text-white shadow-sm' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                Todos ({items.length})
              </button>
              <button
                onClick={() => setFilterType('rules')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'rules' ? 'bg-rose-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                Reglas ({items.filter((i) => ['rule', 'restriction', 'requirement'].includes(i.item_type)).length})
              </button>
              <button
                onClick={() => setFilterType('equipment')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'equipment' ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                🏷️ Equipos ({items.filter((i) => ['equipment', 'equipo', 'instrument', 'instrumento'].includes(i.item_type)).length})
              </button>
              <button
                onClick={() => setFilterType('symbols')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'symbols' ? 'bg-purple-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                🔣 Símbolos ({items.filter(isSymbolItem).length})
              </button>
              {items.some(isSymbolItem) && (
                <button
                  type="button"
                  onClick={() => setIsSymbolStudioOpen(true)}
                  className="px-2.5 py-1 text-xs font-bold rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white shadow-sm flex items-center gap-1.5 transition-all active:scale-95"
                  title="Abrir Estudio de Curación HITL, Deduplicación y Catálogo de Símbolos"
                >
                  <Compass className="w-3.5 h-3.5 text-purple-200" />
                  <span>Curar Símbolos (HITL)</span>
                </button>
              )}
              <button
                onClick={() => setFilterType('tables')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'tables' ? 'bg-emerald-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                📊 Tablas ({items.filter((i) => ['table', 'tabla'].includes(i.item_type)).length})
              </button>
              <button
                onClick={() => setFilterType('figures')}
                className={`px-2.5 py-1 text-xs font-medium rounded-lg transition-all ${filterType === 'figures' ? 'bg-violet-600 text-white' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'}`}
              >
                🖼️ Figuras & Esquemas ({items.filter((i) => ['figure', 'image', 'foto', 'table_graphic'].includes(i.item_type) || ['figure', 'table_graphic'].includes((i as any).graphic_classification || (i as any).content_class)).length})
              </button>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 inline-block" /> Aceptados: {items.filter((i) => i.review_status === 'accepted' || i.review_status === 'validada').length}
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" /> Por Confirmar: {items.filter((i) => i.review_status === 'to_confirm' || i.review_status === 'por_confirmar' || i.review_status === 'draft').length}
              </span>
              {items.filter((i) => i.blocked_from_acceptance || i.duplicate_status === 'exact_match_existing_rule').length > 0 && (
                <span className="flex items-center gap-1 text-rose-400 font-semibold">
                  <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> En Motor QA/QC: {items.filter((i) => i.blocked_from_acceptance || i.duplicate_status === 'exact_match_existing_rule').length}
                </span>
              )}
            </div>
          </div>

          {/* Fila 2: Filtros de Completitud y Revisión Ortogonales */}
          <div className="flex items-center justify-between flex-wrap gap-2 pt-1 border-t border-slate-800/40">
            <div className="flex items-center space-x-1.5 overflow-x-auto py-0.5">
              <span className="text-xs font-semibold text-slate-400 flex items-center gap-1 mr-1">
                <Layers className="w-3 h-3 text-slate-500" /> Completitud:
              </span>
              <button
                onClick={() => setCompletenessFilter('all')}
                className={`px-2 py-0.5 text-[11px] font-medium rounded transition-all ${completenessFilter === 'all' ? 'bg-slate-700 text-white font-semibold' : 'bg-slate-800/80 text-slate-400 hover:text-slate-200'}`}
              >
                Todas ({items.length})
              </button>
              <button
                onClick={() => setCompletenessFilter('complete')}
                className={`px-2 py-0.5 text-[11px] font-medium rounded transition-all ${completenessFilter === 'complete' ? 'bg-emerald-900 text-emerald-200 border border-emerald-700 font-semibold' : 'bg-slate-800/80 text-emerald-400 hover:bg-slate-800'}`}
              >
                🟢 Completos ({items.filter((i) => i.completeness_status === 'complete').length})
              </button>
              <button
                onClick={() => setCompletenessFilter('partial')}
                className={`px-2 py-0.5 text-[11px] font-medium rounded transition-all ${completenessFilter === 'partial' ? 'bg-amber-900 text-amber-200 border border-amber-700 font-semibold' : 'bg-slate-800/80 text-amber-400 hover:bg-slate-800'}`}
              >
                🟡 Parciales ({items.filter((i) => i.completeness_status === 'partial').length})
              </button>
              <button
                onClick={() => setCompletenessFilter('missing_data')}
                className={`px-2 py-0.5 text-[11px] font-medium rounded transition-all ${completenessFilter === 'missing_data' ? 'bg-rose-900 text-rose-200 border border-rose-700 font-semibold' : 'bg-slate-800/80 text-rose-400 hover:bg-slate-800'}`}
              >
                🔴 Faltan Datos ({items.filter((i) => i.completeness_status === 'missing_data' || !i.completeness_status).length})
              </button>
              <button
                onClick={() => setCompletenessFilter('web_suggested')}
                className={`px-2 py-0.5 text-[11px] font-medium rounded transition-all ${completenessFilter === 'web_suggested' ? 'bg-sky-900 text-sky-200 border border-sky-700 font-semibold' : 'bg-slate-800/80 text-sky-400 hover:bg-slate-800'}`}
              >
                ✨ Con Sugerencia ({items.filter((i) => i.completeness_status === 'web_suggested' || i.enrichment_status === 'suggestion_found').length})
              </button>
            </div>

            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span className="text-[11px] text-slate-500 font-medium">
                Completitud General: <strong className="text-slate-300">{items.length > 0 ? Math.round((items.filter((i) => i.completeness_status === 'complete').length / items.length) * 100) : 0}%</strong>
              </span>
            </div>
          </div>

          {/* Fila 3: Controles de Traducción IA Granular y Tri-State Viewer */}
          <div className="flex items-center justify-between flex-wrap gap-2 pt-2 border-t border-slate-800/60">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-semibold text-slate-300 flex items-center gap-1">
                <Globe className="w-3.5 h-3.5 text-sky-400" /> Vista de Idioma:
              </span>
              <div className="inline-flex rounded-lg bg-slate-950 p-0.5 border border-slate-800 text-xs">
                <button
                  type="button"
                  onClick={() => setTranslationViewMode('original')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    translationViewMode === 'original'
                      ? 'bg-slate-800 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Original
                </button>
                <button
                  type="button"
                  onClick={() => setTranslationViewMode('translation')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    translationViewMode === 'translation'
                      ? 'bg-sky-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Traducción
                </button>
                <button
                  type="button"
                  onClick={() => setTranslationViewMode('both')}
                  className={`px-2.5 py-1 rounded-md font-medium transition-all ${
                    translationViewMode === 'both'
                      ? 'bg-indigo-600 text-white shadow-sm'
                      : 'text-slate-400 hover:text-slate-200'
                  }`}
                >
                  Original + Traducción
                </button>
              </div>

              <select
                value={selectedTargetLang}
                onChange={(e) => setSelectedTargetLang(e.target.value)}
                className="text-xs bg-slate-950 border border-slate-800 text-slate-200 rounded-lg px-2 py-1 focus:outline-none focus:border-sky-500"
              >
                <option value="es">Destino: Español (ES)</option>
                <option value="en">Destino: Inglés (EN)</option>
                <option value="pt">Destino: Portugués (PT)</option>
              </select>
            </div>

            <div className="flex items-center gap-2">
              <button
                type="button"
                disabled={selectedItemIds.size === 0 || translatingBatch}
                onClick={handleTranslateSelected}
                className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  selectedItemIds.size === 0 || translatingBatch
                    ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                    : 'bg-sky-600 hover:bg-sky-500 text-white shadow-sm'
                }`}
                title="Traducir únicamente los elementos seleccionados mediante casillas"
              >
                {translatingBatch ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
                <span>Traducir selección ({selectedItemIds.size})</span>
              </button>

              <button
                type="button"
                disabled={items.length === 0 || translatingBatch}
                onClick={handleTranslateDocument}
                className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 transition-all"
                title="Traducir todos los elementos de este documento bajo demanda"
              >
                {translatingBatch ? <Loader2 className="w-3 h-3 animate-spin" /> : <Globe className="w-3 h-3 text-sky-400" />}
                <span>Traducir documento completo</span>
              </button>
            </div>
          </div>
        </div>

        {/* Lista de Elementos Extraídos */}
        <div className="p-6 overflow-y-auto space-y-3.5 flex-1 max-h-[calc(92vh-220px)]">
          {error && (
            <div className="p-3 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {loading ? (
            <div className="p-12 text-center text-slate-400 text-sm">
              Cargando elementos estructurados del documento...
            </div>
          ) : filteredItems.length === 0 ? (
            <div className="p-12 text-center text-slate-500 text-sm">
              No hay elementos en esta combinación de filtros.
            </div>
          ) : (
            filteredItems.map((item) => {
              const badge = getItemTypeBadge(item.item_type, item.item_nature, item.source_origin, item);
              const isAccepted = item.review_status === 'accepted';
              const isRejected = item.review_status === 'rejected';
              const isWebItem = item.source_origin === 'web';
              const isExactDuplicate = item.blocked_from_acceptance || item.duplicate_status === 'exact_match_existing_rule';
              const isLikelyDuplicate = item.duplicate_status === 'likely_duplicate_existing_rule';
              const isRelatedRule = item.duplicate_status === 'related_existing_rule';

              return (
                <div
                  key={item.id}
                  className={`p-4 rounded-xl border transition-all ${
                    isExactDuplicate
                      ? 'bg-rose-950/20 border-rose-800/60 shadow-sm shadow-rose-950/30'
                      : isAccepted
                      ? isWebItem
                        ? 'bg-slate-900/90 border-indigo-800/50 shadow-sm shadow-indigo-950/30'
                        : 'bg-slate-900/90 border-emerald-800/40'
                      : isRejected
                      ? 'bg-slate-950/40 border-slate-800 opacity-60'
                      : isWebItem
                      ? 'bg-slate-900/90 border-indigo-900/40'
                      : 'bg-slate-900/90 border-slate-800'
                  }`}
                >
                  <div className="flex items-start justify-between gap-4">
                    {/* Checkbox de selección de item para lote */}
                    <input
                      type="checkbox"
                      checked={selectedItemIds.has(item.id)}
                      onChange={(e) => {
                        setSelectedItemIds((prev) => {
                          const next = new Set(prev);
                          if (e.target.checked) next.add(item.id);
                          else next.delete(item.id);
                          return next;
                        });
                      }}
                      className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-sky-600 focus:ring-sky-500 shrink-0 mt-1 cursor-pointer"
                      title="Seleccionar para traducción o acción por lote"
                    />

                    {/* Contenido Principal */}
                    <div className="space-y-2 flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        
                        {/* Tipo de Elemento */}
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border uppercase tracking-wider ${badge.bg}`}>
                          {badge.label}
                        </span>

                        {/* Badge de Procedencia Celda de Tabla */}
                        {((item as any).source_table_id || item.metadata_payload?.source_table_id || item.metadata_payload?.row_index !== undefined) && (
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-700/70 flex items-center gap-1 shadow-sm">
                            📊 Celda de Tabla: Fila {(item.metadata_payload?.row_index ?? (item as any).row_index ?? 0) + 1}, Col {(item.metadata_payload?.col_index ?? (item as any).col_index ?? 0) + 1}
                          </span>
                        )}

                        {/* Orientación detectada y confianza (Condición 1) */}
                        {(item.reading_orientation || item.orientation || item.metadata_payload?.reading_orientation || item.metadata_payload?.orientation) && (
                          <span
                            className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-cyan-950 text-cyan-300 border border-cyan-700/70 flex items-center gap-1 shadow-sm"
                            title={item.orientation_reason || item.metadata_payload?.orientation_reason || `Sentido: ${item.reading_orientation || item.orientation || item.metadata_payload?.reading_orientation}`}
                          >
                            🧭 Sentido: {
                              (item.reading_orientation || item.orientation || item.metadata_payload?.reading_orientation || item.metadata_payload?.orientation) === 'row_major'
                                ? 'Horizontal (Filas)'
                                : (item.reading_orientation || item.orientation || item.metadata_payload?.reading_orientation || item.metadata_payload?.orientation) === 'col_major'
                                ? 'Vertical (Columnas)'
                                : (item.reading_orientation || item.orientation || item.metadata_payload?.reading_orientation || item.metadata_payload?.orientation) === 'mixed'
                                ? 'Mixto'
                                : 'Indeterminado'
                            } ({Math.round(((item.orientation_confidence ?? item.metadata_payload?.orientation_confidence ?? 1.0)) * 100)}%)
                          </span>
                        )}

                        {/* Alerta de Orientación Incierta / Revisión Humana Obligatoria (Condición 5) */}
                        {(item.requires_human_review || item.metadata_payload?.requires_human_review || ((item.orientation_confidence ?? item.metadata_payload?.orientation_confidence ?? 1.0) < 0.60)) && (
                          <span
                            className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-amber-950 text-amber-300 border border-amber-600 flex items-center gap-1 shadow-sm animate-pulse"
                            title={item.orientation_reason || item.metadata_payload?.orientation_reason || 'Orientación con confianza insuficiente (<60%). Requiere revisión humana obligatoria.'}
                          >
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            <span>Requiere Revisión Humana (Orientación Incierta)</span>
                          </span>
                        )}

                        {/* Badge Inner Drawing BBox (Condición 3) */}
                        {(item.inner_drawing_bbox || item.metadata_payload?.inner_drawing_bbox) && (
                          <span
                            className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700 flex items-center gap-1"
                            title={`Inner Drawing BBox: [${(item.inner_drawing_bbox || item.metadata_payload?.inner_drawing_bbox).map((v: number) => v.toFixed(3)).join(', ')}]`}
                          >
                            📐 Trazo Interno
                          </span>
                        )}

                        {item.metadata_payload?.semantic_association_mode && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-300 border border-slate-700">
                            Contexto: {item.metadata_payload.semantic_association_mode === 'right_text_and_column_header' ? 'Derecha + Superior' : item.metadata_payload.semantic_association_mode}
                          </span>
                        )}

                        {/* Badge de Procedencia por Item */}
                        {isWebItem ? (
                          <>
                            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-800/80 flex items-center gap-1">
                              <Globe className="w-3 h-3 text-indigo-400" /> Búsqueda Web
                            </span>
                            {/* Badges de Calidad y Tipo de Fuente */}
                            {item.metadata_payload?.source_quality_tier === 'manufacturer' ? (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-950/90 text-purple-300 border border-purple-700/70 flex items-center gap-1 shadow-sm">
                                🏭 Fabricante / Catálogo
                              </span>
                            ) : item.metadata_payload?.source_quality_tier === 'educational' ? (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sky-950/90 text-sky-300 border border-sky-700/70 flex items-center gap-1 shadow-sm">
                                🎓 Doc. Académico
                              </span>
                            ) : item.metadata_payload?.source_quality_tier === 'official' || item.metadata_payload?.is_official_source === true ? (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-950/90 text-teal-300 border border-teal-700/70 flex items-center gap-1 shadow-sm">
                                🏛️ Fuente Oficial
                              </span>
                            ) : (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-950/90 text-amber-300 border border-amber-700/70 flex items-center gap-1 shadow-sm">
                                ⚠️ Fuente secundaria
                              </span>
                            )}
                            {(item.metadata_payload?.is_official_source === false || item.requires_validation) && (
                              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-900/40 text-amber-200 border border-amber-800/60 flex items-center gap-1">
                                ⚠️ Requiere validación
                              </span>
                            )}
                          </>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-teal-950/80 text-teal-300 border border-teal-800/80 flex items-center gap-1">
                            <FileText className="w-3 h-3 text-teal-400" /> Documento
                          </span>
                        )}

                        {/* BADGES DE DEDUPLICACIÓN ESTRICTA */}
                        {isExactDuplicate && (
                          <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-rose-950 text-rose-300 border border-rose-700 flex items-center gap-1 shadow-sm">
                            <Ban className="w-3 h-3 text-rose-400" />
                            <span>YA EXISTE EN MOTOR DE REGLAS QA/QC</span>
                          </span>
                        )}

                        {isLikelyDuplicate && (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-950/90 text-amber-300 border border-amber-700/80 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3 text-amber-400" />
                            <span>Posible Duplicado ({Math.round((item.duplicate_confidence || 0) * 100)}%)</span>
                          </span>
                        )}

                        {isRelatedRule && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-sky-950/80 text-sky-300 border border-sky-800/60">
                            Relacionada con Motor QA/QC
                          </span>
                        )}

                        {item.code_or_number && (
                          <span className="font-mono text-xs font-bold text-teal-400">
                            {item.code_or_number}
                          </span>
                        )}

                        {/* Badges de Grilla Física y Clasificación Granular */}
                        {(item.content_class || item.metadata_payload?.content_class) && (
                          <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                            (item.content_class || item.metadata_payload?.content_class) === 'figure'
                              ? 'bg-violet-950 text-violet-300 border-violet-700'
                              : (item.content_class || item.metadata_payload?.content_class) === 'table_graphic'
                              ? 'bg-cyan-950 text-cyan-300 border-cyan-700'
                              : (item.content_class || item.metadata_payload?.content_class) === 'text_only'
                              ? 'bg-slate-900 text-slate-400 border-slate-700'
                              : (item.content_class || item.metadata_payload?.content_class) === 'mixed'
                              ? 'bg-amber-950 text-amber-300 border-amber-700'
                              : 'bg-purple-950 text-purple-300 border-purple-700'
                          }`}>
                            Clase: {item.content_class || item.metadata_payload?.content_class}
                          </span>
                        )}

                        {(item.geometric_confidence !== undefined || item.metadata_payload?.geometric_confidence !== undefined) && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                            Conf. Geométrica: {Math.round(((item.geometric_confidence ?? item.metadata_payload?.geometric_confidence ?? 0)) * 100)}%
                          </span>
                        )}

                        {(item.grid_source || item.metadata_payload?.grid_source) && (
                          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                            Grilla: {item.grid_source || item.metadata_payload?.grid_source}
                          </span>
                        )}
                        
                        {/* Destino Badge */}
                        <span className="text-[10px] text-slate-400 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700">
                          Destino: {item.target_destination === 'both' ? 'Reglas + Base Conocimiento' : item.target_destination === 'knowledge_base' ? 'Base de Conocimiento' : 'Motor de Reglas'}
                        </span>

                        {/* Badge de Estado de Completitud */}
                        {item.completeness_status === 'complete' ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-950/90 text-emerald-300 border border-emerald-700/70 flex items-center gap-1 shadow-sm">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400" /> Completo
                          </span>
                        ) : item.completeness_status === 'needs_visual_crop' ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-950/90 text-rose-300 border border-rose-700/70 flex items-center gap-1 shadow-sm" title="Falta recorte visual comprobable en disco">
                            <AlertTriangle className="w-3 h-3 text-rose-400" /> Falta Recorte Visual
                          </span>
                        ) : item.completeness_status === 'partial' ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-amber-950/90 text-amber-300 border border-amber-700/70 flex items-center gap-1 shadow-sm">
                            <AlertTriangle className="w-3 h-3 text-amber-400" /> Parcial
                          </span>
                        ) : item.completeness_status === 'web_suggested' || item.enrichment_status === 'suggestion_found' ? (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-sky-950/90 text-sky-300 border border-sky-700/70 flex items-center gap-1 shadow-sm">
                            <Sparkles className="w-3 h-3 text-sky-400" /> Sugerencia IA ({Math.round((item.match_confidence || 0.8) * 100)}%)
                          </span>
                        ) : (
                          <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-rose-950/90 text-rose-300 border border-rose-700/70 flex items-center gap-1 shadow-sm">
                            <HelpCircle className="w-3 h-3 text-rose-400" /> Datos faltantes
                          </span>
                        )}
                      </div>

                      {/* TÍTULO Y DESCRIPCIÓN CON SOPORTE TRI-STATE Y RESOLVER UNIFICADO */}
                      {(() => {
                        const tr = translationsCache[item.id] || item.translated_fields;
                        const hasTrans = hasActiveTranslation(item, tr);
                        const titleField = getDisplayField(item, 'title', translationViewMode, tr);
                        const descField = getDisplayField(item, 'description', translationViewMode, tr);

                        if (translationViewMode === 'original') {
                          const origTitle = titleField.original || item.source_fields?.title || item.title;
                          const origDesc = descField.original || item.source_fields?.description || item.description;
                          return (
                            <div className="space-y-1.5 w-full">
                              <div className="flex items-center gap-2">
                                <h4 className="text-sm font-bold text-slate-100">{origTitle}</h4>
                                {hasTrans && (
                                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800">
                                    Traducción disponible ({selectedTargetLang.toUpperCase()})
                                  </span>
                                )}
                              </div>
                              {origDesc && (
                                <p className="text-xs text-slate-300 leading-relaxed">
                                  {origDesc}
                                </p>
                              )}
                            </div>
                          );
                        }

                        if (translationViewMode === 'translation') {
                          const displayTitle = hasTrans ? (titleField.translated || titleField.value) : (titleField.original || item.title);
                          const displayDesc = hasTrans ? (descField.translated || descField.value) : (descField.original || item.description);

                          return (
                            <div className="space-y-1.5 w-full">
                              <div className="flex items-center gap-2">
                                <h4 className={`text-sm font-bold ${hasTrans ? 'text-sky-200' : 'text-slate-200'}`}>{displayTitle}</h4>
                                {hasTrans ? (
                                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded bg-sky-900/80 text-sky-300 border border-sky-600 flex items-center gap-1">
                                    <Sparkles className="w-2.5 h-2.5" /> IA Traducido ({selectedTargetLang.toUpperCase()})
                                  </span>
                                ) : (
                                  <span className="text-[9px] font-medium px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                                    Traducción pendiente/no disponible
                                  </span>
                                )}
                              </div>
                              {displayDesc && (
                                <p className={`text-xs leading-relaxed ${hasTrans ? 'text-slate-200' : 'text-slate-400'}`}>
                                  {displayDesc}
                                </p>
                              )}
                            </div>
                          );
                        }

                        // Mode: both (Original + Traducción) -> dos bloques reales sin concatenar ni repetir OCR
                        const origTitle = titleField.original || item.source_fields?.title || item.title;
                        const origDesc = descField.original || item.source_fields?.description || item.description;
                        const transTitle = hasTrans ? (titleField.translated || titleField.value) : '';
                        const transDesc = hasTrans ? (descField.translated || descField.value) : '';

                        return (
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 w-full">
                            <div className="p-2.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-1">
                              <span className="text-[9px] font-bold uppercase tracking-wider text-slate-400 block">
                                Texto Original ({item.source_language?.toUpperCase() || 'EN'}):
                              </span>
                              <h4 className="text-xs font-semibold text-slate-200">{origTitle}</h4>
                              {origDesc && (
                                <p className="text-xs text-slate-400 leading-relaxed">
                                  {origDesc}
                                </p>
                              )}
                            </div>
                            <div className="p-2.5 rounded-xl bg-sky-950/40 border border-sky-900/60 space-y-1">
                              <span className="text-[9px] font-bold uppercase tracking-wider text-sky-400 flex items-center gap-1">
                                <Sparkles className="w-2.5 h-2.5" /> Traducción ({selectedTargetLang.toUpperCase()}):
                              </span>
                              {hasTrans ? (
                                <>
                                  <h4 className="text-xs font-semibold text-sky-200">{transTitle}</h4>
                                  {transDesc && (
                                    <p className="text-xs text-sky-100/90 leading-relaxed">
                                      {transDesc}
                                    </p>
                                  )}
                                </>
                              ) : (
                                <p className="text-xs text-slate-500 italic">
                                  Traducción pendiente/no disponible
                                </p>
                              )}
                            </div>
                          </div>
                        );
                      })()}

                      {/* Metadatos Geométricos Auditables */}
                      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-400 font-mono pt-1">
                        {(item.cell_bbox || item.metadata_payload?.cell_bbox) && (
                          <span>cell_bbox: [{(item.cell_bbox || item.metadata_payload?.cell_bbox).map((n: number) => n.toFixed(3)).join(', ')}]</span>
                        )}
                        {(item.inner_drawing_bbox || item.metadata_payload?.inner_drawing_bbox) && (
                          <span>inner_drawing: [{(item.inner_drawing_bbox || item.metadata_payload?.inner_drawing_bbox).map((n: number) => n.toFixed(3)).join(', ')}]</span>
                        )}
                        {(item.symbol_crop_bbox || item.metadata_payload?.symbol_crop_bbox) && (
                          <span>crop_bbox: [{(item.symbol_crop_bbox || item.metadata_payload?.symbol_crop_bbox).map((n: number) => n.toFixed(3)).join(', ')}]</span>
                        )}
                        {(item.boundary_evidence || item.metadata_payload?.boundary_evidence) && (
                          <span>
                            bordes: T:{(item.boundary_evidence || item.metadata_payload?.boundary_evidence)?.top ? '✓' : '✗'} B:{(item.boundary_evidence || item.metadata_payload?.boundary_evidence)?.bottom ? '✓' : '✗'} L:{(item.boundary_evidence || item.metadata_payload?.boundary_evidence)?.left ? '✓' : '✗'} R:{(item.boundary_evidence || item.metadata_payload?.boundary_evidence)?.right ? '✓' : '✗'}
                          </span>
                        )}
                      </div>

                      {/* Recorte visual (Thumbnail para símbolos reales) */}
                      {item.crop_image_path && (
                        <div className="mt-2 flex items-center gap-2">
                          <img
                            src={item.crop_image_path.startsWith('http') ? item.crop_image_path : `/api/v1/storage/${item.crop_image_path.replace(/^\/+/, '')}`}
                            alt={item.title}
                            className="w-14 h-14 object-contain bg-white rounded-lg border border-slate-700 p-0.5 shrink-0 shadow-sm"
                            onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }}
                          />
                          <span className="text-[10px] text-slate-500 font-mono truncate max-w-xs">{item.crop_image_path.split('/').pop()}</span>
                        </div>
                      )}

                      {/* Ocurrencias Multipágina / Multicelda para Símbolos Canónicos (Condición 4) */}
                      {((item.occurrences && item.occurrences.length > 0) || (item.metadata_payload?.occurrences && item.metadata_payload.occurrences.length > 0)) && (
                        <div className="mt-2.5 p-2.5 rounded-xl bg-slate-950/80 border border-slate-800 space-y-1.5">
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-[11px] font-bold text-slate-300 flex items-center gap-1.5">
                              <Layers className="w-3.5 h-3.5 text-teal-400" />
                              <span>Ocurrencias del Símbolo en Documento ({(item.occurrences || item.metadata_payload?.occurrences).length}):</span>
                            </span>
                            <span className="text-[10px] text-slate-500 font-medium">
                              Clic en cualquier página para ver su contexto y lámina
                            </span>
                          </div>

                          <div className="flex items-center gap-1.5 flex-wrap pt-0.5">
                            {(item.occurrences || item.metadata_payload?.occurrences).map((occ: any, idx: number) => {
                              const isPrincipal = occ.is_primary || (occ.page_number === item.page_number && idx === 0);
                              return (
                                <button
                                  key={occ.occurrence_id || `occ_${idx}`}
                                  type="button"
                                  onClick={() => handleOpenOccurrenceContext(item, occ)}
                                  className={`px-2.5 py-1 text-xs font-semibold rounded-lg border transition-all flex items-center gap-1.5 shadow-sm active:scale-95 ${
                                    isPrincipal
                                      ? 'bg-teal-950 text-teal-200 border-teal-600 hover:bg-teal-900'
                                      : 'bg-slate-900 text-cyan-300 border-slate-700 hover:bg-cyan-950 hover:border-cyan-600'
                                  }`}
                                  title={`Abrir visor de contexto en Pág. ${occ.page_number} (${occ.source_reference || 'Celda tabular'})`}
                                >
                                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                                  <span>Pág. {occ.page_number}{isPrincipal ? ' (Principal)' : ''}</span>
                                  {occ.row_index !== undefined && occ.col_index !== undefined && (
                                    <span className="text-[10px] px-1 py-0.2 rounded bg-slate-800/90 text-slate-300 font-mono">
                                      F{occ.row_index + 1}C{occ.col_index + 1}
                                    </span>
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      )}

                      {/* Alerta de Recorte Requerido para Símbolos */}
                      {isSymbolItem(item) && (item.completeness_status === 'needs_visual_crop' || (!item.crop_image_path && !(item as any).thumbnail_url)) && (
                        <div className="mt-2 p-2.5 rounded-xl bg-rose-950/30 border border-rose-800/60 text-xs flex items-center gap-2 text-rose-300">
                          <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0" />
                          <div>
                            <span className="font-bold">Recorte visual requerido:</span>
                            <span className="text-rose-200/90 ml-1">
                              Todo símbolo catalogado requiere imagen física verificada en disco ({(item as any).crop_error_reason || item.metadata_payload?.crop_error_reason || 'Sin crop en disco'}).
                            </span>
                          </div>
                        </div>
                      )}

                      {/* BANNER DE SUGERENCIA Y ACEPTACIÓN PARCIAL POR CAMPO */}
                      {(item.suggested_title || item.suggested_description || item.suggested_function) && (
                        <div className="mt-2 p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 text-xs space-y-2 shadow-sm">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-1.5 text-sky-300 font-bold text-[11px]">
                              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                              <span>Sugerencias Disponibles ({Math.round((item.match_confidence || 0.8) * 100)}% Confianza)</span>
                            </div>
                            {!readOnly && (
                              <button
                                type="button"
                                onClick={() => handleApplySuggestion(item)}
                                className="px-2.5 py-0.5 text-[10.5px] font-bold text-slate-950 bg-sky-400 hover:bg-sky-300 rounded shadow flex items-center gap-1 transition-all active:scale-95"
                              >
                                <ArrowDownToLine className="w-3 h-3" />
                                Aplicar Todo
                              </button>
                            )}
                          </div>

                          <div className="space-y-1.5 text-[11px]">
                            {item.suggested_title && (
                              <div className="flex items-center justify-between gap-2 p-1.5 rounded bg-slate-900/70 border border-slate-800">
                                <div className="min-w-0 flex-1">
                                  <span className="text-sky-400 font-mono text-[10px] font-bold mr-1.5">TÍTULO:</span>
                                  <span className="text-slate-200">{item.suggested_title}</span>
                                </div>
                                {!readOnly && (
                                  <button
                                    type="button"
                                    disabled={fieldPatchingId === `${item.id}_title`}
                                    onClick={() => handleAcceptField(item, 'title', item.suggested_title!)}
                                    className="px-2 py-0.5 text-[10px] font-semibold text-sky-300 bg-sky-950 hover:bg-sky-900 border border-sky-700 rounded transition-all flex items-center gap-1"
                                    title="Aplicar solo este título"
                                  >
                                    <Check className="w-2.5 h-2.5" /> Aplicar
                                  </button>
                                )}
                              </div>
                            )}

                            {item.suggested_description && (
                              <div className="flex items-start justify-between gap-2 p-1.5 rounded bg-slate-900/70 border border-slate-800">
                                <div className="min-w-0 flex-1">
                                  <span className="text-sky-400 font-mono text-[10px] font-bold mr-1.5">DESCRIPCIÓN:</span>
                                  <span className="text-slate-200">{item.suggested_description}</span>
                                </div>
                                {!readOnly && (
                                  <button
                                    type="button"
                                    disabled={fieldPatchingId === `${item.id}_description`}
                                    onClick={() => handleAcceptField(item, 'description', item.suggested_description!)}
                                    className="px-2 py-0.5 text-[10px] font-semibold text-sky-300 bg-sky-950 hover:bg-sky-900 border border-sky-700 rounded transition-all flex items-center gap-1 shrink-0"
                                    title="Aplicar solo esta descripción"
                                  >
                                    <Check className="w-2.5 h-2.5" /> Aplicar
                                  </button>
                                )}
                              </div>
                            )}

                            {item.suggested_function && (
                              <div className="flex items-start justify-between gap-2 p-1.5 rounded bg-slate-900/70 border border-slate-800">
                                <div className="min-w-0 flex-1">
                                  <span className="text-sky-400 font-mono text-[10px] font-bold mr-1.5">FUNCIÓN:</span>
                                  <span className="text-slate-200">{item.suggested_function}</span>
                                </div>
                                {!readOnly && (
                                  <button
                                    type="button"
                                    disabled={fieldPatchingId === `${item.id}_function`}
                                    onClick={() => handleAcceptField(item, 'function', item.suggested_function!)}
                                    className="px-2 py-0.5 text-[10px] font-semibold text-sky-300 bg-sky-950 hover:bg-sky-900 border border-sky-700 rounded transition-all flex items-center gap-1 shrink-0"
                                    title="Aplicar solo esta función"
                                  >
                                    <Check className="w-2.5 h-2.5" /> Aplicar
                                  </button>
                                )}
                              </div>
                            )}
                          </div>

                          {item.suggested_source_url && (
                            <a
                              href={item.suggested_source_url}
                              target="_blank"
                              rel="noreferrer"
                              className="inline-flex items-center gap-1 text-[10px] text-sky-400 hover:text-sky-300 underline font-medium pt-0.5"
                            >
                              <ExternalLink className="w-3 h-3" />
                              {item.suggested_source_label || 'Fuente de Referencia Técnica'}
                            </a>
                          )}
                        </div>
                      )}

                      {/* CUADRO DE REFERENCIA DE REGLA EXISTENTE EN MOTOR QA/QC (SI ES DUPLICADO) */}
                      {isExactDuplicate && (
                        <div className="mt-2 p-2.5 rounded-xl bg-rose-950/40 border border-rose-800/70 text-xs space-y-1">
                          <div className="flex items-center gap-1.5 text-rose-300 font-bold">
                            <ShieldX className="w-4 h-4 text-rose-400 shrink-0" />
                            <span>Bloqueada para Aceptación: Ya existe en el Motor de Reglas QA/QC</span>
                          </div>
                          <div className="text-[11px] text-slate-200">
                            <span className="text-slate-400">Regla existente:</span>{' '}
                            <strong className="font-mono text-teal-300">{item.best_match_rule_code || 'REG-EXISTENTE'}</strong> - {item.best_match_title || 'Regla en Motor QA/QC'}
                            {item.best_match_discipline && <span className="text-slate-400"> ({item.best_match_discipline})</span>}
                          </div>
                          {item.duplicate_reason && (
                            <div className="text-[10.5px] text-slate-300 italic">
                              {item.duplicate_reason}
                            </div>
                          )}
                        </div>
                      )}

                      {isLikelyDuplicate && (
                        <div className="mt-2 p-2 rounded-xl bg-amber-950/30 border border-amber-800/50 text-xs space-y-1">
                          <div className="flex items-center gap-1.5 text-amber-300 font-semibold">
                            <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                            <span>Posible duplicado detectado en Motor QA/QC:</span>
                          </div>
                          <div className="text-[11px] text-slate-300">
                            <span className="text-slate-400">Regla similar:</span>{' '}
                            <strong className="font-mono text-amber-300">{item.best_match_rule_code}</strong> - {item.best_match_title}
                            {item.best_match_discipline && <span className="text-slate-400"> ({item.best_match_discipline})</span>}
                          </div>
                          {item.duplicate_reason && (
                            <div className="text-[10.5px] text-slate-400 italic">
                              {item.duplicate_reason}
                            </div>
                          )}
                        </div>
                      )}

                      {/* Enlace o Referencia Normativa si existe */}
                      {item.source_reference && (
                        <div className="flex items-center gap-1.5 text-[11px] text-indigo-300 bg-indigo-950/40 px-2.5 py-1 rounded-lg border border-indigo-800/40 w-fit mt-1">
                          <Link2 className="w-3 h-3 text-indigo-400" />
                          <span className="font-medium">Referencia / Enlace:</span>
                          <span className="font-mono text-[10px] text-indigo-200">{item.source_reference}</span>
                        </div>
                      )}

                      {/* Nota de Gobernanza si existe */}
                      {item.governance_note && (
                        <div className="text-[10.5px] text-amber-300/90 italic flex items-center gap-1 mt-0.5">
                          <ShieldAlert className="w-3 h-3 text-amber-400 shrink-0" />
                          <span>{item.governance_note}</span>
                        </div>
                      )}

                      {/* OCR Text si aplica */}
                      {item.ocr_text && (
                        <div className="p-2 rounded-lg bg-slate-950/80 border border-slate-800/70 text-[11px] font-mono text-slate-400">
                          <span className="text-[10px] text-teal-500 font-bold block mb-0.5">OCR EXTRAÍDO:</span>
                          {item.ocr_text}
                        </div>
                      )}

                      {/* Recorte o Imagen si existe con Lightbox Click */}
                      {item.crop_image_path && (
                        <div className="mt-2.5 p-2 rounded-xl bg-slate-950/90 border border-slate-800 flex flex-col sm:flex-row items-start sm:items-center gap-3">
                          <div 
                            className="relative group cursor-zoom-in overflow-hidden rounded-lg border border-slate-750 bg-slate-900 p-1 shrink-0"
                            onClick={() => setLightboxItem(item)}
                            title="Hacer click para ampliar recorte en Lightbox (3x)"
                          >
                            <img
                              src={item.crop_image_path.startsWith('http') || item.crop_image_path.startsWith('data:') ? item.crop_image_path : (item.crop_image_path.startsWith('/') ? item.crop_image_path : `/${item.crop_image_path}`)}
                              alt={item.title}
                              className="max-h-28 max-w-full sm:max-w-xs rounded object-contain transition-transform group-hover:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1 text-cyan-300 text-[10.5px] font-semibold transition-opacity rounded">
                              <Maximize2 className="w-4 h-4" />
                              <span>Ampliación 3x</span>
                            </div>
                          </div>

                          <div className="text-[11px] text-slate-300 space-y-1">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold text-teal-400">Evidencia Visual • Pág. {item.page_number || 1}</span>
                              <button
                                type="button"
                                onClick={() => setLightboxItem(item)}
                                className="text-[10.5px] text-cyan-400 hover:text-cyan-300 underline font-medium flex items-center gap-1"
                              >
                                <Maximize2 className="w-3 h-3" /> Ampliar
                              </button>
                            </div>
                            {item.caption_or_context && (
                              <div className="text-slate-400 text-[10.5px]">
                                <span className="text-slate-300 font-medium">Contexto:</span> {item.caption_or_context}
                              </div>
                            )}
                            {item.disclaimer_notes && (
                              <div className="text-[10px] text-amber-300/80 italic">
                                {item.disclaimer_notes}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Acciones de Validación y Revisión Asistida */}
                    <div className="flex flex-col sm:flex-row items-end sm:items-center gap-1.5 shrink-0">
                      {/* Botón Traducir Elemento */}
                      <button
                        type="button"
                        onClick={() => handleTranslateSingleItem(item)}
                        disabled={translatingItemIds.has(item.id)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-sky-950/80 text-sky-300 hover:bg-sky-900 border border-sky-700/80 flex items-center gap-1.5 shadow-sm disabled:opacity-50 transition-all active:scale-95"
                        title="Traducir este elemento individualmente bajo demanda"
                      >
                        {translatingItemIds.has(item.id) ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin text-sky-400" />
                        ) : (
                          <Globe className="w-3.5 h-3.5 text-sky-400" />
                        )}
                        <span>Traducir</span>
                      </button>

                      {/* Botón Ver Contexto */}
                      <button
                        type="button"
                        onClick={() => setContextModalItem(item)}
                        className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-cyan-950/80 text-cyan-300 hover:bg-cyan-900 border border-cyan-700/80 flex items-center gap-1.5 shadow-sm transition-all active:scale-95"
                        title="Ver contexto en lámina exacta con Bounding Box y OCR"
                      >
                        <Compass className="w-3.5 h-3.5 text-cyan-400" />
                        <span>Contexto</span>
                      </button>

                      {/* Botón Buscar Referencia / Enriquecer */}
                      {!readOnly && (
                        <button
                          type="button"
                          onClick={() => handleEnrichItem(item)}
                          disabled={enrichingItemId === item.id}
                          className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-950/80 text-indigo-300 hover:bg-indigo-900 border border-indigo-700/80 flex items-center gap-1.5 shadow-sm disabled:opacity-50 transition-all active:scale-95"
                          title="Buscar referencia técnica y sugerir nombre/descripción"
                        >
                          {enrichingItemId === item.id ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          ) : (
                            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                          )}
                          <span>Buscar ref.</span>
                        </button>
                      )}

                      {!readOnly && (
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleStartEdit(item)}
                            className="p-1.5 text-slate-400 hover:text-teal-400 hover:bg-slate-800 rounded-lg transition-colors"
                            title="Editar elemento"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          
                          <button
                            disabled={isExactDuplicate}
                            onClick={() => handleStatusChange(item, isAccepted ? 'to_confirm' : 'accepted')}
                            className={`p-1.5 rounded-lg transition-colors ${
                              isExactDuplicate
                                ? 'text-slate-600 bg-slate-900/80 border border-slate-800 cursor-not-allowed opacity-40'
                                : isAccepted
                                ? 'text-emerald-400 bg-emerald-950/50 border border-emerald-800'
                                : 'text-slate-400 hover:text-emerald-400 hover:bg-slate-800'
                            }`}
                            title={
                              isExactDuplicate
                                ? 'Acción deshabilitada: Ya existe en Motor de Reglas QA/QC'
                                : isAccepted
                                ? 'Aceptado (clic para desmarcar)'
                                : 'Aceptar elemento'
                            }
                          >
                            <Check className="w-4 h-4" />
                          </button>

                          <button
                            onClick={() => handleDeleteItem(item.id)}
                            className="p-1.5 text-slate-400 hover:text-rose-400 hover:bg-slate-800 rounded-lg transition-colors"
                            title="Eliminar elemento"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Inline de Edición de Item */}
        {editingItem && (() => {
          const editModalDisplayTitle = getDisplayField(
            editingItem,
            'title',
            translationViewMode,
            translationsCache[editingItem.id] || editingItem.translated_fields
          ).value || editingItem.title;

          return (
            <div className="p-4 border-t border-slate-800 bg-slate-950/95 space-y-3">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-200 uppercase tracking-wide flex items-center gap-1.5">
                  <Edit3 className="w-3.5 h-3.5 text-teal-400" />
                  Editando Elemento: {editModalDisplayTitle}
                </h4>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setContextModalItem(editingItem)}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-cyan-950/80 text-cyan-300 hover:bg-cyan-900 border border-cyan-700/80 flex items-center gap-1 shadow-sm transition-all"
                  title="Abrir visor de contexto en lámina con bounding box"
                >
                  <Compass className="w-3.5 h-3.5 text-cyan-400" />
                  <span>Ver contexto en lámina</span>
                </button>

                <button
                  type="button"
                  onClick={() => handleEnrichItem(editingItem)}
                  disabled={enrichingItemId === editingItem.id}
                  className="px-2.5 py-1 text-xs font-semibold rounded-lg bg-indigo-950/80 text-indigo-300 hover:bg-indigo-900 border border-indigo-700/80 flex items-center gap-1 shadow-sm transition-all disabled:opacity-50"
                  title="Buscar referencia y sugerencias"
                >
                  {enrichingItemId === editingItem.id ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
                  )}
                  <span>Buscar ref.</span>
                </button>

                <button
                  onClick={() => setEditingItem(null)}
                  className="text-xs text-slate-400 hover:text-slate-200 ml-2"
                >
                  Cerrar edición
                </button>
              </div>
            </div>

            {/* Banner de Advertencia si está bloqueada por duplicado exacto */}
            {(editingItem.blocked_from_acceptance || editingItem.duplicate_status === 'exact_match_existing_rule') && (
              <div className="p-2.5 rounded-xl bg-rose-950/40 border border-rose-800/80 text-xs text-rose-300 flex items-center gap-2">
                <ShieldX className="w-4 h-4 text-rose-400 shrink-0" />
                <div>
                  <strong>Atención:</strong> Esta regla ya existe en el Motor de Reglas QA/QC (Código:{' '}
                  <strong className="font-mono text-teal-300">{editingItem.best_match_rule_code || 'Existente'}</strong>). Su aceptación e incorporación como nueva regla está bloqueada por política estricta de deduplicación.
                </div>
              </div>
            )}

            {/* Vista Previa Visual en Modo Edición con Click para Lightbox */}
            {editingItem.crop_image_path && (
              <div className="flex items-center gap-4 p-3 bg-slate-900 rounded-xl border border-slate-800">
                <div
                  className="relative group cursor-zoom-in overflow-hidden rounded-lg border border-slate-750 bg-slate-950 p-1 shadow shrink-0"
                  onClick={() => setLightboxItem(editingItem)}
                  title="Hacer click para ampliar recorte en Lightbox (3x)"
                >
                  <img
                    src={editingItem.crop_image_path.startsWith('http') || editingItem.crop_image_path.startsWith('data:') ? editingItem.crop_image_path : (editingItem.crop_image_path.startsWith('/') ? editingItem.crop_image_path : `/${editingItem.crop_image_path}`)}
                    alt={editingItem.title}
                    className="max-h-32 max-w-[200px] rounded object-contain transition-transform group-hover:scale-105"
                  />
                  <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 flex items-center justify-center gap-1 text-cyan-300 text-[10px] font-semibold transition-opacity rounded">
                    <Maximize2 className="w-3.5 h-3.5" />
                    <span>Ampliación 3x</span>
                  </div>
                </div>

                <div className="text-xs text-slate-300 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-teal-400">Recorte Técnico Asociado • Pág. {editingItem.page_number || 1}</span>
                    <button
                      type="button"
                      onClick={() => setLightboxItem(editingItem)}
                      className="text-[10.5px] text-cyan-400 hover:text-cyan-300 underline font-medium flex items-center gap-1"
                    >
                      <Maximize2 className="w-3 h-3" /> Ver en Lightbox
                    </button>
                  </div>
                  <div className="text-[11px] text-slate-400">Ruta: <code className="text-teal-300 font-mono text-[10px]">{editingItem.crop_image_path}</code></div>
                  {editingItem.caption_or_context && (
                    <div className="text-[11px] text-slate-300"><span className="text-slate-400">Contexto detectado:</span> {editingItem.caption_or_context}</div>
                  )}
                  {editingItem.disclaimer_notes && (
                    <div className="text-[10.5px] text-amber-300/80 italic">{editingItem.disclaimer_notes}</div>
                  )}
                </div>
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Título</label>
                <input
                  type="text"
                  value={editTitle}
                  onChange={(e) => setEditTitle(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Código / Artículo</label>
                <input
                  type="text"
                  value={editCode}
                  onChange={(e) => setEditCode(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Naturaleza del Ítem</label>
                <select
                  value={editNature}
                  onChange={(e: any) => setEditNature(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="official_rule">Regla Oficial (Documento)</option>
                  <option value="proposed_rule">Regla Propuesta (Web / Sugerida)</option>
                  <option value="support_research">Contenido de Apoyo / Parámetro</option>
                  <option value="concept">Concepto / Definición</option>
                  <option value="reference">Referencia / Enlace</option>
                </select>
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Destino</label>
                <select
                  value={editDestination}
                  onChange={(e: any) => setEditDestination(e.target.value)}
                  className="w-full px-2.5 py-1 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                >
                  <option value="rules_engine">Motor de Reglas QA/QC</option>
                  <option value="knowledge_base">Base de Conocimiento</option>
                  <option value="both">Ambos (Reglas + Conocimiento)</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Descripción o Contenido</label>
                <textarea
                  rows={2}
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  className="w-full p-2 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                />
              </div>

              <div>
                <label className="block text-[11px] font-semibold text-slate-300 mb-1">Referencia / Enlace Web (URL o Cita)</label>
                <input
                  type="text"
                  value={editSourceRef}
                  onChange={(e) => setEditSourceRef(e.target.value)}
                  className="w-full px-2.5 py-2 text-xs rounded-lg bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-teal-500"
                  placeholder="https://... o Art. 4.2.4 OGUC"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setEditingItem(null)}
                className="px-3 py-1 text-xs font-medium text-slate-400 hover:text-slate-200"
              >
                Cancelar
              </button>
              <button
                type="button"
                onClick={handleSaveEdit}
                className="px-4 py-1 text-xs font-semibold text-white bg-teal-600 hover:bg-teal-500 rounded-lg transition-all"
              >
                Guardar Cambios
              </button>
            </div>
          </div>
        );
      })()}

        {/* Footer con Acciones Finales */}
        <div className="px-6 py-4 border-t border-slate-800 bg-slate-950/80 flex items-center justify-between">
          <div className="text-xs text-slate-400">
            Total: <strong>{items.length}</strong> elementos analizados ({items.filter((i) => i.review_status === 'accepted').length} aprobados)
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium text-slate-400 hover:text-slate-200 rounded-xl"
            >
              {readOnly ? 'Cerrar' : 'Cancelar'}
            </button>

            {!readOnly && extractionId && (
              <button
                type="button"
                onClick={handleCommitAll}
                disabled={committing || items.length === 0}
                className={`px-5 py-2 text-xs font-bold text-white rounded-xl transition-all shadow-lg flex items-center space-x-2 disabled:opacity-50 ${
                  isWebExtraction
                    ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 shadow-indigo-950/50'
                    : 'bg-gradient-to-r from-teal-600 to-emerald-600 hover:from-teal-500 hover:to-emerald-500 shadow-teal-950/50'
                }`}
              >
                <CheckCircle2 className="w-4 h-4" />
                <span>
                  {committing
                    ? 'Incorporando...'
                    : isWebExtraction
                    ? 'Aceptar e Incorporar Reglas de Apoyo (Web)'
                    : 'Aceptar Todo / Incorporar a Reglas QA/QC'}
                </span>
              </button>
            )}
          </div>
        </div>

        {/* Modales de Revisión Asistida Multimodal */}
        <ItemCropLightboxModal
          isOpen={!!lightboxItem}
          item={lightboxItem}
          documentTitle={extraction?.title}
          onClose={() => setLightboxItem(null)}
          onOpenContext={(it) => setContextModalItem(it)}
        />

        <ItemContextViewerModal
          isOpen={!!contextModalItem}
          extractionId={extractionId}
          item={contextModalItem}
          onClose={() => setContextModalItem(null)}
          onItemUpdated={handleItemUpdated}
        />

        <SymbolCurationStudioModal
          isOpen={isSymbolStudioOpen}
          extractionId={extractionId}
          onClose={() => setIsSymbolStudioOpen(false)}
          onPromoted={() => {
            if (extractionId) loadExtractionData(extractionId);
          }}
        />
      </div>
    </div>
  );
};
