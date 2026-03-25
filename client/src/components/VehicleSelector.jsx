import React from 'react';

export default function VehicleSelector({ value, onChange }) {
  return (
    <div className="vehicle-selector" role="radiogroup" aria-label="Vehicle type">
      <button
        type="button"
        role="radio"
        aria-checked={value === 'golf_cart'}
        className={`vehicle-option ${value === 'golf_cart' ? 'vehicle-option--active' : ''}`}
        onClick={() => onChange('golf_cart')}
      >
        <span className="vehicle-option-name">Golf Cart</span>
        <span className="vehicle-option-desc">Roads up to 25 MPH</span>
      </button>
      <button
        type="button"
        role="radio"
        aria-checked={value === 'lsv'}
        className={`vehicle-option ${value === 'lsv' ? 'vehicle-option--active' : ''}`}
        onClick={() => onChange('lsv')}
      >
        <span className="vehicle-option-name">LSV</span>
        <span className="vehicle-option-desc">Roads up to 35 MPH</span>
      </button>
    </div>
  );
}
