// Dashboard script: Live clock (12-hour format) & fully dynamic attendance charts
document.addEventListener('DOMContentLoaded', function () {
  // 1. Live Clock (12-hour format with AM/PM)
  const clockEl = document.getElementById('currentDateTime');
  function updateClock() {
    if (!clockEl) return;
    const now = new Date();
    const day = String(now.getDate()).padStart(2, '0');
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const year = now.getFullYear();
    let rawHours = now.getHours();
    const ampm = rawHours >= 12 ? 'PM' : 'AM';
    let hours = rawHours % 12;
    hours = hours ? hours : 12;
    const hoursStr = String(hours).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    const seconds = String(now.getSeconds()).padStart(2, '0');
    clockEl.textContent = `${day}/${month}/${year} ${hoursStr}:${minutes}:${seconds} ${ampm}`;
  }
  updateClock();
  setInterval(updateClock, 1000);

  // 2. Parse Dynamic Stats Data from Server
  let stats = {
    total: 0,
    present: 0,
    absent: 0,
    present_percentage: 0.0,
    timeout: 0,
    last_7_days: [],
    monthly_stats: []
  };

  const dataScript = document.getElementById('statsData');
  if (dataScript && dataScript.textContent) {
    try {
      stats = JSON.parse(dataScript.textContent);
    } catch (e) {
      console.error('Failed to parse dynamic stats:', e);
    }
  }

  // 3. Render Dynamic Last 7 Days Attendance Line Chart
  const lineCtx = document.getElementById('last7DaysChart');
  if (lineCtx && typeof Chart !== 'undefined') {
    let lineLabels = [];
    let lineData = [];

    if (stats.last_7_days && stats.last_7_days.length > 0) {
      lineLabels = stats.last_7_days.map(d => d.date);
      lineData = stats.last_7_days.map(d => (d.count !== undefined ? d.count : (d.present !== undefined ? d.present : 0)));
    } else {
      // Default dates if empty
      for (let i = 6; i >= 0; i--) {
        const d = new Date();
        d.setDate(d.getDate() - i);
        lineLabels.push(d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }));
        lineData.push(0);
      }
    }

    const maxLineVal = Math.max(...lineData, stats.total || 1);

    new Chart(lineCtx, {
      type: 'line',
      data: {
        labels: lineLabels,
        datasets: [{
          label: 'Employees Present',
          data: lineData,
          borderColor: '#00a8ff',
          backgroundColor: 'rgba(56, 189, 248, 0.15)',
          pointBackgroundColor: '#00a8ff',
          pointBorderColor: '#ffffff',
          pointBorderWidth: 2,
          pointRadius: 5,
          pointHoverRadius: 7,
          fill: true,
          tension: 0.25
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
              boxWidth: 18,
              boxHeight: 10,
              color: '#334155',
              font: { size: 11, weight: '600' }
            }
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return `Present: ${ctx.parsed.y} employee(s)`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: Math.max(2, maxLineVal + 1),
            ticks: {
              stepSize: 1,
              precision: 0,
              color: '#64748b',
              font: { size: 10 }
            },
            grid: {
              color: '#f1f5f9'
            }
          },
          x: {
            ticks: {
              color: '#64748b',
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

  // 4. Render Dynamic Monthly Attendance Bar Chart
  const barCtx = document.getElementById('monthlyAttendanceChart');
  if (barCtx && typeof Chart !== 'undefined') {
    let monthLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    let monthData = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];

    if (stats.monthly_stats && stats.monthly_stats.length > 0) {
      monthLabels = stats.monthly_stats.map(m => m.month);
      monthData = stats.monthly_stats.map(m => (m.count !== undefined ? m.count : 0));
    }

    const maxMonthVal = Math.max(...monthData, 5);

    new Chart(barCtx, {
      type: 'bar',
      data: {
        labels: monthLabels,
        datasets: [{
          label: 'Total Attendance Punches',
          data: monthData,
          backgroundColor: '#38bdf8',
          hoverBackgroundColor: '#0284c7',
          borderRadius: 4,
          borderWidth: 0,
          barPercentage: 0.65
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
              boxWidth: 18,
              boxHeight: 10,
              color: '#334155',
              font: { size: 11, weight: '600' }
            }
          },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return `Attendance: ${ctx.parsed.y} punches`;
              }
            }
          }
        },
        scales: {
          y: {
            beginAtZero: true,
            suggestedMax: Math.max(5, maxMonthVal + 2),
            ticks: {
              stepSize: 1,
              precision: 0,
              color: '#64748b',
              font: { size: 10 }
            },
            grid: {
              color: '#f1f5f9'
            }
          },
          x: {
            ticks: {
              color: '#64748b',
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
});
