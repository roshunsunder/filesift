import React from 'react';
import './LoadingSpinner.css';

export const LoadingSpinner: React.FC = () => {
  return (
    <div className="loading-spinner-container">
      <div className="loading-spinner"></div>
      <p>Loading...</p>
    </div>
  );
};
