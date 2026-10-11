import React, { useState } from 'react';
import { Trash2, AlertTriangle, X } from 'lucide-react';
import { PipingLineItem } from '../types';

interface DeletePipingLineModalProps {
  isOpen: boolean;
  line: PipingLineItem | null;
  onClose: () => void;
  onConfirm: (lineId: string) => Promise<void> | void;
}

export const DeletePipingLineModal: React.FC<DeletePipingLineModalProps> = ({
  isOpen,
  line,
  onClose,
  onConfirm
}) => {
  const [isDeleting, setIsDeleting] = useState(false);

  if (!isOpen || !line) return null;

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onConfirm(line.id);
      onClose();
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 110,
        backgroundColor: 'rgba(2, 6, 23, 0.8)',
        backdropFilter: 'blur(8px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px'
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '460px',
          background: 'linear-gradient(135deg, #180d12 0%, #0c080d 100%)',
          borderRadius: '16px',
          border: '1px solid rgba(239, 68, 68, 0.35)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(239, 68, 68, 0.2)',
          overflow: 'hidden'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: '18px 24px',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'rgba(239, 68, 68, 0.08)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'rgba(239, 68, 68, 0.15)',
                border: '1px solid #ef4444',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ef4444'
              }}
            >
              <AlertTriangle size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f1f5f9' }}>
                Eliminar Línea de Piping
              </h3>
              <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Confirmación de remoción permanente
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: '#64748b',
              cursor: 'pointer',
              padding: '6px',
              borderRadius: '6px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div style={{ padding: '24px' }}>
          <p style={{ fontSize: '13px', color: '#cbd5e1', lineHeight: '1.5', margin: '0 0 16px 0' }}>
            ¿Estás seguro de que deseas eliminar la línea de piping{' '}
            <strong style={{ color: '#38bdf8' }}>{line.line_number || line.id.slice(0, 8)}</strong>?
          </p>

          <div
            style={{
              background: 'rgba(239, 68, 68, 0.08)',
              border: '1px solid rgba(239, 68, 68, 0.2)',
              borderRadius: '8px',
              padding: '12px 14px',
              marginBottom: '20px'
            }}
          >
            <div style={{ fontSize: '12px', color: '#fca5a5', lineHeight: '1.4' }}>
              Esta acción eliminará la línea lógica y sus {line.segments?.length || 0} segmento(s) vectoriales asociados de la base de datos.
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isDeleting}
              style={{
                padding: '8px 16px',
                borderRadius: '8px',
                background: 'rgba(255, 255, 255, 0.06)',
                border: '1px solid rgba(255, 255, 255, 0.12)',
                color: '#cbd5e1',
                fontSize: '13px',
                cursor: 'pointer'
              }}
            >
              Cancelar
            </button>
            <button
              type="button"
              onClick={handleDelete}
              disabled={isDeleting}
              style={{
                padding: '8px 20px',
                borderRadius: '8px',
                background: '#ef4444',
                border: 'none',
                color: '#ffffff',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 4px 14px rgba(239, 68, 68, 0.3)'
              }}
            >
              <Trash2 size={16} />
              {isDeleting ? 'Eliminando...' : 'Eliminar Línea'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
