import React, { useEffect, useRef } from 'react';

const ModemColors = [
  '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40',
  '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384', '#36A2EB', '#FFCE56'
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
    mode: 'xy',
    scaleMode: 'xy',
    onZoomComplete: function({chart}) {
      // Force tick regeneration for better time labels
      chart.update('none');
    }
  },
  pan: {
    enabled: true,
    mode: 'xy',
    scaleMode: 'xy',
    threshold: 10,
    modifierKey: null,
    onPanComplete: function({chart}) {
      // Force tick regeneration for better time labels
      chart.update('none');
    }
  },
  limits: {
    y: {min: 0, max: 'original'}
  }
});

// Zoom control buttons component
function ZoomControls({ chartRef }) {
  const resetZoom = () => {
    if (chartRef.current) {
      chartRef.current.resetZoom();
    }
  };

  return (
    <div className="chart-controls">
      <button onClick={resetZoom} className="zoom-button">
        Reset Zoom
      </button>
      <span className="zoom-help">
        💡 Mouse wheel to zoom, click and drag to pan
      </span>
    </div>
  );
}

function BandwidthChart({ data, title }) {
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
        x: new Date(point.time),
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
              text: 'Time'
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
  }, [data, title]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ZoomControls chartRef={chartInstance} />
    </div>
  );
}

function AggregatedBandwidthChart({ data }) {
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
      const originalTime = new Date(point.time);
      // Round to nearest second to group closely-timed measurements
      const roundedTime = new Date(originalTime.getFullYear(), originalTime.getMonth(), originalTime.getDate(),
                                   originalTime.getHours(), originalTime.getMinutes(), originalTime.getSeconds());
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
              text: 'Time'
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
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ZoomControls chartRef={chartInstance} />
    </div>
  );
}

function RTTChart({ data }) {
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
        x: new Date(point.time),
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
              text: 'Time'
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
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ZoomControls chartRef={chartInstance} />
    </div>
  );
}

function PacketLossChart({ data }) {
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
        x: new Date(point.time),
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
              text: 'Time'
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
  }, [data]);

  return (
    <div style={{ position: 'relative', width: '100%' }}>
      <div style={{ height: '400px' }}>
        <canvas ref={chartRef}></canvas>
      </div>
      <ZoomControls chartRef={chartInstance} />
    </div>
  );
}

export { BandwidthChart, AggregatedBandwidthChart, RTTChart, PacketLossChart };