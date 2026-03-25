import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';
import VehicleSelector from './VehicleSelector';

export default function AccountMenu({ onClose }) {
  const { user, logout, updateProfile } = useAuth();
  const [saving, setSaving] = useState(false);

  if (!user) return null;

  const handleVehicleChange = async (vehicleType) => {
    setSaving(true);
    try {
      await updateProfile({ vehicle_type: vehicleType });
    } catch {
      // silently fail — the UI will still show the old value
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = async () => {
    await logout();
    onClose();
  };

  return (
    <div className="account-menu" role="dialog" aria-label="Account settings">
      <div className="account-menu-header">
        <h2>Account</h2>
        <button className="btn-dismiss" onClick={onClose} aria-label="Close">
          Close
        </button>
      </div>

      <div className="account-info">
        {user.display_name && (
          <span className="account-name">{user.display_name}</span>
        )}
        <span className="account-email">{user.email}</span>
        {user.tier !== 'free' && (
          <span className="account-tier-badge">{user.tier}</span>
        )}
      </div>

      <div className="account-section">
        <h3>Vehicle type</h3>
        <VehicleSelector
          value={user.vehicle_type}
          onChange={handleVehicleChange}
        />
        {saving && <p className="account-saving">Saving...</p>}
      </div>

      <div className="account-actions">
        <button className="btn-secondary" onClick={handleLogout}>
          Sign out
        </button>
      </div>
    </div>
  );
}
