import 'dart:async';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:camera/camera.dart';
import 'package:geolocator/geolocator.dart';
import 'package:intl/intl.dart';
import '../constants/app_theme.dart';
import '../services/api_service.dart';
import 'field_worker_portal_screen.dart';
import 'employee_portal_screen.dart';

class AttendanceTerminalScreen extends StatefulWidget {
  const AttendanceTerminalScreen({super.key});

  @override
  State<AttendanceTerminalScreen> createState() => _AttendanceTerminalScreenState();
}

class _AttendanceTerminalScreenState extends State<AttendanceTerminalScreen> with WidgetsBindingObserver {
  CameraController? _cameraController;
  List<CameraDescription> _cameras = [];
  bool _isCameraInitialized = false;
  bool _isProcessingPunch = false;
  String _timeString = '';
  String _dateString = '';
  Timer? _clockTimer;
  Position? _currentPosition;
  String _locationStatus = 'Locating GPS...';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _updateClock();
    _clockTimer = Timer.periodic(const Duration(seconds: 1), (_) => _updateClock());
    _initCamera();
    _fetchLocation();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _clockTimer?.cancel();
    _cameraController?.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (_cameraController == null || !_cameraController!.value.isInitialized) return;
    if (state == AppLifecycleState.inactive) {
      _cameraController?.dispose();
    } else if (state == AppLifecycleState.resumed) {
      _initCamera();
    }
  }

  void _updateClock() {
    final now = DateTime.now();
    setState(() {
      _timeString = DateFormat('hh:mm:ss a').format(now);
      _dateString = DateFormat('EEEE, dd MMMM yyyy').format(now);
    });
  }

  Future<void> _fetchLocation() async {
    try {
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.whileInUse || perm == LocationPermission.always) {
        final pos = await Geolocator.getCurrentPosition(
          locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
        );
        if (mounted) {
          setState(() {
            _currentPosition = pos;
            _locationStatus = 'GPS Active: ${pos.latitude.toStringAsFixed(4)}, ${pos.longitude.toStringAsFixed(4)}';
          });
        }
      } else {
        if (mounted) {
          setState(() => _locationStatus = 'GPS Permission Denied');
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _locationStatus = 'GPS Unavailable');
      }
    }
  }

  Future<void> _initCamera() async {
    try {
      _cameras = await availableCameras();
      if (_cameras.isEmpty) return;

      // Prefer front-facing camera for kiosk attendance terminal
      CameraDescription selectedCamera = _cameras.first;
      for (var c in _cameras) {
        if (c.lensDirection == CameraLensDirection.front) {
          selectedCamera = c;
          break;
        }
      }

      _cameraController = CameraController(
        selectedCamera,
        ResolutionPreset.medium,
        enableAudio: false,
      );

      await _cameraController!.initialize();
      if (mounted) {
        setState(() => _isCameraInitialized = true);
      }
    } catch (e) {
      debugPrint('Camera initialization error: $e');
    }
  }

  Future<void> _captureAndPunchFace() async {
    if (_isProcessingPunch) return;
    if (_cameraController == null || !_cameraController!.value.isInitialized) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Camera initializing. Please wait a moment...')),
      );
      return;
    }

    setState(() {
      _isProcessingPunch = true;
    });

    try {
      final XFile photo = await _cameraController!.takePicture();
      final photoFile = File(photo.path);

      final result = await ApiService.recognizeFace(
        photoFile,
        latitude: _currentPosition?.latitude,
        longitude: _currentPosition?.longitude,
      );

      if (mounted) {
        setState(() {
          _isProcessingPunch = false;
        });

        if (result['matched'] == true) {
          _showPunchSuccessDialog(result);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              backgroundColor: AppTheme.dangerRed,
              content: Text(result['message'] ?? 'Face not recognized. Please center your face and try again.'),
            ),
          );
        }
      }
    } catch (e) {
      if (mounted) {
        setState(() => _isProcessingPunch = false);
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            backgroundColor: AppTheme.dangerRed,
            content: Text('Punch processing error: $e'),
          ),
        );
      }
    }
  }

  void _showPunchSuccessDialog(Map<String, dynamic> data) {
    final name = data['employee_name'] ?? 'Verified Employee';
    final code = data['employee_code'] ?? data['employee_id'] ?? 'EMP-VERIFIED';
    final dept = data['department'] ?? 'Operations';
    final status = data['punch_status'] == 'punch_out' ? 'Punch Out Recorded' : 'Punch In Recorded';
    final isOut = data['punch_status'] == 'punch_out';

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return Container(
          decoration: const BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 68,
                height: 68,
                decoration: BoxDecoration(
                  color: isOut ? const Color(0xFFF59E0B).withValues(alpha: 0.15) : const Color(0xFF10B981).withValues(alpha: 0.15),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  isOut ? Icons.logout_rounded : Icons.check_circle_rounded,
                  color: isOut ? const Color(0xFFD97706) : const Color(0xFF059669),
                  size: 40,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                status,
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                  color: isOut ? const Color(0xFFD97706) : const Color(0xFF059669),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                name,
                style: const TextStyle(
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  color: AppTheme.textDark,
                ),
              ),
              Text(
                '$code • $dept',
                style: const TextStyle(fontSize: 13, color: AppTheme.textMuted),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                decoration: BoxDecoration(
                  color: AppTheme.surfaceLight,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.borderSubtle),
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceAround,
                  children: [
                    Column(
                      children: [
                        const Text('Time (IST)', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                        Text(_timeString, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700)),
                      ],
                    ),
                    Column(
                      children: [
                        const Text('GPS Verification', style: TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                        const Text('Site Verified ✔', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF15803D))),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () => Navigator.pop(ctx),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryNavy,
                    padding: const EdgeInsets.symmetric(vertical: 14),
                  ),
                  child: const Text('OK / Done', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700)),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showPinPunchDialog() {
    final codeCtrl = TextEditingController();
    final pinCtrl = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: Row(
            children: const [
              Icon(Icons.pin_rounded, color: AppTheme.primaryNavy),
              SizedBox(width: 8),
              Text('Manual PIN Punch', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: codeCtrl,
                decoration: const InputDecoration(
                  labelText: 'Employee Code / ID',
                  hintText: 'e.g. EMP-001',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.badge_outlined),
                ),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: pinCtrl,
                obscureText: true,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Attendance PIN',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.lock_outline),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Verifying PIN credential...')),
                );
                final res = await ApiService.punchWithPin(
                  employeeCode: codeCtrl.text,
                  pin: pinCtrl.text,
                  latitude: _currentPosition?.latitude,
                  longitude: _currentPosition?.longitude,
                );
                if (mounted) {
                  if (res['success'] == true) {
                    _showPunchSuccessDialog(res);
                  } else {
                    ScaffoldMessenger.of(context).showSnackBar(
                      SnackBar(
                        backgroundColor: AppTheme.dangerRed,
                        content: Text(res['error'] ?? 'Invalid Employee Code or PIN'),
                      ),
                    );
                  }
                }
              },
              child: const Text('Punch In / Out'),
            ),
          ],
        );
      },
    );
  }

  void _openServerConfigDialog() {
    final messenger = ScaffoldMessenger.of(context);
    final ctrl = TextEditingController();
    ApiService.getBaseUrl().then((val) => ctrl.text = val);

    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Server Configuration', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'Enter backend Flask API server URL (e.g. http://192.168.1.50:5000 or https://attendance.argus.com):',
                style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: ctrl,
                decoration: const InputDecoration(
                  labelText: 'API Base URL',
                  border: OutlineInputBorder(),
                  prefixIcon: Icon(Icons.dns_rounded),
                ),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: () async {
                await ApiService.setBaseUrl(ctrl.text);
                if (ctx.mounted) {
                  Navigator.pop(ctx);
                }
                if (mounted) {
                  messenger.showSnackBar(
                    const SnackBar(content: Text('Server URL updated successfully!')),
                  );
                }
              },
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Row(
          children: [
            Image.asset(
              'assets/images/logo.png',
              height: 32,
              errorBuilder: (_, __, ___) => const Icon(Icons.security, color: Colors.white),
            ),
            const SizedBox(width: 10),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'ARGUS ATTENDANCE',
                  style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, letterSpacing: 0.8),
                ),
                Text(
                  _dateString,
                  style: TextStyle(fontSize: 10.5, color: Colors.white.withValues(alpha: 0.8)),
                ),
              ],
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined, size: 20),
            tooltip: 'Server Settings',
            onPressed: _openServerConfigDialog,
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Top Live Clock & GPS Status Bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: AppTheme.primaryNavy.withValues(alpha: 0.04),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      const Icon(Icons.schedule, size: 14, color: AppTheme.primaryElectricBlue),
                      const SizedBox(width: 5),
                      Text(
                        _timeString,
                        style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w800, color: AppTheme.primaryNavy),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      const Icon(Icons.location_on, size: 14, color: Color(0xFF10B981)),
                      const SizedBox(width: 4),
                      Text(
                        _locationStatus,
                        style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // Camera Viewfinder & Face Guide Oval
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Stack(
                  alignment: Alignment.center,
                  children: [
                    // Camera Preview
                    Container(
                      width: double.infinity,
                      decoration: BoxDecoration(
                        color: Colors.black,
                        borderRadius: BorderRadius.circular(20),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.12),
                            blurRadius: 10,
                            offset: const Offset(0, 4),
                          ),
                        ],
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: _isCameraInitialized && _cameraController != null
                          ? CameraPreview(_cameraController!)
                          : Center(
                              child: Column(
                                mainAxisSize: MainAxisSize.min,
                                children: const [
                                  CircularProgressIndicator(color: Colors.white),
                                  SizedBox(height: 12),
                                  Text(
                                    'Starting Camera Feed...',
                                    style: TextStyle(color: Colors.white, fontSize: 13),
                                  ),
                                ],
                              ),
                            ),
                    ),

                    // Face Framing Oval Overlay
                    IgnorePointer(
                      child: Container(
                        width: 230,
                        height: 310,
                        decoration: BoxDecoration(
                          shape: BoxShape.rectangle,
                          borderRadius: BorderRadius.circular(115),
                          border: Border.all(
                            color: _isProcessingPunch ? AppTheme.warningAmber : const Color(0xFF38BDF8),
                            width: 3.5,
                          ),
                          boxShadow: [
                            BoxShadow(
                              color: const Color(0xFF38BDF8).withValues(alpha: 0.2),
                              blurRadius: 20,
                              spreadRadius: 2,
                            ),
                          ],
                        ),
                        child: Align(
                          alignment: Alignment.topCenter,
                          child: Container(
                            margin: const EdgeInsets.only(top: 14),
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: Colors.black.withValues(alpha: 0.6),
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Text(
                              _isProcessingPunch ? 'Verifying Face...' : 'Align Face in Oval',
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                              ),
                            ),
                          ),
                        ),
                      ),
                    ),

                    if (_isProcessingPunch)
                      Container(
                        color: Colors.black.withValues(alpha: 0.55),
                        child: Center(
                          child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: const [
                              CircularProgressIndicator(color: Color(0xFF38BDF8)),
                              SizedBox(height: 14),
                              Text(
                                'Matching Biometric Face Vector...',
                                style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w700),
                              ),
                            ],
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),

            // Punch Attendance Buttons
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16.0),
              child: Column(
                children: [
                  SizedBox(
                    width: double.infinity,
                    height: 52,
                    child: ElevatedButton.icon(
                      onPressed: _isProcessingPunch ? null : _captureAndPunchFace,
                      icon: const Icon(Icons.camera_alt_rounded, size: 22),
                      label: Text(
                        _isProcessingPunch ? 'PROCESSING PUNCH...' : 'MARK ATTENDANCE (FACE)',
                        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800, letterSpacing: 0.5),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryNavy,
                        elevation: 3,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  TextButton.icon(
                    onPressed: _showPinPunchDialog,
                    icon: const Icon(Icons.dialpad_rounded, size: 16, color: AppTheme.textMuted),
                    label: const Text(
                      'Manual Employee Code & PIN Fallback',
                      style: TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600, color: AppTheme.textMuted),
                    ),
                  ),
                ],
              ),
            ),

            const SizedBox(height: 8),

            // Portal Navigation Bar (Field Worker Portal & Employee Portal Buttons)
            Container(
              padding: const EdgeInsets.all(12),
              margin: const EdgeInsets.fromLTRB(16, 4, 16, 12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(14),
                border: Border.all(color: AppTheme.borderSubtle),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 6,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const FieldWorkerPortalScreen()),
                        );
                      },
                      icon: const Icon(Icons.two_wheeler_rounded, size: 18, color: AppTheme.primaryNavy),
                      label: const Text(
                        'Field Worker Portal',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppTheme.primaryNavy),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: AppTheme.primaryNavy, width: 1.2),
                        padding: const EdgeInsets.symmetric(vertical: 11),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: OutlinedButton.icon(
                      onPressed: () {
                        Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const EmployeePortalScreen()),
                        );
                      },
                      icon: const Icon(Icons.badge_rounded, size: 18, color: AppTheme.primaryElectricBlue),
                      label: const Text(
                        'Employee Portal',
                        style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: AppTheme.primaryElectricBlue),
                      ),
                      style: OutlinedButton.styleFrom(
                        side: const BorderSide(color: AppTheme.primaryElectricBlue, width: 1.2),
                        padding: const EdgeInsets.symmetric(vertical: 11),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
