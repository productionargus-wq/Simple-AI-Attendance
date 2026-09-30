// Modern Dashboard Chart and UI initialization matching reference design
document.addEventListener('DOMContentLoaded', function () {
  // 1. Parse Dynamic Stats Data
  let stats = {
    total: 0,
    present: 0,
    absent: 0,
    present_percent: '0.0%',
    absent_percent: '0.0%',
    timeout: 0,
    timeout_percent: '0.0%',
    last_7_days: [],
    monthly_stats: [],
    today_attendance: [],
    department_summary: []
  };

  const dataScript = document.getElementById('statsData');
  if (dataScript && dataScript.textContent) {
    try {
      stats = JSON.parse(dataScript.textContent);
    } catch (e) {
      console.error('Failed to parse dynamic stats JSON:', e);
    }
  }

  // 2. Render Last 7 Days Attendance Line/Area Chart
  const lineCanvas = document.getElementById('last7DaysLineChart');
  if (lineCanvas && typeof Chart !== 'undefined') {
    const ctx = lineCanvas.getContext('2d');

    // Create subtle gradient fills
    const greenGradient = ctx.createLinearGradient(0, 0, 0, 240);
    greenGradient.addColorStop(0, 'rgba(16, 185, 129, 0.28)');
    greenGradient.addColorStop(1, 'rgba(16, 185, 129, 0.02)');

    const redGradient = ctx.createLinearGradient(0, 0, 0, 240);
    redGradient.addColorStop(0, 'rgba(239, 68, 68, 0.28)');
    redGradient.addColorStop(1, 'rgba(239, 68, 68, 0.02)');

    let lineLabels = [];
    let presentSeries = [];
    let absentSeries = [];
    let timeoutSeries = [];

    if (stats.last_7_days && stats.last_7_days.length > 0) {
      lineLabels = stats.last_7_days.map(d => d.date);
      presentSeries = stats.last_7_days.map(d => (d.present !== undefined ? d.present : (d.count || 0)));
      absentSeries = stats.last_7_days.map(d => (d.absent !== undefined ? d.absent : Math.max(0, (stats.total || 0) - (d.present || d.count || 0))));
      timeoutSeries = stats.last_7_days.map(d => (d.timeout !== undefined ? d.timeout : 0));
    } else {
      // Default last 7 days
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        lineLabels.push(d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }));
        presentSeries.push(0);
        absentSeries.push(0);
        timeoutSeries.push(0);
      }
    }

    const allLineVals = [...presentSeries, ...absentSeries, ...timeoutSeries];
    const maxVal = Math.max(...allLineVals, 6);

    new Chart(lineCanvas, {
      type: 'line',
      data: {
        labels: lineLabels,
        datasets: [
          {
            label: 'Present',
            data: presentSeries,
            borderColor: '#10b981',
            backgroundColor: greenGradient,
            pointBackgroundColor: '#10b981',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.35
          },
          {
            label: 'Absent',
            data: absentSeries,
            borderColor: '#ef4444',
            backgroundColor: redGradient,
            pointBackgroundColor: '#ef4444',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: true,
            tension: 0.35
          },
          {
            label: 'Timeout',
            data: timeoutSeries,
            borderColor: '#f59e0b',
            backgroundColor: 'transparent',
            pointBackgroundColor: '#f59e0b',
            pointBorderColor: '#ffffff',
            pointBorderWidth: 2,
            pointRadius: 4,
            pointHoverRadius: 6,
            fill: false,
            tension: 0.35
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: 'index',
          intersect: false
        },
        plugins: {
          legend: {
            position: 'top',
            align: 'center',
            labels: {
              usePointStyle: true,
              pointStyle: 'circle',
              boxWidth: 8,
              boxHeight: 8,
              padding: 18,
              color: '#334155',
              font: { size: 11, weight: '600' }
            }
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleFont: { size: 12, weight: '700' },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: Math.ceil((maxVal + 2) / 2) * 2,
            ticks: {
              stepSize: 2,
              precision: 0,
              color: '#94a3b8',
              font: { size: 11 }
            },
            grid: {
              color: '#f1f5f9',
              drawBorder: false
            }
          },
          x: {
            ticks: {
              color: '#64748b',
              font: { size: 11 }
            },
            grid: {
              display: false,
              drawBorder: false
            }
          }
        }
      }
    });
  }

  // 3. Render Monthly Attendance Grouped Bar Chart
  const barCanvas = document.getElementById('monthlyAttendanceBarChart');
  if (barCanvas && typeof Chart !== 'undefined') {
    const monthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    let mPresent = new Array(12).fill(0);
    let mAbsent = new Array(12).fill(0);
    let mTimeout = new Array(12).fill(0);

    if (stats.monthly_stats && stats.monthly_stats.length > 0) {
      stats.monthly_stats.forEach((m, idx) => {
        if (idx < 12) {
          mPresent[idx] = m.present !== undefined ? m.present : (m.count || 0);
          mAbsent[idx] = m.absent !== undefined ? m.absent : 0;
          mTimeout[idx] = m.timeout !== undefined ? m.timeout : 0;
        }
      });
    }

    const allBarVals = [...mPresent, ...mAbsent, ...mTimeout];
    const maxBarVal = Math.max(...allBarVals, 10);

    new Chart(barCanvas, {
      type: 'bar',
      data: {
        labels: monthNames,
        datasets: [
          {
            label: 'Present',
            data: mPresent,
            backgroundColor: '#10b981',
            borderRadius: 4,
            barPercentage: 0.7,
            categoryPercentage: 0.75
          },
          {
            label: 'Absent',
            data: mAbsent,
            backgroundColor: '#ef4444',
            borderRadius: 4,
            barPercentage: 0.7,
            categoryPercentage: 0.75
          },
          {
            label: 'Timeout',
            data: mTimeout,
            backgroundColor: '#f59e0b',
            borderRadius: 4,
            barPercentage: 0.7,
            categoryPercentage: 0.75
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            align: 'center',
            labels: {
              usePointStyle: true,
              pointStyle: 'circle',
              boxWidth: 8,
              boxHeight: 8,
              padding: 18,
              color: '#334155',
              font: { size: 11, weight: '600' }
            }
          },
          tooltip: {
            backgroundColor: '#0f172a',
            titleFont: { size: 12, weight: '700' },
            bodyFont: { size: 12 },
            padding: 10,
            cornerRadius: 6
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: Math.ceil((maxBarVal + 2) / 2) * 2,
            ticks: {
              stepSize: 2,
              precision: 0,
              color: '#94a3b8',
              font: { size: 11 }
            },
            grid: {
              color: '#f1f5f9',
              drawBorder: false
            }
          },
          x: {
            ticks: {
              color: '#64748b',
              font: { size: 11 }
            },
            grid: {
              display: false,
              drawBorder: false
            }
          }
        }
      }
    });
  }
});
