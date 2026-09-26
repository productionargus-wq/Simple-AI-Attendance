// Dashboard script: Live clock & attendance charts
document.addEventListener('DOMContentLoaded', function () {
  // 1. Live Clock
  const clockEl = document.getElementById('currentDateTime');
  function updateClock() {
    if (!clockEl) return;
    const now = new Date();
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const year = now.getFullYear();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    clockEl.textContent = `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
  }
  updateClock();
  setInterval(updateClock, 1000);

  // 2. Parse Stats Data
  let stats = {
    total: 3,
    present: 0,
    absent: 3,
    present_percent: "0.0%",
    timeout: 0,
    last_7_days: [],
    monthly_attendance: 14
  };

  const dataScript = document.getElementById('statsData');
  if (dataScript && dataScript.textContent) {
    try {
      stats = JSON.parse(dataScript.textContent);
    } catch (e) {
      console.error('Failed to parse stats:', e);
    }
  }

  // 3. Render Last 7 Days Attendance Line Chart
  const lineCtx = document.getElementById('last7DaysChart');
  if (lineCtx && typeof Chart !== 'undefined') {
    const lineLabels = stats.last_7_days.map(d => d.date);
    const lineData = stats.last_7_days.map(d => d.present);

    new Chart(lineCtx, {
      type: 'line',
      data: {
        labels: lineLabels.length ? lineLabels : ['2026-09-21', '2026-09-22', '2026-09-23', '2026-09-24', '2026-09-25'],
        datasets: [{
          label: 'Employees Present',
          data: lineData.length ? lineData : [1.0, 1.0, 1.0, 1.0, 1.0],
          borderColor: '#00a8ff',
          backgroundColor: '#38bdf8',
          pointBackgroundColor: '#00a8ff',
          pointBorderColor: '#00a8ff',
          pointRadius: 4,
          pointHoverRadius: 6,
          fill: false,
          tension: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            align: 'center',
            labels: {
              boxWidth: 28,
              boxHeight: 12,
              color: '#555555',
              font: { size: 12 }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: false,
            suggestedMin: 0.84,
            suggestedMax: 1.06,
            ticks: {
              stepSize: 0.02,
              callback: function (val) {
                return Number(val).toFixed(2);
              },
              color: '#888888',
              font: { size: 10 }
            },
            grid: {
              color: '#e9ecef'
            }
          },
          x: {
            ticks: {
              color: '#888888',
              font: { size: 10 }
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }

  // 4. Render Monthly Attendance Bar Chart
  const barCtx = document.getElementById('monthlyAttendanceChart');
  if (barCtx && typeof Chart !== 'undefined') {
    new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: ['Monthly Attendance'],
        datasets: [{
          label: 'Unique Daily Entries',
          data: [stats.monthly_attendance || 14],
          backgroundColor: '#93c5fd',
          borderColor: '#93c5fd',
          borderWidth: 1,
          barPercentage: 0.7
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'top',
            align: 'center',
            labels: {
              boxWidth: 28,
              boxHeight: 12,
              color: '#555555',
              font: { size: 12 }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            max: 14,
            ticks: {
              stepSize: 2,
              color: '#888888',
              font: { size: 10 }
            },
            grid: {
              color: '#e9ecef'
            }
          },
          x: {
            ticks: {
              color: '#888888',
              font: { size: 11 }
            },
            grid: {
              display: false
            }
          }
        }
      }
    });
  }
});
