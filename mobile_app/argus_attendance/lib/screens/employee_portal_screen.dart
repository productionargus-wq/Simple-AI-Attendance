import 'package:flutter/material.dart';
import '../constants/app_theme.dart';
import '../services/api_service.dart';

class EmployeePortalScreen extends StatefulWidget {
  const EmployeePortalScreen({super.key});

  @override
  State<EmployeePortalScreen> createState() => _EmployeePortalScreenState();
}

class _EmployeePortalScreenState extends State<EmployeePortalScreen> {
  String _employeeName = 'Employee';

  @override
  void initState() {
    super.initState();
    _loadSession();
  }

  Future<void> _loadSession() async {
    final name = await ApiService.getActiveEmployeeName();
    if (mounted) {
      setState(() {
        if (name != null) _employeeName = name;
      });
    }
  }

  void _showApplyLeaveDialog() {
    final reasonCtrl = TextEditingController();
    String leaveType = 'Casual Leave (CL)';
    String sessionType = 'Full Day';

    showDialog(
      context: context,
      builder: (ctx) {
        return StatefulBuilder(
          builder: (context, setModalState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Apply for Leave', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  DropdownButtonFormField<String>(
                    initialValue: leaveType,
                    decoration: const InputDecoration(labelText: 'Leave Type', border: OutlineInputBorder(), isDense: true),
                    items: const [
                      DropdownMenuItem(value: 'Casual Leave (CL)', child: Text('Casual Leave (CL)')),
                      DropdownMenuItem(value: 'Sick Leave (SL)', child: Text('Sick Leave (SL)')),
                      DropdownMenuItem(value: 'Earned Leave (EL)', child: Text('Earned Leave (EL)')),
                    ],
                    onChanged: (val) {
                      if (val != null) setModalState(() => leaveType = val);
                    },
                  ),
                  const SizedBox(height: 10),
                  DropdownButtonFormField<String>(
                    initialValue: sessionType,
                    decoration: const InputDecoration(labelText: 'Session', border: OutlineInputBorder(), isDense: true),
                    items: const [
                      DropdownMenuItem(value: 'Full Day', child: Text('Full Day (1.0)')),
                      DropdownMenuItem(value: 'Half Day', child: Text('Half Day (0.5)')),
                    ],
                    onChanged: (val) {
                      if (val != null) setModalState(() => sessionType = val);
                    },
                  ),
                  const SizedBox(height: 10),
                  TextField(
                    controller: reasonCtrl,
                    maxLines: 2,
                    decoration: const InputDecoration(
                      labelText: 'Reason for Leave',
                      border: OutlineInputBorder(),
                      isDense: true,
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
                  onPressed: () {
                    Navigator.pop(ctx);
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(
                        backgroundColor: AppTheme.successGreen,
                        content: Text('Leave application submitted for approval!'),
                      ),
                    );
                  },
                  child: const Text('Submit Request'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  void _showApplyPermissionDialog() {
    final reasonCtrl = TextEditingController();
    final durationCtrl = TextEditingController(text: '1.5');

    showDialog(
      context: context,
      builder: (ctx) {
        return AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          title: const Text('Request Permission (Short Leave)', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: durationCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Duration (Hours)',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
              const SizedBox(height: 10),
              TextField(
                controller: reasonCtrl,
                maxLines: 2,
                decoration: const InputDecoration(
                  labelText: 'Reason for Permission',
                  border: OutlineInputBorder(),
                  isDense: true,
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
              onPressed: () {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(
                    backgroundColor: AppTheme.successGreen,
                    content: Text('Permission request submitted successfully!'),
                  ),
                );
              },
              child: const Text('Submit Permission'),
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
        title: const Text('EMPLOYEE PORTAL'),
        backgroundColor: AppTheme.primaryNavy,
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Employee Profile Summary Card
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Container(
                        width: 52,
                        height: 52,
                        decoration: BoxDecoration(
                          color: AppTheme.primaryElectricBlue.withValues(alpha: 0.12),
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(Icons.person, color: AppTheme.primaryElectricBlue, size: 28),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              _employeeName,
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: AppTheme.textDark),
                            ),
                            const SizedBox(height: 2),
                            const Text(
                              'Verified Staff • Operations Department',
                              style: TextStyle(fontSize: 12, color: AppTheme.textMuted),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 14),

              // Quick Actions: Leave & Permission
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _showApplyLeaveDialog,
                      icon: const Icon(Icons.calendar_month, size: 18),
                      label: const Text('Apply Leave', style: TextStyle(fontSize: 12.5)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryNavy,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _showApplyPermissionDialog,
                      icon: const Icon(Icons.timer_outlined, size: 18),
                      label: const Text('Permission', style: TextStyle(fontSize: 12.5)),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryElectricBlue,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ),
                ],
              ),

              const SizedBox(height: 18),

              // Attendance & Payslip Cards
              const Text(
                'MONTHLY ATTENDANCE & PAYSLIP',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: AppTheme.textDark, letterSpacing: 0.5),
              ),
              const SizedBox(height: 8),

              Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: const [
                          Text('Working Days', style: TextStyle(fontSize: 13, color: AppTheme.textMuted)),
                          Text('24 Days', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700)),
                        ],
                      ),
                      const Divider(height: 20),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: const [
                          Text('Paid Leave Balance', style: TextStyle(fontSize: 13, color: AppTheme.textMuted)),
                          Text('4.5 Days (CL: 2, SL: 2.5)', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Color(0xFF15803D))),
                        ],
                      ),
                      const Divider(height: 20),
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          const Text('Current Month Payslip', style: TextStyle(fontSize: 13, color: AppTheme.textMuted)),
                          TextButton.icon(
                            onPressed: () {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('Downloading official signed payslip PDF...')),
                              );
                            },
                            icon: const Icon(Icons.download, size: 16),
                            label: const Text('Download PDF', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w700)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
