import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'constants/app_theme.dart';
import 'screens/attendance_terminal_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Lock to portrait mode for consistent biometric kiosk and field use
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  runApp(const ArgusAttendanceApp());
}

class ArgusAttendanceApp extends StatelessWidget {
  const ArgusAttendanceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Argus Attendance',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      // The Attendance Terminal is the primary launch screen
      home: const AttendanceTerminalScreen(),
    );
  }
}
