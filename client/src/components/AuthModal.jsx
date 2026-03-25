import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function AuthModal({ onClose }) {
  const { sendCode, verifyCode } = useAuth();
  const [step, setStep] = useState('email'); // 'email' | 'code'
  const [email, setEmail] = useState('');
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSendCode = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setError('');
    setLoading(true);
    try {
      await sendCode(email.trim().toLowerCase());
      setStep('code');
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleVerifyCode = async (e) => {
    e.preventDefault();
    if (code.length !== 6) return;
    setError('');
    setLoading(true);
    try {
      await verifyCode(email.trim().toLowerCase(), code);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-modal-backdrop" onClick={onClose}>
      <div
        className="auth-modal"
        role="dialog"
        aria-label="Sign in"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="auth-modal-header">
          <h2>{step === 'email' ? 'Sign in to CartPath' : 'Enter your code'}</h2>
          <button className="btn-dismiss" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>

        {step === 'email' ? (
          <form onSubmit={handleSendCode}>
            <p className="auth-description">
              Enter your email and we'll send you a sign-in code. No password needed.
            </p>
            <label htmlFor="auth-email" className="sr-only">Email address</label>
            <input
              id="auth-email"
              type="email"
              placeholder="Email address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              autoComplete="email"
              required
            />
            {error && <p className="auth-error" role="alert">{error}</p>}
            <div className="auth-actions">
              <button className="btn-primary btn-large" type="submit" disabled={loading}>
                {loading ? 'Sending...' : 'Send code'}
              </button>
            </div>
            <button
              type="button"
              className="btn-dismiss auth-guest-link"
              onClick={onClose}
            >
              Continue as guest
            </button>
          </form>
        ) : (
          <form onSubmit={handleVerifyCode}>
            <p className="auth-description">
              We sent a 6-digit code to <strong>{email}</strong>. Enter it below.
            </p>
            <label htmlFor="auth-code" className="sr-only">Verification code</label>
            <input
              id="auth-code"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              placeholder="000000"
              value={code}
              onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              autoFocus
              autoComplete="one-time-code"
              required
            />
            {error && <p className="auth-error" role="alert">{error}</p>}
            <div className="auth-actions">
              <button className="btn-primary btn-large" type="submit" disabled={loading || code.length !== 6}>
                {loading ? 'Verifying...' : 'Verify'}
              </button>
            </div>
            <button
              type="button"
              className="btn-dismiss auth-guest-link"
              onClick={() => { setStep('email'); setCode(''); setError(''); }}
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
