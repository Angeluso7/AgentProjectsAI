import React, { useState, useEffect } from 'react';
import { Shield, Lock, CheckCircle2, AlertCircle, ArrowRight, Key, Mail, Loader2 } from 'lucide-react';
import { apiService } from '../services/api';

interface ResetPasswordPageProps {
  onSuccess?: () => void;
}

export const ResetPasswordPage: React.FC<ResetPasswordPageProps> = ({ onSuccess }) => {
  const [token, setToken] = useState<string>('');
  const [isVerifyEmail, setIsVerifyEmail] = useState<boolean>(false);
  const [newPassword, setNewPassword] = useState<string>('');
  const [confirmPassword, setConfirmPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [verifyingEmail, setVerifyingEmail] = useState<boolean>(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tokenParam = params.get('token') || '';
    setToken(tokenParam);

    const isVerify = window.location.pathname.includes('/verify-email') || params.get('mode') === 'verify_email';
    setIsVerifyEmail(isVerify);

    if (isVerify && tokenParam) {
      handleAutoVerifyEmail(tokenParam);
    }
  }, []);

  const handleAutoVerifyEmail = async (tokenStr: string) => {
    setVerifyingEmail(true);
    setError(null);
    try {
      const res = await apiService.confirmEmailChange(tokenStr);
      setSuccess(res.message || 'Correo electrónico confirmado exitosamente.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'El enlace de confirmación es inválido o ha expirado.');
    } finally {
      setVerifyingEmail(false);
    }
  };

  const handleSubmitReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token) {
      setError('Token de recuperación no provisto o inválido.');
      return;
    }
    if (newPassword.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.');
      return;
    }
    if (newPassword !== confirmPassword) {
      setError('Las contraseñas no coinciden.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await apiService.confirmPasswordReset(token, newPassword);
      setSuccess(res.message || 'Tu contraseña ha sido restablecida exitosamente.');
    } catch (err: any) {
      console.error('Error restableciendo contraseña:', err);
      setError(err.response?.data?.detail || 'Error al restablecer la contraseña.');
    } finally {
      setLoading(false);
    }
  };

  const handleGoToLogin = () => {
    window.location.href = '/login';
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden selection:bg-cyan-500 selection:text-black">
      {/* Background Decorative Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[400px] bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Brand Header */}
        <div className="flex justify-center items-center gap-3.5 mb-4">
          <div className="p-3 bg-gradient-to-tr from-cyan-500 to-indigo-600 rounded-2xl shadow-xl shadow-cyan-500/20 border border-cyan-400/30">
            <Shield className="w-8 h-8 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold tracking-tight text-white font-mono flex items-center gap-1.5">
              PLAN REVIEW <span className="text-cyan-400">AI</span>
            </h1>
            <p className="text-[11px] text-slate-400 font-mono tracking-widest uppercase">
              Hybrid QA/QC Audit Platform
            </p>
          </div>
        </div>

        <h2 className="text-center text-xl font-bold text-slate-100">
          {isVerifyEmail ? 'Confirmación de Correo Electrónico' : 'Establecer Nueva Contraseña'}
        </h2>
        <p className="mt-1 text-center text-xs text-slate-400">
          {isVerifyEmail
            ? 'Validación segura de dirección de correo'
            : 'Crea una contraseña segura para tu cuenta'}
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-slate-900/90 backdrop-blur-2xl py-8 px-6 sm:px-10 shadow-2xl rounded-2xl border border-slate-800 ring-1 ring-white/5">
          {verifyingEmail ? (
            <div className="py-8 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
              <p className="text-xs text-slate-400">Confirmando nueva dirección de correo...</p>
            </div>
          ) : success ? (
            <div className="space-y-5 animate-in fade-in">
              <div className="p-4 rounded-xl bg-emerald-950/60 border border-emerald-800 text-xs text-emerald-300 flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
                <div className="leading-relaxed">
                  <p className="font-semibold text-sm text-emerald-200 mb-1">¡Operación Exitosa!</p>
                  <p>{success}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleGoToLogin}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 rounded-xl shadow-lg shadow-cyan-600/20 text-sm font-semibold text-white bg-gradient-to-r from-cyan-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 transition-all cursor-pointer"
              >
                <span>Ir al Inicio de Sesión</span>
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          ) : isVerifyEmail && error ? (
            <div className="space-y-5 animate-in fade-in">
              <div className="p-4 rounded-xl bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-rose-400 shrink-0 mt-0.5" />
                <div>
                  <p className="font-semibold text-sm text-rose-200 mb-1">Enlace no Válido</p>
                  <p>{error}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleGoToLogin}
                className="w-full py-2.5 px-4 rounded-xl text-xs font-semibold text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 transition-all"
              >
                Volver al Inicio
              </button>
            </div>
          ) : (
            <form className="space-y-5" onSubmit={handleSubmitReset}>
              {error && (
                <div className="p-3.5 rounded-xl bg-rose-950/60 border border-rose-800/80 flex items-start gap-2.5 text-rose-300 text-xs animate-in fade-in">
                  <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-400" />
                  <span className="leading-relaxed">{error}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Nueva Contraseña
                </label>
                <div className="relative rounded-xl shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <Lock className="h-4 w-4 text-slate-500" />
                  </div>
                  <input
                    type="password"
                    required
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Mínimo 8 caracteres"
                    className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                  Confirmar Nueva Contraseña
                </label>
                <div className="relative rounded-xl shadow-sm">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                    <Key className="h-4 w-4 text-slate-500" />
                  </div>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Repite la contraseña"
                    className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all font-mono"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex justify-center items-center gap-2 py-2.5 px-4 rounded-xl shadow-lg shadow-cyan-600/20 text-sm font-semibold text-white bg-gradient-to-r from-cyan-600 via-sky-600 to-indigo-600 hover:from-cyan-500 hover:to-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-cyan-500 disabled:opacity-50 transition-all cursor-pointer"
              >
                {loading ? (
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Guardando nueva contraseña...</span>
                  </div>
                ) : (
                  <>
                    <span>Guardar y Restablecer Contraseña</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};
