import 'dart:async';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

class AudioRecorderService {
  final AudioRecorder _audioRecorder = AudioRecorder();
  Timer? _timer;
  int _secondsElapsed = 0;
  String? _currentFilePath;
  bool _isRecording = false;
  bool _isPaused = false;

  final StreamController<int> _durationController = StreamController<int>.broadcast();
  Stream<int> get durationStream => _durationController.stream;

  bool get isRecording => _isRecording;
  bool get isPaused => _isPaused;
  int get secondsElapsed => _secondsElapsed;

  /// Requests microphone permission with Google Play compliant disclosure
  Future<bool> checkAndRequestPermission() async {
    final status = await Permission.microphone.status;
    if (status.isGranted) return true;

    final result = await Permission.microphone.request();
    return result.isGranted;
  }

  /// Starts recording high-clarity AAC/M4A audio from device microphone
  Future<bool> startRecording() async {
    final hasPerm = await checkAndRequestPermission();
    if (!hasPerm) return false;

    try {
      final tempDir = await getTemporaryDirectory();
      final timestamp = DateTime.now().millisecondsSinceEpoch;
      _currentFilePath = '${tempDir.path}/visit_audio_$timestamp.m4a';

      // Record AAC-LC compressed audio at 64kbps, 44.1kHz (optimal for voice & low upload size)
      await _audioRecorder.start(
        const RecordConfig(
          encoder: AudioEncoder.aacLc,
          bitRate: 64000,
          sampleRate: 44100,
        ),
        path: _currentFilePath!,
      );

      _isRecording = true;
      _isPaused = false;
      _secondsElapsed = 0;

      _timer?.cancel();
      _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
        if (!_isPaused) {
          _secondsElapsed++;
          _durationController.add(_secondsElapsed);
        }
      });

      return true;
    } catch (e) {
      debugPrint('Error starting audio recording: $e');
      return false;
    }
  }

  /// Pauses the active audio recording
  Future<void> pauseRecording() async {
    if (_isRecording && !_isPaused) {
      await _audioRecorder.pause();
      _isPaused = true;
    }
  }

  /// Resumes the paused audio recording
  Future<void> resumeRecording() async {
    if (_isRecording && _isPaused) {
      await _audioRecorder.resume();
      _isPaused = false;
    }
  }

  /// Stops recording and returns the path to the recorded audio file and total seconds
  Future<AudioRecordResult?> stopRecording() async {
    if (!_isRecording) return null;

    _timer?.cancel();
    final path = await _audioRecorder.stop();
    final duration = _secondsElapsed;

    _isRecording = false;
    _isPaused = false;
    _secondsElapsed = 0;

    final resolvedPath = path ?? _currentFilePath;
    if (resolvedPath != null && File(resolvedPath).existsSync()) {
      return AudioRecordResult(
        filePath: resolvedPath,
        durationSeconds: duration,
      );
    }
    return null;
  }

  /// Discards the current recording without saving
  Future<void> cancelRecording() async {
    _timer?.cancel();
    if (_isRecording) {
      final path = await _audioRecorder.stop();
      if (path != null && File(path).existsSync()) {
        try {
          File(path).deleteSync();
        } catch (_) {}
      }
    }
    _isRecording = false;
    _isPaused = false;
    _secondsElapsed = 0;
  }

  void dispose() {
    _timer?.cancel();
    _durationController.close();
    _audioRecorder.dispose();
  }
}

class AudioRecordResult {
  final String filePath;
  final int durationSeconds;

  AudioRecordResult({
    required this.filePath,
    required this.durationSeconds,
  });
}
