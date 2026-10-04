import React, { useState, useEffect } from 'react';
import {
  User,
  Mail,
  Key,
  Shield,
  Building2,
  CheckCircle2,
  AlertCircle,
  X,
  Loader2,
  Save,
  Lock,
  ArrowRight
} from 'lucide-react';
import { apiService } from '../services/api';

export type ProfileModalTab = 'profile' | 'email' | 'password';

interface UserProfileModalProps {
  isOpen: boolean;
  initialTab?: ProfileModalTab;
  onClose: () => void;
}

export const UserProfileModal: React.FC<UserProfileModalProps> = ({
  isOpen,
  initialTab = 'profile',
  onClose,
}) => {
  const [activeTab, setActiveTab] = useState<ProfileModalTab>(initialTab);
  const [userProfile, setUserProfile] = useState<any>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [saving, setSaving] = useState<boolean>(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Form State - Perfil
  const [displayName, setDisplayName] = useState<string>('');

  // Form State - Cambio de Email
  const [emailCurrentPassword, setEmailCurrentPassword] = useState<string>('');
  const [newEmail, setNewEmail] = useState<string>('');

  // Form State - Cambio de Contraseña
  const [pwdCurrentPassword, setPwdCurrentPassword] = useState<string>('');
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');

  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
      setSuccessMessage(null);
      setErrorMessage(null);
      loadUserProfile();
    }
  }, [isOpen, initialTab]);

  const loadUserProfile = async () => {
    try {
      setLoading(true);
      const data = await apiService.getCurrentUser();
      setUserProfile(data);
      if (data?.user) {
        setDisplayName(data.user.display_name || '');
      }
    } catch (err: any) {
      console.error('Error cargando perfil:', err);
      // Fallback a localStorage
      const stored = localStorage.getItem('user_info');
      if (stored) {
        try {
          const parsed = JSON.parse(stored);
          setUserProfile({ user: parsed, memberships: [] });
          setDisplayName(parsed.display_name || '');
        } catch {}
      }
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  const activeRole = localStorage.getItem('active_role') || 'viewer';

  const handleUpdateProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!displayName.trim()) {
      setErrorMessage('El nombre no puede estar vacío.');
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await apiService.updateProfile(displayName.trim());
      setSuccessMessage('Perfil actualizado exitosamente.');
      loadUserProfile();
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Error al actualizar el perfil.');
    } finally {
      setSaving(false);
    }
  };

  const handleRequestEmailChange = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailCurrentPassword || !newEmail.trim()) {
      setErrorMessage('Por favor completa todos los campos.');
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiService.requestEmailChange(emailCurrentPassword, newEmail.trim());
      setSuccessMessage(res.message || 'Se ha enviado un enlace de confirmación al nuevo correo.');
      setEmailCurrentPassword('');
      setNewEmail('');
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Error al solicitar cambio de correo.');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pwdCurrentPassword || !newPassword || !confirmPassword) {
      setErrorMessage('Por favor completa todos los campos.');
      return;
    }
    if (newPassword.length < 8) {
      setErrorMessage('La nueva contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setErrorMessage('La nueva contraseña y su confirmación no coinciden.');
      return;
    }
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      await apiService.changePassword(pwdCurrentPassword, newPassword);
      setSuccessMessage('Contraseña cambiada exitosamente.');
      setPwdCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || 'Error al cambiar contraseña.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
    >
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-blue-500/10 text-blue-400">
              <User className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-slate-100">
                Configuración de Cuenta & Seguridad
              </h2>
              <p className="text-xs text-slate-400">
                {userProfile?.user?.email || 'Usuario'}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded-lg transition-colors"
            aria-label="Cerrar modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-800 bg-slate-950/40 px-6">
          <button
            type="button"
            onClick={() => {
              setActiveTab('profile');
              setErrorMessage(null);
              setSuccessMessage(null);
            }}
            className={`py-3 px-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition-all ${
              activeTab === 'profile'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <User className="w-3.5 h-3.5" />
            <span>Mi Perfil</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('email');
              setErrorMessage(null);
              setSuccessMessage(null);
            }}
            className={`py-3 px-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition-all ${
              activeTab === 'email'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Mail className="w-3.5 h-3.5" />
            <span>Cambiar Correo</span>
          </button>
          <button
            type="button"
            onClick={() => {
              setActiveTab('password');
              setErrorMessage(null);
              setSuccessMessage(null);
            }}
            className={`py-3 px-3 text-xs font-medium border-b-2 flex items-center space-x-2 transition-all ${
              activeTab === 'password'
                ? 'border-blue-500 text-blue-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            <Key className="w-3.5 h-3.5" />
            <span>Cambiar Contraseña</span>
          </button>
        </div>

        {/* Body */}
        <div className="p-6 overflow-y-auto space-y-4">
          {/* Feedback messages */}
          {successMessage && (
            <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800 text-xs text-emerald-300 flex items-start space-x-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>{successMessage}</span>
            </div>
          )}
          {errorMessage && (
            <div className="p-3 rounded-xl bg-red-950/40 border border-red-800 text-xs text-red-300 flex items-start space-x-2 animate-in fade-in">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* TAB 1: MI PERFIL */}
          {activeTab === 'profile' && (
            <form onSubmit={handleUpdateProfile} className="space-y-4">
              <div className="p-3.5 rounded-xl bg-slate-950/40 border border-slate-800 space-y-2.5">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center space-x-1.5">
                    <Mail className="w-3.5 h-3.5 text-slate-500" />
                    <span>Correo Electrónico:</span>
                  </span>
                  <span className="font-mono text-slate-200 font-medium">{userProfile?.user?.email}</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center space-x-1.5">
                    <Shield className="w-3.5 h-3.5 text-slate-500" />
                    <span>Rol Asignado:</span>
                  </span>
                  <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 uppercase font-semibold text-[10px]">
                    {activeRole}
                  </span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-slate-400 flex items-center space-x-1.5">
                    <Building2 className="w-3.5 h-3.5 text-slate-500" />
                    <span>Organizaciones:</span>
                  </span>
                  <span className="text-slate-300">
                    {userProfile?.memberships?.length || 1} activa(s)
                  </span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Nombre Completo / Para Mostrar
                </label>
                <input
                  type="text"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="Tu nombre y apellido"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-all flex items-center space-x-2 shadow-lg shadow-blue-950/50 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                  <span>Guardar Cambios</span>
                </button>
              </div>
            </form>
          )}

          {/* TAB 2: CAMBIAR CORREO */}
          {activeTab === 'email' && (
            <form onSubmit={handleRequestEmailChange} className="space-y-4">
              <p className="text-xs text-slate-400 leading-relaxed">
                Por motivos de seguridad, se enviará un enlace de confirmación a tu nueva dirección. El cambio no se aplicará hasta que hagas clic en dicho enlace.
              </p>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Nueva Dirección de Correo Electrónico
                </label>
                <input
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="nuevo_correo@empresa.com"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Contraseña Actual (para confirmar tu identidad)
                </label>
                <input
                  type="password"
                  value={emailCurrentPassword}
                  onChange={(e) => setEmailCurrentPassword(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="••••••••••••"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-all flex items-center space-x-2 shadow-lg shadow-blue-950/50 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Mail className="w-3.5 h-3.5" />}
                  <span>Enviar Confirmación</span>
                </button>
              </div>
            </form>
          )}

          {/* TAB 3: CAMBIAR CONTRASEÑA */}
          {activeTab === 'password' && (
            <form onSubmit={handleChangePassword} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Contraseña Actual
                </label>
                <input
                  type="password"
                  value={pwdCurrentPassword}
                  onChange={(e) => setPwdCurrentPassword(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="••••••••••••"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Nueva Contraseña (mínimo 8 caracteres)
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="••••••••••••"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Confirmar Nueva Contraseña
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full px-3.5 py-2 text-xs rounded-xl bg-slate-950 border border-slate-800 text-slate-200 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                  placeholder="••••••••••••"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-2 text-xs font-medium text-white bg-blue-600 hover:bg-blue-500 rounded-xl transition-all flex items-center space-x-2 shadow-lg shadow-blue-950/50 disabled:opacity-50"
                >
                  {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Lock className="w-3.5 h-3.5" />}
                  <span>Actualizar Contraseña</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
