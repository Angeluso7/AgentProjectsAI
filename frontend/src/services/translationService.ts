import { apiClient } from './api';

export interface LanguageDetectionRequest {
  text: string;
}

export interface LanguageDetectionResponse {
  detected_language: string;
  confidence: number;
  is_supported: boolean;
}

export interface TranslationRequest {
  source_entity_type?: string;
  source_entity_id?: string;
  target_language?: string;
  source_language?: string;
  fields_to_translate?: Record<string, string>;
  organization_id?: string;
  // Compatibilidad con invocaciones heredadas
  entity_type?: string;
  entity_id?: string;
  source_fields?: Record<string, any>;
}

export interface TranslationResponse {
  id: string;
  organization_id: string;
  source_entity_type: string;
  source_entity_id: string;
  entity_type?: string;
  entity_id?: string;
  source_language: string;
  source_language_confidence?: number;
  target_language: string;
  source_text_hash: string;
  translated_title?: string;
  translated_content?: string;
  translated_summary?: string;
  translated_fields: Record<string, string>;
  provider?: string;
  model?: string;
  model_id?: string;
  prompt_version?: string;
  translation_status?: string;
  status?: string;
  cached?: boolean;
  is_stale?: boolean;
  created_at: string;
  updated_at?: string;
}

export interface BatchTranslationRequest {
  items: TranslationRequest[];
  target_language: string;
  source_language?: string;
  organization_id?: string;
}

export interface BatchTranslationResponse {
  translations: TranslationResponse[];
  total_requested?: number;
  total_completed?: number;
  total_cached?: number;
  total_processed: number;
}

export const translationService = {
  async detectLanguage(text: string): Promise<LanguageDetectionResponse> {
    const res = await apiClient.post<LanguageDetectionResponse>('/translations/detect-language', { text });
    return res.data;
  },

  async translateEntity(req: TranslationRequest): Promise<TranslationResponse> {
    const payload = {
      source_entity_type: req.source_entity_type || req.entity_type,
      source_entity_id: req.source_entity_id || req.entity_id,
      target_language: req.target_language || 'es',
      source_language: req.source_language || 'auto',
      fields_to_translate: req.fields_to_translate || req.source_fields || {},
      organization_id: req.organization_id
    };
    const res = await apiClient.post<TranslationResponse>('/translations/translate', payload);
    return res.data;
  },

  async translateBatch(req: BatchTranslationRequest): Promise<BatchTranslationResponse> {
    const payload = {
      target_language: req.target_language || 'es',
      source_language: req.source_language || 'auto',
      organization_id: req.organization_id,
      items: req.items.map((it) => ({
        source_entity_type: it.source_entity_type || it.entity_type,
        source_entity_id: it.source_entity_id || it.entity_id,
        target_language: it.target_language || req.target_language || 'es',
        source_language: it.source_language || req.source_language || 'auto',
        fields_to_translate: it.fields_to_translate || it.source_fields || {},
        organization_id: it.organization_id || req.organization_id
      }))
    };
    const res = await apiClient.post<BatchTranslationResponse>('/translations/translate-batch', payload);
    return res.data;
  },

  async getEntityTranslation(
    entityType: string,
    entityId: string,
    targetLanguage: string = 'es'
  ): Promise<TranslationResponse | null> {
    try {
      const res = await apiClient.get<TranslationResponse>(`/translations/${entityType}/${entityId}`, {
        params: { target_language: targetLanguage }
      });
      return res.data;
    } catch (err: any) {
      if (err?.response?.status === 404) {
        return null;
      }
      throw err;
    }
  },

  async getEntityHistory(entityType: string, entityId: string): Promise<TranslationResponse[]> {
    const res = await apiClient.get<TranslationResponse[]>(`/translations/${entityType}/${entityId}/history`);
    return res.data;
  }
};
