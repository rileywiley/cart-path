import React, { useState } from 'react';

const STEPS = {
  SPLASH: 'splash',
  LOCATION: 'location',
  DISCLAIMER: 'disclaimer',
};

export default function Onboarding({ onComplete }) {
  const [step, setStep] = useState(STEPS.SPLASH);
  const [locationStatus, setLocationStatus] = useState(null);
  const [location, setLocation] = useState(null);

  const handleGetStarted = () => {
    setStep(STEPS.LOCATION);
  };

  const handleRequestLocation = () => {
    setLocationStatus('requesting');
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocationStatus('granted');
        setLocation({ lat: pos.coords.latitude, lon: pos.coords.longitude });
        setStep(STEPS.DISCLAIMER);
      },
      () => {
        setLocationStatus('denied');
        setStep(STEPS.DISCLAIMER);
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  };

  const handleSkipLocation = () => {
    setLocationStatus('skipped');
    setStep(STEPS.DISCLAIMER);
  };

  const handleAcceptDisclaimer = () => {
    localStorage.setItem('cartpath_disclaimer', 'accepted');
    onComplete(location);
  };

  if (step === STEPS.SPLASH) {
    return (
      <div className="onboarding onboarding-splash" role="main">
        <div className="onboarding-content">
          <h1 className="onboarding-logo">CartPath</h1>
          <p className="onboarding-tagline">Safe routes for your golf cart</p>
          <button className="btn-primary btn-large" onClick={handleGetStarted}>
            Get Started
          </button>
        </div>
      </div>
    );
  }

  if (step === STEPS.LOCATION) {
    return (
      <div className="onboarding onboarding-location" role="main">
        <div className="onboarding-content">
          <h2>Find routes near you</h2>
          <p>CartPath needs your location to find routes near you.</p>
          {locationStatus === 'requesting' ? (
            <p className="onboarding-status">Requesting location...</p>
          ) : (
            <div className="onboarding-actions">
              <button className="btn-primary btn-large" onClick={handleRequestLocation}>
                Allow location
              </button>
              <button className="btn-secondary" onClick={handleSkipLocation}>
                Not now
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  if (step === STEPS.DISCLAIMER) {
    return (
      <div className="onboarding onboarding-disclaimer" role="main">
        <div className="onboarding-content">
          <h2>Before you go</h2>
          <p className="disclaimer-text">
            CartPath suggests routes based on available data. Routes are not guaranteed
            to be legal or safe for all vehicles. Always obey posted signs and local regulations.
          </p>
          <p className="disclaimer-text disclaimer-night-weather">
            Some areas restrict golf cart use after dark or during severe weather. Check local regulations.
          </p>
          <button className="btn-primary btn-large" onClick={handleAcceptDisclaimer}>
            I understand
          </button>
        </div>
      </div>
    );
  }

  return null;
}
