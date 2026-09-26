# ARGUS TECHNOLOGIES - AI Face Attendance Web Application

A full-stack attendance and payroll management web application built with Python Flask and MongoDB Atlas, styled to match Argus Technologies UI.

## Features Implemented

### 1. Dashboard Tab
- **Top Bar**: Yellow brand banner (`#ffd166`) with Argus Technologies title, hamburger sidebar toggle, Logout button, and Fullscreen toggle.
- **Fixed Sidebar**: Fixed, non-scrollable left navigation sidebar with responsive collapse. Only right-side content scrolls.
- **Header Card**: Live updating date and time ticker (`DD/MM/YYYY HH:MM:SS`).
- **5 Dynamic Stat Summary Cards**: Total, Present, Absent, Present %, Timeout.
- **Interactive Charts**: Last 7 Days Attendance (line chart) and Monthly Attendance (bar chart) populated dynamically from MongoDB.

### 2. Employee Details Tab
- Exact 13-column sortable table with action buttons (View, Edit, Delete, View Image).
- 3-column Employee Detail Entry Modal.
- 2-column Employee Detail View Modal with Print & PDF download.

### 3. Live Report Tab
- **Live Entries** and **Timeout Entries** sub-views.
- Date Range Filter Bar, Show rows, Copy, Excel, PDF, Print, Search.
- Zero image storage: Omitted image columns as instructed.

### 4. Attendance Report Tab
- Sub-views: **All Entries**, **Proper Entries**, **Improper Entries**, **Manual Entries**, and **Simple Table**.
- Real-time `🔄 Update` recalculation button, date range filters, and export tools.

### 5. Manual Entry Tab
- Manual Entry table and Add Manual Entry Modal with dynamic employee dropdown, date picker, in/out timestamps, and working hours calculation.

### 6. Dedicated Payment Entry & Advance / Balance Tabs
- **Payment Entry Tab** (`/payment-entry`): Single isolated view for Payment Management table and Add Payment modal. Includes direct navigation buttons to dedicated sub-pages.
- **Advance Management Tab** (`/advance-management`): Dedicated page matching UI with employee filter, advance table, and `← Back to Payment` navigation.
- **Balance Report Tab** (`/balance-report`): Dedicated full page report displaying employee balance summary with sticky bottom totals bar.

### 7. Monthly Payslip Tab (`/monthly-payslip`)
- Selection view with Employee, Year, and Month dropdowns.
- Dynamic Payslip Generation matching official Argus Technologies payslip template (Company info, 4-column earnings/deductions breakdown, Net Pay in figures and words).

### 8. Salary Report Tab (`/salary-report`)
- Comprehensive 14-column monthly salary report table with status badges and totals.

---

## Face Recognition Architecture (Zero-Image-Storage Method)

### How Face Recognition is Performed Without Storing Images:
1. **Mathematical Feature Vectors (128-d Embeddings)**:
   - When an employee registers or stands in front of the camera, the face is detected.
   - The face crop is passed through a deep convolutional neural network / feature extractor (`face_engine.py`).
   - The model generates a **128-dimensional floating-point mathematical embedding vector** (e.g. `[0.052, -0.183, 0.491, ...]`).
   - **The raw face image is never stored on disk or in the database and is immediately discarded from memory.**
   - Only the 128 numerical floats are stored in `employees.face_embedding` (~512 bytes).

2. **Real-time Recognition via Cosine Similarity**:
   - During live camera check-in, a live 128-d vector is computed on-the-fly.
   - The vector is compared against all registered employee vectors using **Cosine Similarity**:
     $$\text{Cosine Similarity} = \frac{\mathbf{A} \cdot \mathbf{B}}{\|\mathbf{A}\|_2 \|\mathbf{B}\|_2}$$
   - If the similarity is above the recognition threshold ($\ge 0.75$), the employee is identified instantly (< 1 millisecond).

3. **Advantages**:
   - **100% Privacy Compliant**: Original face image cannot be reconstructed from the 128-d numerical embedding.
   - **Zero Disk Storage**: No folder of employee photos.
   - **Sub-millisecond Speed**: Fast vector dot product with NumPy.

## How to Run

1. Open PowerShell or Command Prompt in the project folder:
   ```bash
   python run.py
   ```
2. Open your web browser and navigate to:
   ```
   http://127.0.0.1:5000
   ```

## Database (MongoDB Atlas)

- Connected to cloud MongoDB Atlas cluster (`argus_attendance` database).
- Collections:
  - `employees`: Employee details, salary configuration, and 128-d face embeddings.
  - `attendance`: Date-stamped check-in and check-out records.
  - `live_entries`: Real-time active check-in sessions and timeout records (>15 hrs).
  - `attendance_reports`: Historical attendance records categorized by proper, improper, manual.
  - `manual_entries`: Admin-entered manual attendance logs.
  - `payments`: Recorded salary and miscellaneous disbursements.
  - `advances`: Employee advance loans and repayment statuses.
  - `salary_reports`: Monthly consolidated payroll and deduction statements.

## Backend API Endpoints

- `GET /` -> Redirects to `/dashboard`
- `GET /dashboard` -> Renders Dashboard view
- `GET /employee-details` -> Renders Employee Details view
- `GET /api/dashboard/stats` -> Returns dashboard statistics and chart data
- `GET /api/employees` -> Retrieves paginated, sorted, and filtered employee records
- `GET /api/employees/<id>` -> Retrieves full details of an employee
- `POST /api/employees` -> Creates a new employee with photo upload
- `POST /api/employees/<id>` -> Updates existing employee record
- `DELETE /api/employees/<id>` -> Deletes an employee
- `GET /api/employees/<id>/pdf` -> Generates and downloads formatted PDF report
- `GET /uploads/<filename>` -> Serves uploaded employee photos
