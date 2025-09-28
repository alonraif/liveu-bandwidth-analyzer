import React, { useState } from 'react';
import './App.css';
import { BandwidthChart, AggregatedBandwidthChart, RTTChart, PacketLossChart } from './Charts';

function App() {
  const [file, setFile] = useState(null);
  const [sessionId, setSessionId] = useState(null);
  const [data, setData] = useState(null);
  const [logMergerFile, setLogMergerFile] = useState(null);
  const [mergeStatus, setMergeStatus] = useState(null);
  const [activeTab, setActiveTab] = useState('bandwidth');
  const [dateRange, setDateRange] = useState({
    startDate: '',
    endDate: '',
    startTime: '',
    endTime: ''
  });
  const [bandwidthDateRange, setBandwidthDateRange] = useState({
    startDate: '',
    endDate: '',
    startTime: '',
    endTime: ''
  });

  const handleUpload = async () => {
    const formData = new FormData();
    formData.append('file', file);

    // Add bandwidth analysis date range parameters if provided
    if (bandwidthDateRange.startDate || bandwidthDateRange.startTime) {
      const startDateTime = `${bandwidthDateRange.startDate} ${bandwidthDateRange.startTime || '00:00:00'}`;
      formData.append('time_start', startDateTime);
    }

    if (bandwidthDateRange.endDate || bandwidthDateRange.endTime) {
      const endDateTime = `${bandwidthDateRange.endDate} ${bandwidthDateRange.endTime || '23:59:59'}`;
      formData.append('time_end', endDateTime);
    }

    try {
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData
      });
      const result = await res.json();
      setSessionId(result.session_id);
      pollStatus(result.session_id);
    } catch (err) {
      console.error(err);
    }
  };

  const pollStatus = async (id) => {
    const interval = setInterval(async () => {
      const res = await fetch(`/api/sessions/${id}/status`);
      const status = await res.json();
      
      if (status.status === 'completed') {
        clearInterval(interval);
        fetchData(id);
      }
    }, 2000);
  };

  const fetchData = async (id) => {
    const res = await fetch(`/api/sessions/${id}/data`);
    const result = await res.json();
    setData(result);
  };

  const handleLogMerge = async () => {
    if (!logMergerFile) return;

    const formData = new FormData();
    formData.append('file', logMergerFile);

    // Add date range parameters if provided
    if (dateRange.startDate || dateRange.startTime) {
      const startDateTime = `${dateRange.startDate} ${dateRange.startTime || '00:00:00'}`;
      formData.append('start_datetime', startDateTime);
    }

    if (dateRange.endDate || dateRange.endTime) {
      const endDateTime = `${dateRange.endDate} ${dateRange.endTime || '23:59:59'}`;
      formData.append('end_datetime', endDateTime);
    }

    try {
      setMergeStatus('processing');
      const res = await fetch('/api/merge-logs', {
        method: 'POST',
        body: formData
      });
      const result = await res.json();

      if (result.success) {
        setMergeStatus('completed');
      } else {
        setMergeStatus('error');
      }
    } catch (err) {
      console.error(err);
      setMergeStatus('error');
    }
  };

  const downloadMergedLogs = async () => {
    if (!logMergerFile) return;

    const formData = new FormData();
    formData.append('file', logMergerFile);

    // Add date range parameters if provided
    if (dateRange.startDate || dateRange.startTime) {
      const startDateTime = `${dateRange.startDate} ${dateRange.startTime || '00:00:00'}`;
      formData.append('start_datetime', startDateTime);
    }

    if (dateRange.endDate || dateRange.endTime) {
      const endDateTime = `${dateRange.endDate} ${dateRange.endTime || '23:59:59'}`;
      formData.append('end_datetime', endDateTime);
    }

    try {
      const res = await fetch('/api/merge-logs/download', {
        method: 'POST',
        body: formData
      });

      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');

        // Include date range in filename if specified
        let filename = `merged_messages_${logMergerFile.name.replace(/\.(tar\.)?bz2|\.tar$/g, '')}`;
        if (dateRange.startDate || dateRange.endDate) {
          const start = dateRange.startDate || 'start';
          const end = dateRange.endDate || 'end';
          filename += `_${start}_to_${end}`;
        }
        filename += '.txt';

        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else {
        console.error('Download failed');
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="App">
      <h1>LiveU Bandwidth Analyzer</h1>

      <div className="tabs">
        <button
          onClick={() => setActiveTab('bandwidth')}
          className={activeTab === 'bandwidth' ? 'active' : ''}
        >
          Bandwidth Analysis
        </button>
        <button
          onClick={() => setActiveTab('logmerger')}
          className={activeTab === 'logmerger' ? 'active' : ''}
        >
          Log Merger
        </button>
      </div>

      {activeTab === 'bandwidth' && (
        <div className="bandwidth-tab">
          <h2>Bandwidth Analysis</h2>
          <p>Upload a compressed log archive to extract and analyze bandwidth metrics.</p>

          <input
            type="file"
            onChange={(e) => setFile(e.target.files[0])}
            accept=".tar.bz2,.bz2,.tar"
          />

          <div className="date-range-filter">
            <h3>Date/Time Range Filter (Optional)</h3>
            <p>Filter analysis to include only data within the specified date/time range</p>

            <div className="date-inputs">
              <div className="date-group">
                <label>From:</label>
                <input
                  type="date"
                  value={bandwidthDateRange.startDate}
                  onChange={(e) => setBandwidthDateRange(prev => ({...prev, startDate: e.target.value}))}
                  placeholder="Start date"
                />
                <input
                  type="time"
                  value={bandwidthDateRange.startTime}
                  onChange={(e) => setBandwidthDateRange(prev => ({...prev, startTime: e.target.value}))}
                  placeholder="Start time"
                />
              </div>

              <div className="date-group">
                <label>To:</label>
                <input
                  type="date"
                  value={bandwidthDateRange.endDate}
                  onChange={(e) => setBandwidthDateRange(prev => ({...prev, endDate: e.target.value}))}
                  placeholder="End date"
                />
                <input
                  type="time"
                  value={bandwidthDateRange.endTime}
                  onChange={(e) => setBandwidthDateRange(prev => ({...prev, endTime: e.target.value}))}
                  placeholder="End time"
                />
              </div>
            </div>

            <button
              type="button"
              className="clear-button"
              onClick={() => setBandwidthDateRange({startDate: '', endDate: '', startTime: '', endTime: ''})}
            >
              Clear Date Range
            </button>
          </div>

          <div className="bandwidth-actions">
            <button onClick={handleUpload} disabled={!file}>
              Upload & Analyze
            </button>
          </div>

          {sessionId && <p>Session: {sessionId}</p>}
          {data && (
            <div className="results">
              <h3>Streaming Session Analysis</h3>
              {bandwidthDateRange.startDate || bandwidthDateRange.endDate ? (
                <p className="filter-info">
                  📅 Date range filter applied:
                  {bandwidthDateRange.startDate && ` From ${bandwidthDateRange.startDate} ${bandwidthDateRange.startTime || '00:00'}`}
                  {bandwidthDateRange.endDate && ` To ${bandwidthDateRange.endDate} ${bandwidthDateRange.endTime || '23:59'}`}
                </p>
              ) : null}

              {data.analytics && (
                <div className="analytics-dashboard">
                  {/* Session Overview */}
                  <div className="analytics-section">
                    <h4>Session Overview</h4>
                    <div className="stats-grid">
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.overall_statistics.modem_count || 0}</div>
                        <div className="stat-label">Active Modems</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.session_duration_seconds / 60).toFixed(1)}m</div>
                        <div className="stat-label">Session Duration</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.overall_statistics.total_measurements || 0}</div>
                        <div className="stat-label">Data Points</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.quality_insights.reliability_score.toFixed(1)}%</div>
                        <div className="stat-label">Reliability Score</div>
                      </div>
                    </div>
                  </div>

                  {/* Bandwidth Performance */}
                  <div className="analytics-section">
                    <h4>Bandwidth Performance</h4>
                    <div className="stats-grid">
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.total_bandwidth || 0).toFixed(2)} Mbps</div>
                        <div className="stat-label">Total Bandwidth</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.avg_bandwidth || 0).toFixed(2)} Mbps</div>
                        <div className="stat-label">Average Bandwidth</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.max_bandwidth || 0).toFixed(2)} Mbps</div>
                        <div className="stat-label">Peak Bandwidth</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.avg_packet_loss || 0).toFixed(2)}%</div>
                        <div className="stat-label">Avg Packet Loss</div>
                      </div>
                    </div>
                  </div>

                  {/* Network Quality */}
                  <div className="analytics-section">
                    <h4>Network Quality</h4>
                    <div className="stats-grid">
                      <div className="stat-card">
                        <div className="stat-value">{(data.analytics.overall_statistics.avg_rtt || 0).toFixed(0)}ms</div>
                        <div className="stat-label">Average Latency</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.quality_insights.high_loss_samples || 0}</div>
                        <div className="stat-label">High Loss Events</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.quality_insights.high_latency_samples || 0}</div>
                        <div className="stat-label">High Latency Events</div>
                      </div>
                      <div className="stat-card">
                        <div className="stat-value">{data.analytics.quality_insights.low_bandwidth_samples || 0}</div>
                        <div className="stat-label">Low Bandwidth Events</div>
                      </div>
                    </div>
                  </div>

                  {/* Per-Modem Statistics */}
                  {data.analytics.per_modem_statistics.length > 0 && (
                    <div className="analytics-section">
                      <h4>Per-Modem Performance</h4>
                      <div className="modem-stats">
                        {data.analytics.per_modem_statistics.map((modem, index) => (
                          <div key={index} className="modem-card">
                            <h5>Modem {modem.modem_id}</h5>
                            <div className="modem-metrics">
                              <div className="metric">
                                <span className="metric-label">Bandwidth:</span>
                                <span className="metric-value">{modem.avg_bandwidth.toFixed(2)} Mbps avg</span>
                              </div>
                              <div className="metric">
                                <span className="metric-label">Packet Loss:</span>
                                <span className="metric-value">{modem.avg_packet_loss.toFixed(2)}% avg</span>
                              </div>
                              <div className="metric">
                                <span className="metric-label">Latency:</span>
                                <span className="metric-value">{modem.avg_rtt.toFixed(0)}ms avg</span>
                              </div>
                              <div className="metric">
                                <span className="metric-label">Samples:</span>
                                <span className="metric-value">{modem.measurement_count}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Charts Section */}
                  <div className="analytics-section">
                    <h4>Performance Graphs</h4>

                    <div className="chart-container">
                      <h5>Bandwidth Per Modem Over Time</h5>
                      <BandwidthChart data={data.data} title="Bandwidth per Modem" />
                    </div>

                    <div className="chart-container">
                      <h5>Total Aggregated Bandwidth Over Time</h5>
                      <AggregatedBandwidthChart data={data.data} />
                    </div>

                    <div className="chart-container">
                      <h5>RTT (Round Trip Time) Per Modem Over Time</h5>
                      <RTTChart data={data.data} />
                    </div>

                    <div className="chart-container">
                      <h5>Packet Loss Percentage Per Modem Over Time</h5>
                      <PacketLossChart data={data.data} />
                    </div>
                  </div>
                </div>
              )}

              {!data.analytics && (
                <div className="no-data">
                  <p>No modem statistics found in the uploaded logs.</p>
                  <p>Make sure your logs contain LiveU modem statistics in the expected format.</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'logmerger' && (
        <div className="logmerger-tab">
          <h2>Messages Log Merger</h2>
          <p>Upload a compressed log archive to merge all messages.log files in chronological order.</p>

          <input
            type="file"
            onChange={(e) => setLogMergerFile(e.target.files[0])}
            accept=".tar.bz2,.bz2,.tar"
          />

          <div className="date-range-filter">
            <h3>Date/Time Range Filter (Optional)</h3>
            <p>Filter logs to include only entries within the specified date/time range</p>

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

            <button
              type="button"
              className="clear-button"
              onClick={() => setDateRange({startDate: '', endDate: '', startTime: '', endTime: ''})}
            >
              Clear Date Range
            </button>
          </div>

          <div className="logmerger-actions">
            <button
              onClick={handleLogMerge}
              disabled={!logMergerFile || mergeStatus === 'processing'}
            >
              {mergeStatus === 'processing' ? 'Processing...' : 'Process Logs'}
            </button>

            <button
              onClick={downloadMergedLogs}
              disabled={!logMergerFile}
            >
              Download Merged Logs
            </button>
          </div>

          {mergeStatus === 'completed' && (
            <div className="status success">
              ✅ Logs processed successfully! You can now download the merged file.
            </div>
          )}

          {mergeStatus === 'error' && (
            <div className="status error">
              ❌ Error processing logs. Please check the file format.
            </div>
          )}

          {logMergerFile && (
            <div className="file-info">
              <p><strong>Selected file:</strong> {logMergerFile.name}</p>
              <p><strong>Size:</strong> {(logMergerFile.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;