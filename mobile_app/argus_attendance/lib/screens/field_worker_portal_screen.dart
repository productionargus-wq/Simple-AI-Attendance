import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import '../constants/app_theme.dart';
import '../services/api_service.dart';
import '../services/audio_recorder_service.dart';

class FieldWorkerPortalScreen extends StatefulWidget {
  const FieldWorkerPortalScreen({super.key});

  @override
  State<FieldWorkerPortalScreen> createState() => _FieldWorkerPortalScreenState();
}

class _FieldWorkerPortalScreenState extends State<FieldWorkerPortalScreen> {
  final AudioRecorderService _audioRecorder = AudioRecorderService();
  bool _isShiftActive = false;
  Timer? _gpsPingTimer;
  Position? _currentPosition;
  String _workerName = 'Field Worker';

  // Audio Recording State
  bool _isRecordingVisit = false;
  bool _isPaused = false;
  int _recordSeconds = 0;
  StreamSubscription<int>? _durationSub;

  // Recent Visits
  List<dynamic> _visits = [];
  bool _isLoadingVisits = false;
  List<Map<String, dynamic>> _warehouseProducts = [];

  @override
  void initState() {
    super.initState();
    _loadWorkerSession();
    _fetchVisits();
    _fetchWarehouseProducts();
    _durationSub = _audioRecorder.durationStream.listen((sec) {
      if (mounted) setState(() => _recordSeconds = sec);
    });
  }

  @override
  void dispose() {
    _gpsPingTimer?.cancel();
    _durationSub?.cancel();
    _audioRecorder.dispose();
    super.dispose();
  }

  Future<void> _loadWorkerSession() async {
    final name = await ApiService.getActiveEmployeeName();
    if (mounted) {
      setState(() {
        if (name != null && name.isNotEmpty) _workerName = name;
      });
    }
  }

  Future<void> _fetchVisits() async {
    setState(() => _isLoadingVisits = true);
    final list = await ApiService.fetchCustomerVisits(employeeName: _workerName);
    if (mounted) {
      setState(() {
        _visits = list;
        _isLoadingVisits = false;
      });
    }
  }

  Future<void> _fetchWarehouseProducts() async {
    final prods = await ApiService.fetchWarehouseProducts();
    if (mounted) {
      setState(() => _warehouseProducts = prods);
    }
  }

  void _toggleShift(bool val) async {
    setState(() => _isShiftActive = val);
    if (val) {
      _startGpsTracking();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          backgroundColor: AppTheme.successGreen,
          content: Text('Field shift started! Continuous GPS route telemetry active.'),
        ),
      );
    } else {
      _gpsPingTimer?.cancel();
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Field shift ended.')),
      );
    }
  }

  void _startGpsTracking() async {
    _gpsPingTimer?.cancel();
    // Send ping immediately then every 3 minutes
    _sendSingleLocationPing();
    _gpsPingTimer = Timer.periodic(const Duration(minutes: 3), (_) {
      _sendSingleLocationPing();
    });
  }

  Future<void> _sendSingleLocationPing() async {
    try {
      final pos = await Geolocator.getCurrentPosition(
        locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
      );
      _currentPosition = pos;
      await ApiService.sendLocationPing(
        employeeName: _workerName,
        latitude: pos.latitude,
        longitude: pos.longitude,
        activityNote: _isRecordingVisit ? 'Active Client Meeting' : 'On Field Route',
      );
    } catch (_) {}
  }

  Future<void> _startClientVisitRecording() async {
    // Show Google Play compliant prominent disclosure modal before audio recording
    final bool? proceed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: const [
            Icon(Icons.mic, color: AppTheme.primaryNavy),
            SizedBox(width: 8),
            Text('Record Client Discussion', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: const [
            Text(
              'Argus Attendance will record audio of this customer visit to generate verbatim Tamil & English transcripts, extract order values, and verify meeting notes for company records.',
              style: TextStyle(fontSize: 12.5, height: 1.4),
            ),
            SizedBox(height: 10),
            Text(
              'வாடிக்கையாளர் சந்திப்பின் போது மட்டுமே ஆடியோ பதிவு செய்யப்படும். சந்திப்பு முடிந்ததும் பதிவு தானாக நின்றுவிடும்.',
              style: TextStyle(fontSize: 12, color: Color(0xFF1E3A8A), fontWeight: FontWeight.w600, height: 1.4),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryNavy),
            child: const Text('Start Recording (தொடங்கு)'),
          ),
        ],
      ),
    );

    if (proceed != true) return;

    final success = await _audioRecorder.startRecording();
    if (success) {
      setState(() {
        _isRecordingVisit = true;
        _isPaused = false;
        _recordSeconds = 0;
      });
      // Ping server that visit recording started
      _sendSingleLocationPing();
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            backgroundColor: AppTheme.dangerRed,
            content: Text('Microphone permission required to record customer discussion.'),
          ),
        );
      }
    }
  }

  Future<void> _pauseResumeRecording() async {
    if (_isPaused) {
      await _audioRecorder.resumeRecording();
      setState(() => _isPaused = false);
    } else {
      await _audioRecorder.pauseRecording();
      setState(() => _isPaused = true);
    }
  }

  Future<void> _completeVisitAndUpload() async {
    final result = await _audioRecorder.stopRecording();
    setState(() {
      _isRecordingVisit = false;
      _isPaused = false;
    });

    if (result == null) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('No audio file captured.')),
        );
      }
      return;
    }

    // Open Visit Completion Details Dialog
    _showVisitFormDialog(result);
  }

  void _showVisitFormDialog(AudioRecordResult audioResult) {
    final messenger = ScaffoldMessenger.of(context);
    final custCtrl = TextEditingController();
    final personCtrl = TextEditingController();
    final phoneCtrl = TextEditingController();
    final productCtrl = TextEditingController(text: 'Argus AI Kiosk System');
    final amountCtrl = TextEditingController(text: '0');
    String leadStatus = 'Interested';

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: Row(
                children: const [
                  Icon(Icons.assignment_turned_in_rounded, color: AppTheme.primaryNavy),
                  SizedBox(width: 8),
                  Text('Complete Client Visit', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
                ],
              ),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                      decoration: BoxDecoration(
                        color: const Color(0xFFEFF6FF),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle, size: 16, color: Color(0xFF2563EB)),
                          const SizedBox(width: 6),
                          Text(
                            'Audio Recorded: ${audioResult.durationSeconds}s (Tamil AI ready)',
                            style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w700, color: Color(0xFF1E40AF)),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: custCtrl,
                      decoration: const InputDecoration(
                        labelText: 'Customer / Business Name *',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: personCtrl,
                            decoration: const InputDecoration(
                              labelText: 'Contact Person',
                              border: OutlineInputBorder(),
                              isDense: true,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: TextField(
                            controller: phoneCtrl,
                            keyboardType: TextInputType.phone,
                            decoration: const InputDecoration(
                              labelText: 'Phone',
                              border: OutlineInputBorder(),
                              isDense: true,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: productCtrl,
                      decoration: InputDecoration(
                        labelText: 'Product / Proposal Pitched',
                        border: const OutlineInputBorder(),
                        isDense: true,
                        suffixIcon: _warehouseProducts.isNotEmpty
                            ? PopupMenuButton<Map<String, dynamic>>(
                                icon: const Icon(Icons.arrow_drop_down_circle_outlined, color: AppTheme.primaryNavy, size: 20),
                                tooltip: 'Select from Product Warehouse',
                                onSelected: (prod) {
                                  setModalState(() {
                                    productCtrl.text = prod['name']?.toString() ?? '';
                                    final price = prod['price'];
                                    if (price != null && (price as num) > 0) {
                                      amountCtrl.text = price.toString();
                                    }
                                  });
                                },
                                itemBuilder: (context) {
                                  return _warehouseProducts.map((p) {
                                    final priceStr = p['price'] != null ? '₹${p['price']}' : '';
                                    return PopupMenuItem<Map<String, dynamic>>(
                                      value: p,
                                      child: Row(
                                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                        children: [
                                          Expanded(
                                            child: Text(
                                              p['name']?.toString() ?? '',
                                              style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w600),
                                              overflow: TextOverflow.ellipsis,
                                            ),
                                          ),
                                          const SizedBox(width: 8),
                                          Text(
                                            priceStr,
                                            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700, color: Color(0xFF15803D)),
                                          ),
                                        ],
                                      ),
                                    );
                                  }).toList();
                                },
                              )
                            : null,
                      ),
                    ),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      initialValue: leadStatus,
                      decoration: const InputDecoration(
                        labelText: 'Lead Outcome',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      items: const [
                        DropdownMenuItem(value: 'Order Confirmed', child: Text('Order Confirmed (Converted)')),
                        DropdownMenuItem(value: 'Interested', child: Text('Interested (Hot Lead)')),
                        DropdownMenuItem(value: 'Price Quoted', child: Text('Price Quoted / Follow-Up')),
                        DropdownMenuItem(value: 'Demo Given', child: Text('Demo Given')),
                        DropdownMenuItem(value: 'Not Interested', child: Text('Not Interested')),
                      ],
                      onChanged: (val) {
                        if (val != null) setModalState(() => leadStatus = val);
                      },
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: amountCtrl,
                      keyboardType: TextInputType.number,
                      decoration: const InputDecoration(
                        labelText: 'Estimated Deal Value (₹)',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(ctx),
                  child: const Text('Discard'),
                ),
                ElevatedButton(
                  onPressed: () async {
                    if (custCtrl.text.trim().isEmpty) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        const SnackBar(content: Text('Please enter customer / business name')),
                      );
                      return;
                    }
                    Navigator.pop(ctx);
                    messenger.showSnackBar(
                      const SnackBar(content: Text('Uploading visit & processing Tamil AI audio...')),
                    );

                    final pos = _currentPosition ??
                        await Geolocator.getCurrentPosition(
                          locationSettings: const LocationSettings(accuracy: LocationAccuracy.high),
                        );

                    final res = await ApiService.uploadCustomerVisitWithAudio(
                      visitData: {
                        'employee_name': _workerName,
                        'customer_name': custCtrl.text.trim(),
                        'contact_person': personCtrl.text.trim(),
                        'customer_phone': phoneCtrl.text.trim(),
                        'product_pitched': productCtrl.text.trim(),
                        'lead_status': leadStatus,
                        'order_amount': amountCtrl.text.trim(),
                        'latitude': pos.latitude.toString(),
                        'longitude': pos.longitude.toString(),
                      },
                      audioFilePath: audioResult.filePath,
                      durationSeconds: audioResult.durationSeconds.toDouble(),
                    );

                    if (mounted) {
                      if (res['success'] == true) {
                        messenger.showSnackBar(
                          SnackBar(
                            backgroundColor: AppTheme.successGreen,
                            content: Text(res['message'] ?? 'Visit recorded! Tamil AI transcript sent to Company Admin.'),
                          ),
                        );
                        _fetchVisits();
                      } else {
                        messenger.showSnackBar(
                          SnackBar(
                            backgroundColor: AppTheme.dangerRed,
                            content: Text(res['error'] ?? 'Failed to upload visit.'),
                          ),
                        );
                      }
                    }
                  },
                  style: ElevatedButton.styleFrom(backgroundColor: AppTheme.primaryNavy),
                  child: const Text('Save & Upload AI Audio'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  String _formatTimer(int sec) {
    final m = sec ~/ 60;
    final s = sec % 60;
    return '${m.toString().padLeft(2, '0')}:${s.toString().padLeft(2, '0')}';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('FIELD WORKER PORTAL'),
        backgroundColor: AppTheme.primaryNavy,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Worker Status & Shift Toggle Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Container(
                        width: 48,
                        height: 48,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryNavy.withValues(alpha: 0.1),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.two_wheeler_rounded, color: AppTheme.primaryNavy, size: 26),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _workerName,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textDark),
                            ),
                            Text(
                              _isShiftActive ? '🟢 On Active Field Duty (GPS Telemetry Live)' : '⚪ Shift Off-Duty',
                              style: TextStyle(
                                fontSize: 11.5,
                                fontWeight: FontWeight.w600,
                                color: _isShiftActive ? const Color(0xFF15803D) : AppTheme.textMuted,
                              ),
                            ),
                          ],
                        ),
                      ),
                      Switch(
                        value: _isShiftActive,
                        activeThumbColor: AppTheme.primaryNavy,
                        onChanged: _toggleShift,
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 14),

              // Active Client Visit & Tamil Speech-to-Text Recorder Box
              Card(
                color: _isRecordingVisit ? const Color(0xFFFEF2F2) : Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                  side: BorderSide(
                    color: _isRecordingVisit ? const Color(0xFFEF4444) : AppTheme.borderSubtle,
                    width: _isRecordingVisit ? 1.5 : 1.0,
                  ),
                ),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: const [
                              Icon(Icons.mic, color: AppTheme.primaryNavy, size: 20),
                              SizedBox(width: 6),
                              Text(
                                'AI Client Conversation Recorder',
                                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: AppTheme.primaryNavy),
                              ),
                            ],
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                            decoration: BoxDecoration(
                              color: const Color(0xFFDBEAFE),
                              borderRadius: BorderRadius.circular(6),
                            ),
                            child: const Text(
                              '🇮🇳 தமிழ் STT',
                              style: TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: Color(0xFF1E40AF)),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      const Text(
                        'Record audio when discussing orders with clients. Gemini AI automatically converts speech into verbatim Tamil script & English summary for admin auditing.',
                        style: TextStyle(fontSize: 11.5, color: AppTheme.textMuted, height: 1.4),
                      ),
                      const SizedBox(height: 14),

                      if (_isRecordingVisit) ...[
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(10),
                            border: Border.all(color: const Color(0xFFFCA5A5)),
                          ),
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: [
                              Row(
                                children: [
                                  Container(
                                    width: 12,
                                    height: 12,
                                    decoration: const BoxDecoration(
                                      color: Colors.red,
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  Text(
                                    _isPaused ? 'Recording Paused' : 'Recording in Progress...',
                                    style: TextStyle(
                                      fontSize: 12,
                                      fontWeight: FontWeight.w700,
                                      color: _isPaused ? AppTheme.warningAmber : Colors.red,
                                    ),
                                  ),
                                ],
                              ),
                              Text(
                                _formatTimer(_recordSeconds),
                                style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.black87),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed: _pauseResumeRecording,
                                icon: Icon(_isPaused ? Icons.play_arrow : Icons.pause, size: 18),
                                label: Text(_isPaused ? 'Resume' : 'Pause'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: ElevatedButton.icon(
                                onPressed: _completeVisitAndUpload,
                                icon: const Icon(Icons.stop, size: 18),
                                label: const Text('Finish Visit'),
                                style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFFDC2626)),
                              ),
                            ),
                          ],
                        ),
                      ] else ...[
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _startClientVisitRecording,
                            icon: const Icon(Icons.fiber_manual_record, color: Colors.redAccent, size: 18),
                            label: const Text(
                              'START VISIT & AI AUDIO (நேரடி சந்திப்பு)',
                              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, letterSpacing: 0.3),
                            ),
                            style: ElevatedButton.styleFrom(
                              backgroundColor: AppTheme.primaryNavy,
                              padding: const EdgeInsets.symmetric(vertical: 13),
                            ),
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 18),

              // Recent Logged Visits Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text(
                    'RECENT CUSTOMER VISITS',
                    style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppTheme.textDark, letterSpacing: 0.5),
                  ),
                  IconButton(
                    icon: const Icon(Icons.refresh, size: 20, color: AppTheme.primaryNavy),
                    onPressed: _fetchVisits,
                  ),
                ],
              ),

              if (_isLoadingVisits)
                const Center(child: Padding(padding: EdgeInsets.all(20), child: CircularProgressIndicator()))
              else if (_visits.isEmpty)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Center(
                      child: Column(
                        children: const [
                          Icon(Icons.storefront_outlined, size: 36, color: AppTheme.textMuted),
                          SizedBox(height: 8),
                          Text('No customer visits recorded today.', style: TextStyle(color: AppTheme.textMuted, fontSize: 13)),
                        ],
                      ),
                    ),
                  ),
                )
              else
                ListView.builder(
                  shrinkWrap: true,
                  physics: const NeverScrollableScrollPhysics(),
                  itemCount: _visits.length,
                  itemBuilder: (ctx, i) {
                    final v = _visits[i];
                    final hasAudio = v['has_audio_recording'] == true;
                    final dur = v['audio_duration_seconds'] ?? 0;
                    return Card(
                      margin: const EdgeInsets.only(bottom: 8),
                      child: ListTile(
                        leading: CircleAvatar(
                          backgroundColor: const Color(0xFFEFF6FF),
                          child: Icon(
                            hasAudio ? Icons.mic : Icons.business,
                            color: const Color(0xFF2563EB),
                            size: 20,
                          ),
                        ),
                        title: Text(
                          v['customer_name'] ?? 'Client Visit',
                          style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13.5),
                        ),
                        subtitle: Text(
                          '${v['product_pitched'] ?? 'Product'} • ₹${v['order_amount'] ?? 0} • ${v['lead_status'] ?? ''}',
                          style: const TextStyle(fontSize: 11.5, color: AppTheme.textMuted),
                        ),
                        trailing: hasAudio
                            ? Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFEFF6FF),
                                  borderRadius: BorderRadius.circular(6),
                                  border: Border.all(color: const Color(0xFFBFDBFE)),
                                ),
                                child: Text(
                                  '🎙️ ${dur.toString()}s தமிழ்',
                                  style: const TextStyle(fontSize: 10, fontWeight: FontWeight.w800, color: Color(0xFF1D4ED8)),
                                ),
                              )
                            : null,
                      ),
                    );
                  },
                ),
            ],
          ),
        ),
      ),
    );
  }
}
