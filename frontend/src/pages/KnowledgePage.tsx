import React, { useState } from 'react';
import { KnowledgeBaseManager } from '../components/KnowledgeBaseManager';
import { AssistantCopilotDrawer } from '../components/AssistantCopilotDrawer';
import { BookOpen, FileCode, Layers, Database, Sparkles } from 'lucide-react';

export const KnowledgePage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'operational_kb' | 'standards' | 'ontologies' | 'templates'>('operational_kb');
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  return (
    <div className="page-container">
      {/* Top Tabs */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
          <button
            className={`btn ${activeTab === 'operational_kb' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('operational_kb')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Database size={16} /> Base de Conocimiento Operacional
          </button>
          <button
            className={`btn ${activeTab === 'standards' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('standards')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <BookOpen size={16} /> Normativas Técnicas (`normative_memory`)
          </button>
          <button
            className={`btn ${activeTab === 'ontologies' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('ontologies')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <FileCode size={16} /> Ontologías & Alias
          </button>
          <button
            className={`btn ${activeTab === 'templates' ? 'btn-primary' : 'btn-secondary'}`}
            onClick={() => setActiveTab('templates')}
            style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <Layers size={16} /> Plantillas de Viñeta (`template_memory`)
          </button>
        </div>

        {/* Botón Asistente Copilot */}
        <button
          className="btn btn-primary"
          style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, background: 'linear-gradient(135deg, var(--primary), var(--accent))' }}
          onClick={() => setIsCopilotOpen(true)}
        >
          <Sparkles size={16} /> Abrir Copilot Asistente
        </button>
      </div>

      <AssistantCopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
        initialTaskType="normative_query"
      />

      {activeTab === 'operational_kb' && (
        <KnowledgeBaseManager />
      )}

      {activeTab === 'standards' && (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <h2 style={{ fontSize: '16px', fontWeight: 700 }}>Estándar: OGUC-CHILE-2024 (Ordenanza General de Urbanismo)</h2>
            <span className="badge badge-success">Activo</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            <div style={{ background: 'var(--bg-sidebar)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>Art. 4.1.7 — Ancho Mínimo de Puertas</div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                "Las puertas de recintos habitables deberán tener un ancho libre mínimo de 0.85 m..."
              </div>
              <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                <span className="badge badge-medium">Criterio: clear_width_m &gt;= 0.85</span>
                <span className="badge badge-high">Severidad: Alta</span>
              </div>
            </div>

            <div style={{ background: 'var(--bg-sidebar)', padding: '14px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
              <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--primary)' }}>Art. 4.1.8 — Altura Libre Interior</div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px' }}>
                "La altura libre mínima de piso a cielo en recintos habitables será de 2.30 m..."
              </div>
              <div style={{ marginTop: '8px', display: 'flex', gap: '6px' }}>
                <span className="badge badge-medium">Criterio: clear_height_m &gt;= 2.30</span>
                <span className="badge badge-high">Severidad: Media</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'ontologies' && (
        <div className="card">
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>Diccionario de Conceptos Canónicos & Alias</h2>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
            <div style={{ background: 'var(--bg-sidebar)', padding: '14px', borderRadius: '8px' }}>
              <div style={{ fontWeight: 700, color: 'var(--accent)' }}>LEVEL_FINISHED_FLOOR</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Nivel de Piso Terminado</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                Alias: <span className="font-mono">["NPT", "N.P.T.", "NIVEL PISO TERM.", "FFL"]</span>
              </div>
            </div>

            <div style={{ background: 'var(--bg-sidebar)', padding: '14px', borderRadius: '8px' }}>
              <div style={{ fontWeight: 700, color: 'var(--accent)' }}>DOOR_SINGLE</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>Puerta Batiente Simple</div>
              <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: '4px' }}>
                Alias: <span className="font-mono">["P1", "P-1", "PUERTA", "PTA."]</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTab === 'templates' && (
        <div className="card">
          <h2 style={{ fontSize: '16px', fontWeight: 700, marginBottom: '16px' }}>Plantilla: Standard-A0-BottomRight</h2>
          <div style={{ background: 'var(--bg-sidebar)', padding: '16px', borderRadius: '8px', fontSize: '13px' }}>
            <div><strong>Posición:</strong> Esquina inferior derecha (x: 72% - 99%, y: 72% - 99%)</div>
            <div style={{ marginTop: '8px' }}>
              <strong>Anchors de Extracción:</strong>
              <ul style={{ paddingLeft: '20px', marginTop: '4px', color: 'var(--text-muted)' }}>
                <li>Código de Plano: "PLANO N°", "CODIGO", "LAMINA"</li>
                <li>Escala: "ESCALA", "ESC."</li>
                <li>Revisión: "REV", "REVISION"</li>
              </ul>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
