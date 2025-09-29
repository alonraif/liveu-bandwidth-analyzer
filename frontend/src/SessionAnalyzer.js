import React, { useState, useEffect } from 'react';
import './SessionAnalyzer.css';

const SessionAnalyzer = ({ token }) => {
  const [file, setFile] = useState(null);
  const [sessionData, setSessionData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [dateRange, setDateRange] = useState({
    startDate: '',
    endDate: '',
    startTime: '',
    endTime: ''
  });

  const analyzeSessionFile = async () => {
    if (!file) return;

    setLoading(true);
    setError(null);

    try {
      const formData = new FormData();
      formData.append('file', file);

      // Add date range filtering if provided
      if (dateRange.startDate || dateRange.startTime) {
        const startDateTime = `${dateRange.startDate} ${dateRange.startTime || '00:00:00'}`;
        formData.append('start_datetime', startDateTime);
      }
      if (dateRange.endDate || dateRange.endTime) {
        const endDateTime = `${dateRange.endDate} ${dateRange.endTime || '23:59:59'}`;
        formData.append('end_datetime', endDateTime);
      }

      const response = await fetch('/api/analyze-sessions', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Analysis failed: ${response.statusText}`);
      }

      const data = await response.json();
      setSessionData(data);
    } catch (err) {
      setError(err.message);
      console.error('Session analysis error:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds) return 'N/A';
    const mins = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(1);
    return `${mins}m ${secs}s`;
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'streaming': return '#28a745';
      case 'connecting': return '#ffc107';
      case 'collecting': return '#17a2b8';
      case 'error': return '#dc3545';
      default: return '#6c757d';
    }
  };

  return (
    <div className="session-analyzer">
      <h2>Session Information</h2>
      <p>Upload a log file to analyze streaming session details and connection flow.</p>

      <div className="upload-section">
        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
          accept=".tar.bz2,.bz2,.tar,.log,.txt"
        />
        <button
          onClick={analyzeSessionFile}
          disabled={!file || loading}
          className="analyze-btn"
        >
          {loading ? 'Analyzing...' : 'Analyze Sessions'}
        </button>
      </div>

      <div className="date-range-filter">
        <h3>Date/Time Range Filter (Optional)</h3>
        <p>Filter analysis to include only sessions within the specified date/time range</p>

        <div className="date-inputs">
          <div className="date-group">
            <label>From:</label>
            <input
              type="date"
              value={dateRange.startDate}
              onChange={(e) => setDateRange(prev => ({...prev, startDate: e.target.value}))}
              placeholder="Start date"
            />
            <input
              type="time"
              value={dateRange.startTime}
              onChange={(e) => setDateRange(prev => ({...prev, startTime: e.target.value}))}
              placeholder="Start time"
            />
          </div>

          <div className="date-group">
            <label>To:</label>
            <input
              type="date"
              value={dateRange.endDate}
              onChange={(e) => setDateRange(prev => ({...prev, endDate: e.target.value}))}
              placeholder="End date"
            />
            <input
              type="time"
              value={dateRange.endTime}
              onChange={(e) => setDateRange(prev => ({...prev, endTime: e.target.value}))}
              placeholder="End time"
            />
          </div>
        </div>
      </div>

      {error && (
        <div className="error-message">
          Error: {error}
        </div>
      )}

      {sessionData && (
        <div className="session-results">
          <div className="sessions-overview">
            <h3>Sessions Overview</h3>
            <div className="overview-stats">
              <div className="stat-card">
                <h4>Total Sessions</h4>
                <span className="stat-value">{sessionData.total_sessions || 0}</span>
              </div>
              <div className="stat-card">
                <h4>Successful Connections</h4>
                <span className="stat-value">{sessionData.successful_sessions || 0}</span>
              </div>
              <div className="stat-card">
                <h4>Failed Connections</h4>
                <span className="stat-value">{sessionData.failed_sessions || 0}</span>
              </div>
              <div className="stat-card">
                <h4>Average Setup Time</h4>
                <span className="stat-value">{formatDuration(sessionData.avg_setup_time)}</span>
              </div>
              <div className="stat-card">
                <h4>Average Session Duration</h4>
                <span className="stat-value">{formatDuration(sessionData.avg_session_duration)}</span>
              </div>
            </div>
          </div>

          {sessionData.sessions && sessionData.sessions.length > 0 && (
            <div className="sessions-list">
              <h3>Session Details</h3>
              {sessionData.sessions.map((session, index) => (
                <div key={index} className="session-card">
                  <div className="session-header">
                    <h4>Session #{session.session_id || 'Unknown'}</h4>
                    <span
                      className="session-status"
                      style={{ color: getStatusColor(session.final_status) }}
                    >
                      {session.final_status || 'Unknown'}
                    </span>
                  </div>

                  <div className="session-content">
                    <div className="session-info">
                      <div className="info-section">
                        <h5>Connection Info</h5>
                        <div className="info-grid">
                          <div className="info-item">
                            <label>Unit:</label>
                            <span>{session.unit_name || 'N/A'}</span>
                          </div>
                          <div className="info-item">
                            <label>Server Instance:</label>
                            <span>{session.server_instance || 'N/A'}</span>
                          </div>
                          <div className="info-item">
                            <label>Server Version:</label>
                            <span>{session.server_version || 'N/A'}</span>
                          </div>
                          <div className="info-item">
                            <label>Start Time:</label>
                            <span>{formatTimestamp(session.start_time)}</span>
                          </div>
                          <div className="info-item">
                            <label>End Time:</label>
                            <span>{formatTimestamp(session.end_time)}</span>
                          </div>
                          <div className="info-item">
                            <label>Session Duration:</label>
                            <span>{formatDuration(session.session_duration)}</span>
                          </div>
                          <div className="info-item">
                            <label>Setup Duration:</label>
                            <span>{formatDuration(session.setup_duration)}</span>
                          </div>
                        </div>
                      </div>

                      {session.network_config && (
                        <div className="info-section">
                          <h5>Network Configuration</h5>
                          <div className="info-grid">
                            <div className="info-item">
                              <label>Collector Address:</label>
                              <span>{session.network_config.collector_address || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>IFB Address:</label>
                              <span>{session.network_config.ifb_address || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>STUN Server:</label>
                              <span>{session.network_config.stun_server || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>Video Port:</label>
                              <span>{session.network_config.video_port || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>Audio Ports:</label>
                              <span>{session.network_config.audio_ports?.join(', ') || 'N/A'}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {session.streaming_config && (
                        <div className="info-section">
                          <h5>Streaming Configuration</h5>
                          <div className="info-grid">
                            <div className="info-item">
                              <label>Profile:</label>
                              <span>{session.streaming_config.profile || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>Active Links:</label>
                              <span>{session.streaming_config.active_links || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>Bonding Spare Delay:</label>
                              <span>{session.streaming_config.spare_delay || 'N/A'}</span>
                            </div>
                            <div className="info-item">
                              <label>Encryption:</label>
                              <span>{session.streaming_config.encryption ? 'Enabled' : 'Disabled'}</span>
                            </div>
                          </div>
                        </div>
                      )}

                      {session.state_timeline && session.state_timeline.length > 0 && (
                        <div className="info-section">
                          <h5>Connection Timeline</h5>
                          <div className="timeline">
                            {session.state_timeline.map((state, idx) => (
                              <div key={idx} className="timeline-item">
                                <div className="timeline-marker"></div>
                                <div className="timeline-content">
                                  <div className="timeline-header">
                                    <span className="timeline-state">{state.state}</span>
                                    <span className="timeline-time">{formatTimestamp(state.timestamp)}</span>
                                  </div>
                                  {state.duration && (
                                    <div className="timeline-duration">
                                      Duration: {formatDuration(state.duration)}
                                    </div>
                                  )}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SessionAnalyzer;