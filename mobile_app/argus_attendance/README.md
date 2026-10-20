# Argus Attendance — Mobile Application

Production-grade cross-platform mobile application for **Argus Attendance**, publishable to the **Google Play Store**.

Built with **Flutter (Dart)**, connecting seamlessly to the existing Flask/MongoDB backend APIs with **100% Zero-Disturbance** to the existing web application.

---

## 🚀 Key Features

1. **Attendance Punch Terminal (Primary / First Screen)**:
   - Live camera viewfinder with animated facial alignment oval.
   - One-tap facial recognition attendance punch via `/api/face/recognize`.
   - Real-time GPS geofence verification stamp.
   - Manual Employee Code & PIN fallback modal.
   - Real-time IST digital clock and date display.
   - Zero administrative controls on the mobile app.

2. **Field Worker Portal**:
   - Shift toggle: Starts/stops continuous background GPS route telemetry to `/api/field-worker/location-ping`.
   - Today's assigned customer visits list with site navigation.
   - **Tamil AI Conversation Audio Tracker**:
     - Records client discussions directly via device hardware microphone.
     - Live duration counter and pause/resume controls.
     - Automatically compresses audio to `.m4a` and uploads to backend upon visit completion.
     - Backend **Google Gemini 1.5 Flash Multimodal Audio AI** performs verbatim Indian Tamil (`ta-IN`) transcription, English translation, client sentiment classification, and order value extraction.

3. **Employee Portal**:
   - Monthly working days and paid leave balance overview.
   - Apply for Leave (Casual Leave, Sick Leave, Earned Leave) with Full/Half Day sessions.
   - Apply for Permission (Short Leave / 1-2 hours).
   - Monthly payslip status and download.

4. **Zero-Disturbance Web App Guarantee**:
   - The Flask web application, web kiosk terminal, admin dashboard, and field worker web module continue running 24/7 without modification or interruption.
   - Mobile endpoints are purely additive.

---

## 📦 Tech Stack & Packages

- **Framework**: Flutter 3.x (Dart 3.x)
- **Camera & Biometrics**: `camera: ^0.11.0+2`
- **GPS & Geofencing**: `geolocator: ^13.0.2`
- **Audio Recording**: `record: ^5.2.0` (AAC-LC @ 64kbps, 44.1kHz)
- **Audio Playback**: `audioplayers: ^6.1.0`
- **Networking**: `http: ^1.2.0`
- **Storage & State**: `shared_preferences: ^2.3.2`, `path_provider: ^2.1.5`
- **Permissions**: `permission_handler: ^11.3.1`
- **AI Speech-to-Text**: Google Gemini 1.5 Flash (`ta-IN` Indian Tamil)

---

## 🛠️ How to Run & Build

### 1. Run in Debug Mode (Emulator or USB Connected Device)
```bash
cd mobile_app/argus_attendance
flutter pub get
flutter run
```

*Note: In the app, tap the top-right Settings icon to configure the API server URL (e.g. `http://10.0.2.2:5000` for Android emulator or your LAN IP like `http://192.168.1.100:5000` for physical devices).*

### 2. Build Release APK (For Direct Installation)
```bash
flutter build apk --release
```
The output APK is generated at:
`build/app/outputs/flutter-apk/app-release.apk`

### 3. Build Android App Bundle (.aab) for Google Play Store
```bash
flutter build appbundle --release
```
The output AAB is generated at:
`build/app/outputs/bundle/release/app-release.aab`

---

## 📋 Google Play Store Publishing Checklist

- [x] **Application ID**: `com.argustechnologies.argus_attendance`
- [x] **Target SDK**: Android 14 (API 34)
- [x] **Min SDK**: Android 5.0 (API 21)
- [x] **Foreground Service Permissions**: Declared with `FOREGROUND_SERVICE_LOCATION` and `FOREGROUND_SERVICE_MICROPHONE` in `AndroidManifest.xml`.
- [x] **Prominent Disclosures**: In-app bilingual (English & தமிழ்) dialog before microphone recording begins.
- [x] **App Assets**: Argus official logos in `assets/images/`.
