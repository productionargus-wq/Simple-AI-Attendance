# Documentation & Proposals Directory

This directory contains client proposals, technical dossiers, hosting comparisons, and operational guidelines for the **ARGUS TECHNOLOGIES Simple AI Attendance & Operations Management System**.

---

## 📁 Document Catalog

### 1. Client Proposals & Product Modules
- **`AI_Field_Worker_Tracking_Proposal.pdf`**
  Comprehensive proposal for AI-powered remote field worker tracking, geolocation verification, mobile kiosk attendance, and route/visit monitoring.
- **`Field_Worker_Module_Client_Proposal.pdf`**
  Client presentation detailing the dedicated Field Worker Module, offline sync capability, task verification, and wage calculation workflows.

### 2. Technical Architecture & Credentials Dossiers
- **`ARGUS_Attendance_Technical_Architecture_and_Credentials_Dossier.pdf`** *(Source: `.docx`)*
  In-depth architectural breakdown detailing the Zero-Image-Storage 128-d face recognition pipeline, MongoDB Atlas schema, microservices, and system security.
- **`ARGUS_Attendance_Services_and_Credentials_Directory.pdf`** *(Source: `.docx`)*
  Internal operations directory documenting third-party services, API integrations, and credential specifications.
- **`Technology_Stack_Simple_AI_Attendance.pdf`**
  Technical stack summary covering Python Flask, PyWebView, MongoDB Atlas, Mediapipe/OpenCV DNN, and Capacitor native runtimes.

### 3. Infrastructure & Cloud Hosting
- **`Cloud_Hosting_Comparison_Render_vs_AWS.pdf`**
  Client-facing evaluation and cost-benefit analysis comparing Render cloud hosting against AWS infrastructure. Generated via `scripts/generate_client_cloud_comparison_pdf.py`.

### 4. Operational & Registration Guidelines
- **`Face_Registration_Guidelines.pdf`**
  Single-page operational guide for high-accuracy face enrollment (lighting conditions, distance, angle, facial expression, and anti-spoofing criteria).

---

> [!NOTE]
> To regenerate `Cloud_Hosting_Comparison_Render_vs_AWS.pdf`, run:
> ```bash
> python scripts/generate_client_cloud_comparison_pdf.py
> ```
