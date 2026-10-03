// Dynamic Dashboard: Live Polling, Interactive Range Selectors, KPI Updates, Chart Updates & Real-time Tables
document.addEventListener('DOMContentLoaded', function () {
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

  let lineChartInstance = null;
  let barChartInstance = null;
  let currentTrendDays = 7;
  let currentMonthlyMode = 'current';

  function escapeHtml(str) {
    if (str === null || str === undefined) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  // 1. Render KPIs
  function renderKPIs(data) {
    const elTotal = document.getElementById('statTotal');
    const elPresent = document.getElementById('statPresent');
    const elPresentPct = document.getElementById('statPresentPct');
    const elOnLeave = document.getElementById('statOnLeave');
    const elOnLeavePct = document.getElementById('statOnLeavePct');
    const elAbsent = document.getElementById('statAbsent');
    const elAbsentPct = document.getElementById('statAbsentPct');
    const elTimeout = document.getElementById('statTimeout');
    const elTimeoutPct = document.getElementById('statTimeoutPct');

    if (elTotal) elTotal.textContent = data.total !== undefined ? data.total : '0';
    if (elPresent) elPresent.textContent = data.present !== undefined ? data.present : '0';
    if (elPresentPct) elPresentPct.textContent = data.present_percent || (data.present_percentage ? data.present_percentage + '%' : '0.0%');
    if (elOnLeave) elOnLeave.textContent = data.on_leave !== undefined ? data.on_leave : '0';
    if (elOnLeavePct) elOnLeavePct.textContent = data.on_leave_percent || (data.on_leave_percentage ? data.on_leave_percentage + '%' : '0.0%');
    if (elAbsent) elAbsent.textContent = data.absent !== undefined ? data.absent : '0';
    if (elAbsentPct) elAbsentPct.textContent = data.absent_percent || (data.absent_percentage ? data.absent_percentage + '%' : '0.0%');
    if (elTimeout) elTimeout.textContent = data.timeout !== undefined ? data.timeout : '0';
    if (elTimeoutPct) elTimeoutPct.textContent = data.timeout_percent || (data.timeout_percentage ? data.timeout_percentage + '%' : '0.0%');
  }

  // 2. Render Line/Trend Chart
  function renderLineChart(dataList) {
    const lineCanvas = document.getElementById('last7DaysLineChart');
    if (!lineCanvas || typeof Chart === 'undefined') return;

    let items = (dataList && dataList.length > 0) ? dataList : [];
    if (items.length > currentTrendDays) {
      items = items.slice(items.length - currentTrendDays);
    }

    let lineLabels = [];
    let presentSeries = [];
    let absentSeries = [];
    let timeoutSeries = [];

    if (items.length > 0) {
      lineLabels = items.map(d => d.date);
      presentSeries = items.map(d => (d.present !== undefined ? d.present : (d.count || 0)));
      absentSeries = items.map(d => (d.absent !== undefined ? d.absent : Math.max(0, (stats.total || 0) - (d.present || d.count || 0))));
      timeoutSeries = items.map(d => (d.timeout !== undefined ? d.timeout : 0));
    } else {
      for (let i = currentTrendDays - 1; i >= 0; i--) {
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

    if (lineChartInstance) {
      lineChartInstance.data.labels = lineLabels;
      lineChartInstance.data.datasets[0].data = presentSeries;
      lineChartInstance.data.datasets[1].data = absentSeries;
      lineChartInstance.data.datasets[2].data = timeoutSeries;
      lineChartInstance.options.scales.y.suggestedMax = Math.ceil((maxVal + 2) / 2) * 2;
      lineChartInstance.update();
      return;
    }

    const ctx = lineCanvas.getContext('2d');
    const greenGradient = ctx.createLinearGradient(0, 0, 0, 240);
    greenGradient.addColorStop(0, 'rgba(16, 185, 129, 0.28)');
    greenGradient.addColorStop(1, 'rgba(16, 185, 129, 0.02)');

    const redGradient = ctx.createLinearGradient(0, 0, 0, 240);
    redGradient.addColorStop(0, 'rgba(239, 68, 68, 0.28)');
    redGradient.addColorStop(1, 'rgba(239, 68, 68, 0.02)');

    lineChartInstance = new Chart(lineCanvas, {
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

  // 3. Render Monthly Attendance Bar Chart
  function renderBarChart(monthlyList, rangeMode) {
    const barCanvas = document.getElementById('monthlyAttendanceBarChart');
    if (!barCanvas || typeof Chart === 'undefined') return;

    const allMonthNames = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    let mPresent = new Array(12).fill(0);
    let mAbsent = new Array(12).fill(0);
    let mTimeout = new Array(12).fill(0);

    if (monthlyList && monthlyList.length > 0) {
      monthlyList.forEach((m, idx) => {
        if (idx < 12) {
          mPresent[idx] = m.present !== undefined ? m.present : (m.count || 0);
          mAbsent[idx] = m.absent !== undefined ? m.absent : 0;
          mTimeout[idx] = m.timeout !== undefined ? m.timeout : 0;
        }
      });
    }

    const currentMonthIdx = new Date().getMonth(); // 0-11
    let displayLabels = allMonthNames;
    let dispPresent = mPresent;
    let dispAbsent = mAbsent;
    let dispTimeout = mTimeout;

    if (rangeMode === 'current') {
      const startIdx = Math.max(0, currentMonthIdx - 1);
      const endIdx = Math.min(12, currentMonthIdx + 2);
      displayLabels = allMonthNames.slice(startIdx, endIdx);
      dispPresent = mPresent.slice(startIdx, endIdx);
      dispAbsent = mAbsent.slice(startIdx, endIdx);
      dispTimeout = mTimeout.slice(startIdx, endIdx);
    } else if (rangeMode === 'last3') {
      const startIdx = Math.max(0, currentMonthIdx - 2);
      const endIdx = currentMonthIdx + 1;
      displayLabels = allMonthNames.slice(startIdx, endIdx);
      dispPresent = mPresent.slice(startIdx, endIdx);
      dispAbsent = mAbsent.slice(startIdx, endIdx);
      dispTimeout = mTimeout.slice(startIdx, endIdx);
    }

    const allBarVals = [...dispPresent, ...dispAbsent, ...dispTimeout];
    const maxBarVal = Math.max(...allBarVals, 10);

    if (barChartInstance) {
      barChartInstance.data.labels = displayLabels;
      barChartInstance.data.datasets[0].data = dispPresent;
      barChartInstance.data.datasets[1].data = dispAbsent;
      barChartInstance.data.datasets[2].data = dispTimeout;
      barChartInstance.options.scales.y.suggestedMax = Math.ceil((maxBarVal + 2) / 2) * 2;
      barChartInstance.update();
      return;
    }

    barChartInstance = new Chart(barCanvas, {
      type: 'bar',
      data: {
        labels: displayLabels,
        datasets: [
          {
            label: 'Present',
            data: dispPresent,
            backgroundColor: '#10b981',
            borderRadius: 4,
            barPercentage: 0.7,
            categoryPercentage: 0.75
          },
          {
            label: 'Absent',
            data: dispAbsent,
            backgroundColor: '#ef4444',
            borderRadius: 4,
            barPercentage: 0.7,
            categoryPercentage: 0.75
          },
          {
            label: 'Timeout',
            data: dispTimeout,
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

  // 4. Render Today's Attendance Table
  function renderTodayTable(todayList) {
    const tbody = document.getElementById('todayAttendanceTableBody');
    if (!tbody) return;

    if (!todayList || todayList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty">No attendance records today</td></tr>`;
      return;
    }

    const rows = todayList.slice(0, 6);
    tbody.innerHTML = rows.map((row, idx) => {
      let badgeHtml = '';
      if (row.status === 'Present') {
        badgeHtml = '<span class="table-badge badge-present">Present</span>';
      } else if (row.status === 'Timeout') {
        badgeHtml = '<span class="table-badge badge-timeout">Timeout</span>';
      } else if (row.status === 'On Leave' || row.status === 'Leave') {
        badgeHtml = '<span class="table-badge badge-leave">On Leave</span>';
      } else {
        badgeHtml = '<span class="table-badge badge-absent">Absent</span>';
      }

      return `
        <tr>
          <td class="text-muted">${idx + 1}</td>
          <td class="font-semibold text-dark">${escapeHtml(row.employee_name)}</td>
          <td>${escapeHtml(row.in_time || '-')}</td>
          <td>${escapeHtml(row.out_time || '-')}</td>
          <td>${escapeHtml(row.hours || '-')}</td>
          <td style="text-align: center;">${badgeHtml}</td>
        </tr>
      `;
    }).join('');
  }

  // 5. Render Department Wise Summary Table
  function renderDeptSummary(deptList) {
    const tbody = document.getElementById('deptSummaryTableBody');
    if (!tbody) return;

    if (!deptList || deptList.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" class="table-empty">No department summary data</td></tr>`;
      return;
    }

    tbody.innerHTML = deptList.map(dept => `
      <tr>
        <td class="font-semibold text-dark">${escapeHtml(dept.department || 'General')}</td>
        <td style="text-align: center; font-weight: 700;">${dept.total || 0}</td>
        <td style="text-align: center; color: #16a34a; font-weight: 700;">${dept.present || 0}</td>
        <td style="text-align: center; color: #8b5cf6; font-weight: 700;">${dept.leave || 0}</td>
        <td style="text-align: center; color: #dc2626; font-weight: 700;">${dept.absent || 0}</td>
        <td style="text-align: center; color: #d97706; font-weight: 700;">${dept.timeout || 0}</td>
      </tr>
    `).join('');
  }

  // 6. Dynamic Fetch
  async function fetchDynamicStats() {
    try {
      const res = await fetch('/api/dashboard/stats');
      if (!res.ok) return;
      const data = await res.json();
      stats = data;

      renderKPIs(stats);
      renderLineChart(stats.last_7_days);
      renderBarChart(stats.monthly_stats, currentMonthlyMode);
      renderTodayTable(stats.today_attendance);
      renderDeptSummary(stats.department_summary);
    } catch (err) {
      console.warn('Dashboard live refresh error:', err);
    }
  }

  // Initial renders
  renderKPIs(stats);
  renderLineChart(stats.last_7_days);
  renderBarChart(stats.monthly_stats, currentMonthlyMode);
  if (stats.today_attendance && stats.today_attendance.length > 0) {
    renderTodayTable(stats.today_attendance);
  }
  if (stats.department_summary && stats.department_summary.length > 0) {
    renderDeptSummary(stats.department_summary);
  }

  // Interactive Filter Listeners
  const filterTrendRange = document.getElementById('filterTrendRange');
  if (filterTrendRange) {
    filterTrendRange.addEventListener('change', function () {
      currentTrendDays = parseInt(this.value, 10) || 7;
      renderLineChart(stats.last_7_days);
    });
  }

  const filterMonthlyRange = document.getElementById('filterMonthlyRange');
  if (filterMonthlyRange) {
    filterMonthlyRange.addEventListener('change', function () {
      currentMonthlyMode = this.value;
      renderBarChart(stats.monthly_stats, currentMonthlyMode);
    });
  }

  // Live Auto Polling every 25 seconds
  setInterval(fetchDynamicStats, 25000);

  // Immediate refresh when tab becomes visible
  document.addEventListener('visibilitychange', function () {
    if (!document.hidden) {
      fetchDynamicStats();
    }
  });
});
