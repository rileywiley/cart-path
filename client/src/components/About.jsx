import React from 'react';

export default function About({ onClose }) {
  return (
    <div className="about-panel" role="dialog" aria-label="About CartPath">
      <div className="about-header">
        <h2>About CartPath</h2>
        <button className="btn-dismiss" onClick={onClose} aria-label="Close">
          &times;
        </button>
      </div>

      <div className="about-content">
        <p>
          CartPath helps you navigate safely on roads legal for golf carts and
          low-speed vehicles (LSVs). Routes stay on roads with speed limits of
          35 MPH or less (LSV mode) or 25 MPH or less (golf cart mode).
        </p>

        <h3>Golf Cart vs. LSV</h3>
        <p>
          <strong>Golf carts</strong> (max 20 MPH, no VIN) are restricted to roads
          with lower speed limits. <strong>LSVs/NEVs</strong> (max 25 MPH, street-legal
          equipment, VIN required) may operate on roads up to 35 MPH under FL Statute 316.2122.
          Select your vehicle type in account settings.
        </p>

        <h3>County Golf Cart Ordinances</h3>
        <p>
          The CartPath pilot area crosses multiple counties. Each may impose
          additional restrictions. Check your county's ordinance:
        </p>
        <ul className="about-links">
          <li>
            <a href="https://www.orangecountyfl.net/TrafficTransportation/GolfCarts.aspx" target="_blank" rel="noopener noreferrer">
              Orange County
            </a>
          </li>
          <li>
            <a href="https://www.seminolecountyfl.gov/departments-services/public-works/traffic-engineering/" target="_blank" rel="noopener noreferrer">
              Seminole County
            </a>
          </li>
          <li>
            <a href="https://www.osceola.org/agencies-departments/transportation/" target="_blank" rel="noopener noreferrer">
              Osceola County
            </a>
          </li>
          <li>
            <a href="https://www.lakecountyfl.gov/offices/public_works/traffic_operations/" target="_blank" rel="noopener noreferrer">
              Lake County
            </a>
          </li>
        </ul>

        <h3>Florida Statutes</h3>
        <ul className="about-links">
          <li>
            <a href="http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0316/Sections/0316.212.html" target="_blank" rel="noopener noreferrer">
              FL Statute 316.212 — Golf Cart Operation
            </a>
          </li>
          <li>
            <a href="http://www.leg.state.fl.us/statutes/index.cfm?App_mode=Display_Statute&URL=0300-0399/0316/Sections/0316.2122.html" target="_blank" rel="noopener noreferrer">
              FL Statute 316.2122 — Low-Speed Vehicles
            </a>
          </li>
        </ul>

        <h3>Data Sources</h3>
        <p>
          Road data from OpenStreetMap (&copy; OpenStreetMap contributors, ODbL).
          Speed limits enriched with FDOT open GIS data. Maps by Mapbox.
        </p>

        <p className="about-version">CartPath v1.0</p>
      </div>
    </div>
  );
}
