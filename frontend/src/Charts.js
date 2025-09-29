import React, { useEffect, useRef } from 'react';

// Chart.js plugins are registered in index.html

// Helper function to convert UTC timestamp to target timezone
const convertTimezone = (utcTimestamp, targetTimezone) => {
  try {
    // Parse the original timestamp (which is in UTC)
    const originalDate = new Date(utcTimestamp);

    if (isNaN(originalDate.getTime())) {
      console.warn('Invalid timestamp:', utcTimestamp);
      return new Date();
    }

    if (targetTimezone === 'UTC') {
      // For UTC, we need to create a date that displays the UTC time values
      // but in local context so Chart.js doesn't convert it again
      const utcYear = originalDate.getUTCFullYear();
      const utcMonth = originalDate.getUTCMonth();
      const utcDate = originalDate.getUTCDate();
      const utcHours = originalDate.getUTCHours();
      const utcMinutes = originalDate.getUTCMinutes();
      const utcSeconds = originalDate.getUTCSeconds();
      const utcMs = originalDate.getUTCMilliseconds();

      const localizedUTC = new Date(utcYear, utcMonth, utcDate, utcHours, utcMinutes, utcSeconds, utcMs);
      console.log('UTC conversion:', utcTimestamp, '-> local representation:', localizedUTC);
      return localizedUTC;
    }

    // For other timezones, convert from UTC to target timezone
    const targetFormatter = new Intl.DateTimeFormat('sv-SE', { // ISO format
      timeZone: targetTimezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    });

    const targetTimeString = targetFormatter.format(originalDate);
    const targetDate = new Date(targetTimeString);

    console.log('Timezone conversion:', utcTimestamp, 'UTC ->', targetTimeString, targetTimezone);
    return targetDate;
  } catch (error) {
    console.warn('Timezone conversion failed:', error, 'for timestamp:', utcTimestamp);
    return new Date(utcTimestamp);
  }
};

const ModemColors = [
  '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
  '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384', '#36A2EB', '#FFCE56'
];

// Timezone options
const TIMEZONE_OPTIONS = [
  { value: 'UTC', label: 'UTC' },
  { value: 'America/New_York', label: 'Eastern Time' },
  { value: 'America/Chicago', label: 'Central Time' },
  { value: 'America/Denver', label: 'Mountain Time' },
  { value: 'America/Los_Angeles', label: 'Pacific Time' },
  { value: 'Europe/London', label: 'London Time' },
  { value: 'Europe/Paris', label: 'Central European Time' },
  { value: 'Asia/Tokyo', label: 'Japan Time' },
  { value: 'Asia/Shanghai', label: 'China Time' },
  { value: 'Australia/Sydney', label: 'Australian Eastern Time' }
];

// Common zoom configuration for all charts
const getZoomConfig = () => ({
  zoom: {
    wheel: {
      enabled: true,
      speed: 0.1,
    },
    pinch: {
      enabled: true
    },
    drag: {
      enabled: true,
      modifierKey: 'shift'
    },
    mode: 'xy'
  },
  pan: {
    enabled: true,
    mode: 'xy'
  }
});

// Chart controls component with zoom and timezone
function ChartControls({ chartRef, timezone, onTimezoneChange }) {
  const resetZoom = () => {
    if (chartRef.current) {
      chartRef.current.resetZoom();
    }
  };

  return (
    <div className="chart-controls">
      <div className="control-group">
        <button onClick={resetZoom} className="zoom-button">
          Reset Zoom
        </button>
        <span className="zoom-help">
          💡 Mouse wheel to zoom, drag to pan, Shift+drag to zoom box
        </span>
      </div>
      <div className="control-group">
        <label htmlFor="timezone-select" className="timezone-label">
          Timezone:
        </label>
        <select
          id="timezone-select"
          value={timezone}
          onChange={(e) => onTimezoneChange(e.target.value)}
          className="timezone-select"
        >
          {TIMEZONE_OPTIONS.map(option => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

function BandwidthChart({ data, title, timezone = 'UTC', onTimezoneChange }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const ctx = chartRef.current.getContext('2d');

    // Destroy existing chart
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    // Group data by modem
    const modemData = {};
    data.forEach(point => {
      if (!modemData[point.modem_id]) {
        modemData[point.modem_id] = [];
      }
      modemData[point.modem_id].push({
        x: convertTimezone(point.time, timezone),
        y: point.bandwidth_mbps
      });
    });

    // Create datasets for each modem
    const datasets = Object.keys(modemData).map((modemId, index) => ({
      label: `Modem ${modemId}`,
      data: modemData[modemId].sort((a, b) => a.x - b.x),
      borderColor: ModemColors[index % ModemColors.length],
      backgroundColor: ModemColors[index % ModemColors.length] + '20',
      fill: false,
      tension: 0.1,
      pointRadius: 1,
      pointHoverRadius: 3
    }));

    chartInstance.current = new window.Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: title
          },
          legend: {
            display: true,
            position: 'top'
          },
          zoom: getZoomConfig()
        },
        scales: {
          x: {
            type: 'time',
            time: {
              minUnit: 'second',
              displayFormats: {
                second: 'HH:mm:ss',
                minute: 'HH:mm',
                hour: 'MMM dd HH:mm',
                day: 'MMM dd',
                week: 'MMM dd',
                month: 'MMM yyyy',
                quarter: 'MMM yyyy',
                year: 'yyyy'
              },
              tooltipFormat: 'MMM dd, yyyy HH:mm:ss'
            },
            title: {
              display: true,
              text: `Time (${timezone === 'UTC' ? 'UTC' : TIMEZONE_OPTIONS.find(tz => tz.value === timezone)?.label || timezone})`
            },
            ticks: {
              source: 'auto',
              autoSkip: true,
              maxTicksLimit: 20
            }
          },
          y: {
            title: {
              display: true,
              text: 'Bandwidth (Mbps)'
            },
            beginAtZero: true
          }
        },
        interaction: {
          intersect: false,
          mode: 'index'
        }
      }
    });

    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [data, title, timezone]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ChartControls chartRef={chartInstance} timezone={timezone} onTimezoneChange={onTimezoneChange} />
    </div>
  );
}

function AggregatedBandwidthChart({ data, timezone = 'UTC', onTimezoneChange }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const ctx = chartRef.current.getContext('2d');

    // Destroy existing chart
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    // Group by time (rounded to nearest second) and sum bandwidth
    const timeGroups = {};
    data.forEach(point => {
      const convertedTime = convertTimezone(point.time, timezone);
      // Round to nearest second to group closely-timed measurements
      const roundedTime = new Date(convertedTime.getFullYear(), convertedTime.getMonth(), convertedTime.getDate(),
                                   convertedTime.getHours(), convertedTime.getMinutes(), convertedTime.getSeconds());
      const timeKey = roundedTime.getTime();

      if (!timeGroups[timeKey]) {
        timeGroups[timeKey] = { time: roundedTime, totalBandwidth: 0 };
      }
      timeGroups[timeKey].totalBandwidth += point.bandwidth_mbps;
    });

    const aggregatedData = Object.values(timeGroups)
      .sort((a, b) => a.time - b.time)
      .map(group => ({
        x: group.time,
        y: group.totalBandwidth
      }));

    chartInstance.current = new window.Chart(ctx, {
      type: 'line',
      data: {
        datasets: [{
          label: 'Total Aggregated Bandwidth',
          data: aggregatedData,
          borderColor: '#FF6384',
          backgroundColor: '#FF638420',
          fill: true,
          tension: 0.1,
          pointRadius: 1,
          pointHoverRadius: 3
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: 'Total Aggregated Bandwidth Over Time'
          },
          legend: {
            display: false
          },
          zoom: getZoomConfig()
        },
        scales: {
          x: {
            type: 'time',
            time: {
              minUnit: 'second',
              displayFormats: {
                second: 'HH:mm:ss',
                minute: 'HH:mm',
                hour: 'MMM dd HH:mm',
                day: 'MMM dd',
                week: 'MMM dd',
                month: 'MMM yyyy',
                quarter: 'MMM yyyy',
                year: 'yyyy'
              },
              tooltipFormat: 'MMM dd, yyyy HH:mm:ss'
            },
            title: {
              display: true,
              text: `Time (${timezone === 'UTC' ? 'UTC' : TIMEZONE_OPTIONS.find(tz => tz.value === timezone)?.label || timezone})`
            },
            ticks: {
              source: 'auto',
              autoSkip: true,
              maxTicksLimit: 20
            }
          },
          y: {
            title: {
              display: true,
              text: 'Total Bandwidth (Mbps)'
            },
            beginAtZero: true
          }
        },
        interaction: {
          intersect: false,
          mode: 'index'
        }
      }
    });

    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [data, timezone]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ChartControls chartRef={chartInstance} timezone={timezone} onTimezoneChange={onTimezoneChange} />
    </div>
  );
}

function RTTChart({ data, timezone = 'UTC', onTimezoneChange }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const ctx = chartRef.current.getContext('2d');

    // Destroy existing chart
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    // Group data by modem
    const modemData = {};
    data.forEach(point => {
      if (!modemData[point.modem_id]) {
        modemData[point.modem_id] = [];
      }
      modemData[point.modem_id].push({
        x: convertTimezone(point.time, timezone),
        y: point.smooth_rtt_ms
      });
    });

    // Create datasets for each modem
    const datasets = Object.keys(modemData).map((modemId, index) => ({
      label: `Modem ${modemId}`,
      data: modemData[modemId].sort((a, b) => a.x - b.x),
      borderColor: ModemColors[index % ModemColors.length],
      backgroundColor: ModemColors[index % ModemColors.length] + '20',
      fill: false,
      tension: 0.1,
      pointRadius: 1,
      pointHoverRadius: 3
    }));

    chartInstance.current = new window.Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: 'RTT (Round Trip Time) Over Time'
          },
          legend: {
            display: true,
            position: 'top'
          },
          zoom: getZoomConfig()
        },
        scales: {
          x: {
            type: 'time',
            time: {
              minUnit: 'second',
              displayFormats: {
                second: 'HH:mm:ss',
                minute: 'HH:mm',
                hour: 'MMM dd HH:mm',
                day: 'MMM dd',
                week: 'MMM dd',
                month: 'MMM yyyy',
                quarter: 'MMM yyyy',
                year: 'yyyy'
              },
              tooltipFormat: 'MMM dd, yyyy HH:mm:ss'
            },
            title: {
              display: true,
              text: `Time (${timezone === 'UTC' ? 'UTC' : TIMEZONE_OPTIONS.find(tz => tz.value === timezone)?.label || timezone})`
            },
            ticks: {
              source: 'auto',
              autoSkip: true,
              maxTicksLimit: 20
            }
          },
          y: {
            title: {
              display: true,
              text: 'RTT (ms)'
            },
            beginAtZero: true
          }
        },
        interaction: {
          intersect: false,
          mode: 'index'
        }
      }
    });

    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [data, timezone]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ChartControls chartRef={chartInstance} timezone={timezone} onTimezoneChange={onTimezoneChange} />
    </div>
  );
}

function PacketLossChart({ data, timezone = 'UTC', onTimezoneChange }) {
  const chartRef = useRef(null);
  const chartInstance = useRef(null);

  useEffect(() => {
    if (!data || data.length === 0) return;

    const ctx = chartRef.current.getContext('2d');

    // Destroy existing chart
    if (chartInstance.current) {
      chartInstance.current.destroy();
    }

    // Group data by modem
    const modemData = {};
    data.forEach(point => {
      if (!modemData[point.modem_id]) {
        modemData[point.modem_id] = [];
      }
      modemData[point.modem_id].push({
        x: convertTimezone(point.time, timezone),
        y: point.packet_loss_percent
      });
    });

    // Create datasets for each modem
    const datasets = Object.keys(modemData).map((modemId, index) => ({
      label: `Modem ${modemId}`,
      data: modemData[modemId].sort((a, b) => a.x - b.x),
      borderColor: ModemColors[index % ModemColors.length],
      backgroundColor: ModemColors[index % ModemColors.length] + '20',
      fill: false,
      tension: 0.1,
      pointRadius: 1,
      pointHoverRadius: 3
    }));

    chartInstance.current = new window.Chart(ctx, {
      type: 'line',
      data: { datasets },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          title: {
            display: true,
            text: 'Packet Loss Percentage Over Time'
          },
          legend: {
            display: true,
            position: 'top'
          },
          zoom: getZoomConfig()
        },
        scales: {
          x: {
            type: 'time',
            time: {
              minUnit: 'second',
              displayFormats: {
                second: 'HH:mm:ss',
                minute: 'HH:mm',
                hour: 'MMM dd HH:mm',
                day: 'MMM dd',
                week: 'MMM dd',
                month: 'MMM yyyy',
                quarter: 'MMM yyyy',
                year: 'yyyy'
              },
              tooltipFormat: 'MMM dd, yyyy HH:mm:ss'
            },
            title: {
              display: true,
              text: `Time (${timezone === 'UTC' ? 'UTC' : TIMEZONE_OPTIONS.find(tz => tz.value === timezone)?.label || timezone})`
            },
            ticks: {
              source: 'auto',
              autoSkip: true,
              maxTicksLimit: 20
            }
          },
          y: {
            title: {
              display: true,
              text: 'Packet Loss (%)'
            },
            beginAtZero: true,
            max: 100
          }
        },
        interaction: {
          intersect: false,
          mode: 'index'
        }
      }
    });

    return () => {
      if (chartInstance.current) {
        chartInstance.current.destroy();
      }
    };
  }, [data, timezone]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ChartControls chartRef={chartInstance} timezone={timezone} onTimezoneChange={onTimezoneChange} />
    </div>
  );
}

export { BandwidthChart, AggregatedBandwidthChart, RTTChart, PacketLossChart };