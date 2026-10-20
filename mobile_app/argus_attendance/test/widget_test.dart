import 'package:flutter_test/flutter_test.dart';
import 'package:argus_attendance/main.dart';

void main() {
  testWidgets('Argus Attendance app smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ArgusAttendanceApp());
    expect(find.text('ARGUS ATTENDANCE'), findsOneWidget);
  });
}
