import React, { useState } from 'react';
import { Shield, Lock, Mail, ArrowRight, AlertCircle, Sparkles, CheckCircle2 } from 'lucide-react';
import { apiService } from '../services/api';

interface LoginPageProps {
  onLoginSuccess?: () => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const [email, setEmail] = useState('admin@planreview.ai');
  const [password, setPassword] = useState('admin123456');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Estados para Modal de Recuperación de Contraseña
  const [showResetModal, setShowResetModal] = useState(false);
  const [resetEmail, setResetEmail] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [resetSuccess, setResetSuccess] = useState<string | null>(null);
  const [resetError, setResetError] = useState<string | null>(null);

  const handleRequestReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!resetEmail.trim()) {
      setResetError('Por favor ingresa tu correo electrónico.');
      return;
    }
    setResetLoading(true);
    setResetError(null);
    try {
      const res = await apiService.requestPasswordReset(resetEmail.trim());
      setResetSuccess(res.message || 'Si existe una cuenta asociada a ese correo, recibirás un mensaje con las instrucciones.');
    } catch (err: any) {
      setResetError(err.response?.data?.detail || 'Error al procesar la solicitud.');
    } finally {
      setResetLoading(false);
    }
  };


  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await apiService.login(email, password);
      if (onLoginSuccess) {
        onLoginSuccess();
      } else {
        window.location.href = '/';
      }
    } catch (err: any) {
      console.error('Error durante login:', err);
      const detail =
        err.response?.data?.detail ||
        (err.message === 'Network Error'
          ? 'No se pudo conectar con el servidor backend en http://localhost:8000. Asegúrese de que el backend esté en ejecución.'
          : 'Error de autenticación. Verifique sus credenciales.');
      setError(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleSelectDemoUser = (demoEmail: string) => {
    setEmail(demoEmail);
    setPassword('admin123456');
    setError(null);
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden selection:bg-cyan-500 selection:text-black">
      {/* Background Decorative Glows */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[500px] h-[500px] bg-cyan-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-[400px] h-[400px] bg-indigo-600/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute top-10 right-10 w-72 h-72 bg-blue-600/5 rounded-full blur-2xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        {/* Brand Header */}
        <div className="flex justify-center items-center gap-3.5 mb-3">
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

        <h2 className="mt-4 text-center text-xl font-bold text-slate-100">
          Iniciar Sesión en la Plataforma
        </h2>
        <p className="mt-1 text-center text-xs text-slate-400">
          Aislamiento organizacional multi-tenant y control de acceso RBAC
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10">
        <div className="bg-slate-900/90 backdrop-blur-2xl py-8 px-6 sm:px-10 shadow-2xl rounded-2xl border border-slate-800 ring-1 ring-white/5">
          {error && (
            <div className="mb-5 p-3.5 rounded-xl bg-rose-950/60 border border-rose-800/80 flex items-start gap-2.5 text-rose-300 text-xs animate-in fade-in">
              <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5 text-rose-400" />
              <span className="leading-relaxed">{error}</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1.5">
                Correo Electrónico
              </label>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Mail className="h-4 w-4 text-slate-500" />
                </div>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="usuario@organizacion.com"
                  className="block w-full pl-10 pr-3.5 py-2.5 bg-slate-950/90 border border-slate-700/80 rounded-xl text-slate-100 placeholder-slate-500 text-sm focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent transition-all font-mono"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                  Contraseña
                </label>
                <button
                  type="button"
                  onClick={() => {
                    setResetEmail(email);
                    setShowResetModal(true);
                    setResetSuccess(null);
                    setResetError(null);
                  }}
                  className="text-[11px] text-cyan-400 hover:text-cyan-300 hover:underline transition-colors cursor-pointer"
                >
                  ¿Olvidaste tu contraseña?
                </button>
              </div>
              <div className="relative rounded-xl shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none">
                  <Lock className="h-4 w-4 text-slate-500" />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••••••"
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
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Verificando credenciales...</span>
                </div>
              ) : (
                <>
                  <span>Ingresar a la Plataforma</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>

          {/* Modal de Solicitud de Recuperación de Contraseña */}
          {showResetModal && (
            <div
              className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 animate-in fade-in duration-200"
              role="dialog"
              aria-modal="true"
            >
              <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-base font-semibold text-slate-100 flex items-center gap-2">
                    <Lock className="w-4 h-4 text-cyan-400" />
                    Recuperar Contraseña
                  </h3>
                  <button
                    type="button"
                    onClick={() => setShowResetModal(false)}
                    className="p-1 text-slate-400 hover:text-slate-200 rounded-lg"
                  >
                    ✕
                  </button>
                </div>

                <p className="text-xs text-slate-400 leading-relaxed">
                  Ingresa tu correo electrónico registrado. Si existe una cuenta asociada, te enviaremos un enlace seguro de un solo uso para restablecer tu contraseña.
                </p>

                {resetSuccess ? (
                  <div className="p-3.5 rounded-xl bg-emerald-950/50 border border-emerald-800 text-xs text-emerald-300 space-y-3">
                    <div className="flex items-start gap-2">
                      <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                      <span>{resetSuccess}</span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowResetModal(false)}
                      className="w-full py-2 bg-emerald-700 hover:bg-emerald-600 text-white rounded-xl text-xs font-semibold"
                    >
                      Volver al Inicio de Sesión
                    </button>
                  </div>
                ) : (
                  <form onSubmit={handleRequestReset} className="space-y-4">
                    {resetError && (
                      <div className="p-3 rounded-xl bg-rose-950/50 border border-rose-800 text-xs text-rose-300 flex items-center gap-2">
                        <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                        <span>{resetError}</span>
                      </div>
                    )}
                    <div>
                      <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                        Correo Electrónico
                      </label>
                      <input
                        type="email"
                        required
                        value={resetEmail}
                        onChange={(e) => setResetEmail(e.target.value)}
                        placeholder="tu_correo@organizacion.com"
                        className="w-full px-3.5 py-2.5 text-xs rounded-xl bg-slate-950 border border-slate-700 text-slate-200 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-mono"
                      />
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={() => setShowResetModal(false)}
                        className="px-3.5 py-2 text-xs text-slate-400 hover:text-slate-200 rounded-xl"
                      >
                        Cancelar
                      </button>
                      <button
                        type="submit"
                        disabled={resetLoading}
                        className="px-4 py-2 text-xs font-semibold text-white bg-cyan-600 hover:bg-cyan-500 rounded-xl transition-all disabled:opacity-50"
                      >
                        {resetLoading ? 'Enviando...' : 'Enviar Instrucciones'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}


          {/* Cuentas de Acceso Rápido / Demo */}
          <div className="mt-6 pt-6 border-t border-slate-800/80 space-y-3">
            <div className="flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
              <span className="flex items-center gap-1">
                <Sparkles className="w-3 h-3 text-cyan-400" /> Cuentas de Acceso Rápido:
              </span>
              <span className="text-[10px] text-slate-500">Click para auto-llenar</span>
            </div>

            <div className="space-y-1.5 text-xs">
              <button
                type="button"
                onClick={() => handleSelectDemoUser('admin@planreview.ai')}
                className={`w-full flex justify-between items-center p-2 rounded-xl transition-all border text-left cursor-pointer ${
                  email === 'admin@planreview.ai'
                    ? 'bg-cyan-950/50 border-cyan-600/50 text-cyan-300'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2 font-mono">
                  {email === 'admin@planreview.ai' && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                  <span>admin@planreview.ai</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-cyan-900/40 text-cyan-300 font-semibold border border-cyan-800/40">
                  Admin
                </span>
              </button>

              <button
                type="button"
                onClick={() => handleSelectDemoUser('reviewer@planreview.ai')}
                className={`w-full flex justify-between items-center p-2 rounded-xl transition-all border text-left cursor-pointer ${
                  email === 'reviewer@planreview.ai'
                    ? 'bg-cyan-950/50 border-cyan-600/50 text-cyan-300'
                    : 'bg-slate-950/60 border-slate-800 text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                <div className="flex items-center gap-2 font-mono">
                  {email === 'reviewer@planreview.ai' && <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400 shrink-0" />}
                  <span>reviewer@planreview.ai</span>
                </div>
                <span className="text-[10px] uppercase tracking-wider px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-semibold border border-slate-700">
                  Reviewer
                </span>
              </button>
            </div>

            <p className="text-[10px] text-slate-400 text-center pt-1 font-mono">
              Contraseña predeterminada: <span className="text-slate-200 font-bold">admin123456</span>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
