/**
 * Universal Dynamic Table Column Sorter (No Hardcoding)
 * Enables clickable sorting on ANY <th> with a .sort-icon or ⇅ in ANY table across all tabs.
 * Dynamically handles Numbers, Currency, Dates, Timestamps, Durations, and Strings.
 */

(function () {
  'use strict';

  // Parse cell value dynamically based on its content
  function parseCellValue(cell) {
    if (!cell) return { type: 'empty', val: '' };

    // 1. Check for inputs / checkboxes
    const checkbox = cell.querySelector('input[type="checkbox"]');
    if (checkbox) {
      return { type: 'boolean', val: checkbox.checked ? 1 : 0 };
    }

    // 2. Check for image
    const img = cell.querySelector('img');
    if (img) {
      const src = img.getAttribute('src') || '';
      const isDefault = src.includes('default-avatar') || src.includes('placeholder') || src === '';
      return { type: 'image', val: isDefault ? '0' : '1_' + src };
    }

    // 3. Extract text content
    let raw = cell.textContent || '';
    raw = raw.replace(/\s+/g, ' ').trim();

    if (!raw || raw === '-' || raw === '----' || raw.toLowerCase() === 'n/a' || raw.toLowerCase() === 'none') {
      return { type: 'empty', val: null };
    }

    // 4. Check for Full DateTime with AM/PM or 24h:
    // e.g. "04/11/2026 11:21:56 AM", "04-11-2026 11:21:56 AM", "2026-11-04 11:21:56"
    const dtMatch = raw.match(/^(\d{1,4})[\/\-](\d{1,2})[\/\-](\d{1,4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*(AM|PM))?)?$/i);
    if (dtMatch) {
      let p1 = parseInt(dtMatch[1], 10);
      let p2 = parseInt(dtMatch[2], 10);
      let p3 = parseInt(dtMatch[3], 10);
      let year, month, day;

      if (p1 > 1000) {
        // YYYY-MM-DD
        year = p1;
        month = p2 - 1;
        day = p3;
      } else {
        // DD-MM-YYYY or DD/MM/YYYY
        day = p1;
        month = p2 - 1;
        year = p3;
        if (year < 100) year += 2000;
      }

      let h = dtMatch[4] ? parseInt(dtMatch[4], 10) : 0;
      let m = dtMatch[5] ? parseInt(dtMatch[5], 10) : 0;
      let s = dtMatch[6] ? parseInt(dtMatch[6], 10) : 0;
      let ampm = dtMatch[7] ? dtMatch[7].toUpperCase() : null;

      if (ampm === 'PM' && h < 12) h += 12;
      if (ampm === 'AM' && h === 12) h = 0;

      const dateObj = new Date(year, month, day, h, m, s);
      if (!isNaN(dateObj.getTime())) {
        return { type: 'date', val: dateObj.getTime() };
      }
    }

    // 5. Check for Time only: e.g. "11:21:56 AM", "09:30 AM", "18:45"
    const timeMatch = raw.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*(AM|PM))?$/i);
    if (timeMatch) {
      let h = parseInt(timeMatch[1], 10);
      let m = parseInt(timeMatch[2], 10);
      let s = timeMatch[3] ? parseInt(timeMatch[3], 10) : 0;
      let ampm = timeMatch[4] ? timeMatch[4].toUpperCase() : null;

      if (ampm === 'PM' && h < 12) h += 12;
      if (ampm === 'AM' && h === 12) h = 0;

      return { type: 'time', val: h * 3600 + m * 60 + s };
    }

    // 6. Check for Duration / Hours: e.g. "08:00", "02:30", "8.5 hrs", "8h"
    const durMatch = raw.match(/^(\d+):(\d{2})$/);
    if (durMatch) {
      return { type: 'duration', val: parseInt(durMatch[1], 10) * 60 + parseInt(durMatch[2], 10) };
    }

    // 7. Check for Currency / Numbers / Distance / Percentages
    // e.g. "₹ 1,500.00", "$250.50", "1,200", "500", "12.5 km", "250 m", "85%"
    const cleanNum = raw.replace(/[₹$€£\s%km\+]/gi, '').replace(/rs\.?/gi, '').replace(/,/g, '').replace(/[^\d.-]/g, '');
    if (cleanNum !== '' && !isNaN(cleanNum)) {
      const numVal = parseFloat(cleanNum);
      if (!isNaN(numVal)) {
        return { type: 'number', val: numVal };
      }
    }

    // 8. String fallback
    return { type: 'string', val: raw.toLowerCase() };
  }

  // Compare two parsed values
  function compareValues(a, b, isAsc) {
    // Keep empty / null values at the bottom regardless of sort order
    if (a.val === null && b.val === null) return 0;
    if (a.val === null) return 1;
    if (b.val === null) return -1;

    let res = 0;
    if (a.type === 'number' && b.type === 'number') {
      res = a.val - b.val;
    } else if ((a.type === 'date' || a.type === 'time' || a.type === 'duration') &&
               (b.type === 'date' || b.type === 'time' || b.type === 'duration')) {
      res = a.val - b.val;
    } else {
      const strA = String(a.val);
      const strB = String(b.val);
      res = strA.localeCompare(strB, undefined, { numeric: true, sensitivity: 'base' });
    }

    return isAsc ? res : -res;
  }

  // Check if a table column is a serial number / row index column
  function isSerialNumberHeader(thText) {
    const clean = thText.replace(/[⇅▲▼\s]/g, '').toLowerCase();
    return clean === 'slno' || clean === 'sno' || clean === 's.no' || clean === '#' || clean === 'index';
  }

  // Perform sorting on a table
  function sortTable(table, clickedTh) {
    if (!table || !clickedTh) return;

    const thead = table.querySelector('thead');
    const tbody = table.querySelector('tbody');
    if (!thead || !tbody) return;

    // Get all header cells in the row containing the clicked th
    const headerRow = clickedTh.closest('tr');
    if (!headerRow) return;

    const thCells = Array.from(headerRow.children);
    const colIndex = thCells.indexOf(clickedTh);
    if (colIndex === -1) return;

    // Determine new direction
    const currentDir = clickedTh.getAttribute('data-sort-dir');
    const newDir = currentDir === 'asc' ? 'desc' : 'asc';

    // Update icons in this table header row
    thCells.forEach(th => {
      const icon = th.querySelector('.sort-icon') || (th.textContent.includes('⇅') || th.textContent.includes('▲') || th.textContent.includes('▼') ? th.querySelector('.sort-icon') : null);
      if (th === clickedTh) {
        th.setAttribute('data-sort-dir', newDir);
        if (icon) icon.textContent = newDir === 'asc' ? '▲' : '▼';
      } else {
        th.removeAttribute('data-sort-dir');
        if (icon) icon.textContent = '⇅';
      }
    });

    // Get all rows in tbody excluding empty messages or colspan rows
    const rows = Array.from(tbody.querySelectorAll('tr')).filter(tr => {
      if (tr.classList.contains('table-empty-message') || tr.querySelector('.table-empty-message')) return false;
      const firstTd = tr.querySelector('td');
      if (firstTd && firstTd.hasAttribute('colspan')) return false;
      return true;
    });

    if (rows.length <= 1) return;

    // Map rows with parsed values
    const parsedRows = rows.map((row, index) => {
      const cell = row.children[colIndex];
      return {
        row: row,
        parsed: parseCellValue(cell),
        origIndex: index
      };
    });

    // Stable sort
    parsedRows.sort((a, b) => {
      const cmp = compareValues(a.parsed, b.parsed, newDir === 'asc');
      return cmp !== 0 ? cmp : a.origIndex - b.origIndex;
    });

    // Re-append rows to tbody in sorted order
    parsedRows.forEach(item => tbody.appendChild(item.row));

    // If there is a serial number / SL NO column, re-index sequential numbers
    thCells.forEach((th, cIdx) => {
      if (isSerialNumberHeader(th.textContent || '')) {
        let count = 1;
        tbody.querySelectorAll('tr').forEach(tr => {
          const cell = tr.children[cIdx];
          if (cell && !tr.querySelector('.table-empty-message')) {
            cell.textContent = String(count++);
          }
        });
      }
    });
  }

  // Global event delegation for clicks on sortable table headers
  document.addEventListener('click', function (e) {
    const th = e.target.closest('th');
    if (!th) return;

    // Determine if this th has a sort indicator
    const hasSortIcon = Boolean(th.querySelector('.sort-icon'));
    const hasSortText = th.textContent && (th.textContent.includes('⇅') || th.textContent.includes('▲') || th.textContent.includes('▼'));
    const hasDataCol = th.hasAttribute('data-col');

    if (!hasSortIcon && !hasSortText && !hasDataCol) {
      return;
    }

    const table = th.closest('table');
    if (!table) return;

    // Execute sorting
    sortTable(table, th);
  }, false);

  // Expose global sort helper if modules wish to trigger programmatically
  window.UniversalTableSorter = {
    sort: sortTable,
    parseCellValue: parseCellValue
  };

})();
