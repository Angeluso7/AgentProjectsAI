import { ExtractedItem } from '../types';

export type TranslationViewMode = 'original' | 'translation' | 'both';

/**
 * Deduplica frases o bloques repetidos idénticos y limpia repeticiones comunes de OCR.
 */
export function deduplicateText(text?: string | null): string {
  if (!text) return '';
  const clean = text.trim();
  if (!clean) return '';

  // Dividir por oraciones terminadas en punto
  const sentences = clean.split(/\.\s+/);
  const seen = new Set<string>();
  const deduplicated: string[] = [];

  for (const s of sentences) {
    const trimmed = s.trim();
    if (!trimmed) continue;
    const lower = trimmed.toLowerCase();
    if (!seen.has(lower)) {
      seen.add(lower);
      deduplicated.push(trimmed);
    }
  }

  const result = deduplicated.join('. ');
  return result.endsWith('.') ? result : (result ? `${result}.` : '');
}

/**
 * Elimina la repetición del título dentro del texto de la descripción.
 */
export function stripTitleFromDescription(desc?: string | null, title?: string | null): string {
  if (!desc) return '';
  if (!title) return deduplicateText(desc);

  let cleanDesc = desc.trim();
  const cleanTitle = title.trim().replace(/^[\(\[\{]\d+[\)\]\}]\s*[•\-\.]*\s*/, '').trim();

  // Si la descripción empieza con el título (o con el número de item + título)
  if (cleanTitle && cleanDesc.toLowerCase().startsWith(cleanTitle.toLowerCase())) {
    cleanDesc = cleanDesc.slice(cleanTitle.length).replace(/^[\s.:–•\-]+/, '').trim();
  }

  return deduplicateText(cleanDesc || desc);
}

/**
 * Determina si el ítem cuenta con una traducción completada y aplicada con contenido real en español.
 */
export function hasActiveTranslation(item: ExtractedItem, cacheItem?: Record<string, string>): boolean {
  // Resolver campos traducidos con prioridad a la caché fresca local
  const tr = (cacheItem && Object.keys(cacheItem).length > 0)
    ? cacheItem
    : (item.translated_fields && Object.keys(item.translated_fields).length > 0)
      ? item.translated_fields
      : (item.metadata_payload?.translated_fields && Object.keys(item.metadata_payload.translated_fields).length > 0)
        ? item.metadata_payload.translated_fields
        : null;

  const status = item.translation_status || item.metadata_payload?.translation_status;

  if (!tr || Object.keys(tr).length === 0 || status === 'failed' || status === 'stale') {
    return false;
  }

  // Verificar si hay campos con contenido
  const hasValues = Boolean(
    (tr.title && tr.title.trim()) ||
    (tr.description && tr.description.trim()) ||
    (tr.content_text && tr.content_text.trim())
  );
  if (!hasValues) return false;

  // Comparar contra el texto original para no considerar como traducido un texto que sigue 100% en inglés
  const origTitle = (item.source_fields?.title || item.title || '').trim().toLowerCase();
  const origDesc = (item.source_fields?.description || item.description || item.content_text || '').trim().toLowerCase();

  const trTitle = (tr.title || '').trim().toLowerCase();
  const trDesc = (tr.description || tr.content_text || '').trim().toLowerCase();

  const isTitleDifferent = Boolean(trTitle && trTitle !== origTitle);
  const isDescDifferent = Boolean(trDesc && trDesc !== origDesc);

  if (isTitleDifferent || isDescDifferent) {
    return true;
  }

  return false;
}

export interface DisplayFieldResult {
  value: string;
  original: string;
  translated: string;
  isTranslated: boolean;
  status: 'completed' | 'not_required' | 'stale' | 'none' | string;
}

/**
 * Resolver único de campos textuales según el modo de visualización seleccionado.
 */
export function getDisplayField(
  item: ExtractedItem,
  field: 'title' | 'description' | 'content_text' | 'technical_function' | 'ocr_text',
  mode: TranslationViewMode = 'translation',
  cacheItem?: Record<string, string>
): DisplayFieldResult {
  const tr = (cacheItem && Object.keys(cacheItem).length > 0)
    ? cacheItem
    : (item.translated_fields && Object.keys(item.translated_fields).length > 0)
      ? item.translated_fields
      : (item.metadata_payload?.translated_fields && Object.keys(item.metadata_payload.translated_fields).length > 0)
        ? item.metadata_payload.translated_fields
        : {};

  const eff = item.effective_fields || item.metadata_payload?.effective_fields || {};
  const src = item.source_fields || {};
  const status = item.translation_status || item.metadata_payload?.translation_status || 'none';

  const origRaw = (src[field] || (item as any)[field] || '').trim();
  const trRaw = (tr[field] || '').trim();
  const effRaw = (eff[field] || '').trim();

  // Candidato traducido: prioridad trRaw, luego effRaw si difiere del original
  const candidateTrans = trRaw || (effRaw.toLowerCase() !== origRaw.toLowerCase() ? effRaw : '');

  // Considerar traducido si existe candidato traducido, es distinto al original y el status no es fallido ni stale
  const isTrans = Boolean(
    candidateTrans &&
    candidateTrans.toLowerCase() !== origRaw.toLowerCase() &&
    status !== 'failed' &&
    status !== 'stale'
  );

  let origClean = origRaw;
  let transClean = isTrans ? candidateTrans : origRaw;

  if (field === 'description') {
    origClean = stripTitleFromDescription(origClean, item.title);
    transClean = stripTitleFromDescription(transClean, tr.title || eff.title || item.title);
  }

  let finalValue = origClean;
  if (mode === 'translation') {
    finalValue = isTrans ? transClean : origClean;
  } else if (mode === 'original') {
    finalValue = origClean;
  } else {
    // Both
    finalValue = isTrans ? transClean : origClean;
  }

  return {
    value: finalValue,
    original: origClean,
    translated: isTrans ? transClean : '',
    isTranslated: isTrans,
    status
  };
}
