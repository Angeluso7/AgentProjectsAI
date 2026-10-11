import React, { useState } from 'react';
import { X, GitCommitHorizontal, Check, ShieldCheck, Tag, Compass, Wind } from 'lucide-react';

interface PipingLineDataModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: {
    line_number?: string;
    nominal_size?: string;
    service_fluid?: string;
    spec_class?: string;
    insulation?: string;
    from_equipment_tag?: string;
    to_equipment_tag?: string;
    flow_direction: string;
  }) => Promise<void> | void;
  pointsCount: number;
}

export const PipingLineDataModal: React.FC<PipingLineDataModalProps> = ({
  isOpen,
  onClose,
  onSave,
  pointsCount
}) => {
  const [lineNumber, setLineNumber] = useState('');
  const [nominalSize, setNominalSize] = useState('6"');
  const [serviceFluid, setServiceFluid] = useState('P');
  const [specClass, setSpecClass] = useState('CS150');
  const [insulation, setInsulation] = useState('N');
  const [fromEquipment, setFromEquipment] = useState('');
  const [toEquipment, setToEquipment] = useState('');
  const [flowDirection, setFlowDirection] = useState('unconfirmed');
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    try {
      await onSave({
        line_number: lineNumber.trim() || undefined,
        nominal_size: nominalSize.trim() || undefined,
        service_fluid: serviceFluid.trim() || undefined,
        spec_class: specClass.trim() || undefined,
        insulation: insulation.trim() || undefined,
        from_equipment_tag: fromEquipment.trim() || undefined,
        to_equipment_tag: toEquipment.trim() || undefined,
        flow_direction: flowDirection
      });
      onClose();
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 100,
        backgroundColor: 'rgba(2, 6, 23, 0.75)',
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
          maxWidth: '560px',
          background: 'linear-gradient(135deg, #0b1329 0%, #080e1a 100%)',
          borderRadius: '16px',
          border: '1px solid rgba(6, 182, 212, 0.3)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.8), 0 0 30px rgba(6, 182, 212, 0.15)',
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
            background: 'rgba(15, 23, 42, 0.6)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: '10px',
                background: 'rgba(6, 182, 212, 0.15)',
                border: '1px solid #06b6d4',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#06b6d4'
              }}
            >
              <GitCommitHorizontal size={20} />
            </div>
            <div>
              <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 700, color: '#f1f5f9' }}>
                Asignar Parámetros de Piping
              </h3>
              <p style={{ margin: 0, fontSize: '12px', color: '#94a3b8' }}>
                Polilínea manual con {pointsCount} puntos vectoriales registrados
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} style={{ padding: '24px' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '16px' }}>
            {/* Tag / Line Number */}
            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Número / Tag de Línea
              </label>
              <div style={{ position: 'relative' }}>
                <input
                  type="text"
                  placeholder="ej. 01-6&quot;-P-CS150-001"
                  value={lineNumber}
                  onChange={(e) => setLineNumber(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '9px 12px',
                    borderRadius: '8px',
                    background: 'rgba(15, 23, 42, 0.8)',
                    border: '1px solid rgba(255, 255, 255, 0.12)',
                    color: '#f8fafc',
                    fontSize: '13px'
                  }}
                  autoFocus
                />
              </div>
            </div>

            {/* Diámetro Nominal */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Diámetro Nominal
              </label>
              <input
                type="text"
                placeholder="ej. 6&quot; o 150mm"
                value={nominalSize}
                onChange={(e) => setNominalSize(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Fluido de Servicio */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Fluido de Servicio
              </label>
              <input
                type="text"
                placeholder="ej. P (Proceso), CW, IA"
                value={serviceFluid}
                onChange={(e) => setServiceFluid(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Clase de Tubería / Spec */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Clase / Piping Spec
              </label>
              <input
                type="text"
                placeholder="ej. CS150, SS304"
                value={specClass}
                onChange={(e) => setSpecClass(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Aislación */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Aislación Térmica
              </label>
              <input
                type="text"
                placeholder="ej. N (Ninguna), IH (Caliente)"
                value={insulation}
                onChange={(e) => setInsulation(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Desde Equipo */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Origen (From Equipment)
              </label>
              <input
                type="text"
                placeholder="ej. TK-101"
                value={fromEquipment}
                onChange={(e) => setFromEquipment(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Hasta Equipo */}
            <div>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Destino (To Equipment)
              </label>
              <input
                type="text"
                placeholder="ej. P-101A"
                value={toEquipment}
                onChange={(e) => setToEquipment(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              />
            </div>

            {/* Dirección de Flujo */}
            <div style={{ gridColumn: 'span 2' }}>
              <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: '#cbd5e1', marginBottom: '6px' }}>
                Sentido de Flujo
              </label>
              <select
                value={flowDirection}
                onChange={(e) => setFlowDirection(e.target.value)}
                style={{
                  width: '100%',
                  padding: '9px 12px',
                  borderRadius: '8px',
                  background: 'rgba(15, 23, 42, 0.8)',
                  border: '1px solid rgba(255, 255, 255, 0.12)',
                  color: '#f8fafc',
                  fontSize: '13px'
                }}
              >
                <option value="forward">Forward (Hacia adelante según trazo)</option>
                <option value="reverse">Reverse (Hacia atrás según trazo)</option>
                <option value="unconfirmed">Sin confirmar (Requiere flecha de flujo)</option>
              </select>
            </div>
          </div>

          {/* Footer Actions */}
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' }}>
            <button
              type="button"
              onClick={onClose}
              disabled={isSaving}
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
              type="submit"
              disabled={isSaving}
              style={{
                padding: '8px 20px',
                borderRadius: '8px',
                background: 'linear-gradient(135deg, #06b6d4 0%, #0284c7 100%)',
                border: 'none',
                color: '#ffffff',
                fontWeight: 700,
                fontSize: '13px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                boxShadow: '0 4px 14px rgba(6, 182, 212, 0.3)'
              }}
            >
              <Check size={16} />
              {isSaving ? 'Guardando...' : 'Guardar Línea de Piping'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
