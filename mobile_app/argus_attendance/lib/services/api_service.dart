import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ApiService {
  // Default server base URL (user configurable in app settings)
  // 10.0.2.2 is standard Android emulator loopback for localhost:5000.
  // For physical devices on the same Wi-Fi, this can be set to the server IP.
  static const String defaultBaseUrl = 'http://10.0.2.2:5000';
  static const String keyBaseUrl = 'argus_api_base_url';
  static const String keyRememberToken = 'argus_remember_token';
  static const String keyActiveCompanyId = 'argus_company_id';
  static const String keyActiveEmployeeName = 'argus_employee_name';

  static Future<String> getBaseUrl() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyBaseUrl) ?? defaultBaseUrl;
  }

  static Future<void> setBaseUrl(String url) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(keyBaseUrl, url.trim().replaceAll(RegExp(r'/+$'), ''));
  }

  static Future<String?> getActiveCompanyId() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyActiveCompanyId) ?? 'ARGUS_MASTER';
  }

  static Future<String?> getActiveEmployeeName() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(keyActiveEmployeeName);
  }

  static Future<void> setActiveEmployee(String name, String companyId) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(keyActiveEmployeeName, name);
    await prefs.setString(keyActiveCompanyId, companyId);
  }

  /// Facial recognition biometric attendance punch via /api/face/recognize
  static Future<Map<String, dynamic>> recognizeFace(
    File photoFile, {
    double? latitude,
    double? longitude,
  }) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final uri = Uri.parse('$baseUrl/api/face/recognize');

    final request = http.MultipartRequest('POST', uri);
    request.fields['client_time'] = DateTime.now().toIso8601String();
    if (companyId != null && companyId.isNotEmpty) {
      request.fields['company_id'] = companyId;
    }
    if (latitude != null && longitude != null) {
      request.fields['latitude'] = latitude.toString();
      request.fields['longitude'] = longitude.toString();
    }

    final multipartFile = await http.MultipartFile.fromPath(
      'photo',
      photoFile.path,
    );
    request.files.add(multipartFile);

    try {
      final streamedResponse = await request.send().timeout(const Duration(seconds: 25));
      final response = await http.Response.fromStream(streamedResponse);
      final body = json.decode(response.body);
      if (body is Map<String, dynamic>) {
        return body;
      }
      return {'matched': false, 'message': 'Invalid server response'};
    } catch (e) {
      return {'matched': false, 'message': 'Connection error: ${e.toString()}'};
    }
  }

  /// Manual PIN attendance punch fallback
  static Future<Map<String, dynamic>> punchWithPin({
    required String employeeCode,
    required String pin,
    double? latitude,
    double? longitude,
  }) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final uri = Uri.parse('$baseUrl/api/auth/employee-pin-punch');

    try {
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'employee_code': employeeCode.trim(),
          'pin': pin.trim(),
          'company_id': companyId,
          'latitude': latitude,
          'longitude': longitude,
          'timestamp': DateTime.now().toIso8601String(),
        }),
      ).timeout(const Duration(seconds: 15));

      return json.decode(response.body) as Map<String, dynamic>;
    } catch (e) {
      return {'success': false, 'error': 'Network error: ${e.toString()}'};
    }
  }

  /// Background GPS telemetry ping for Field Worker route tracking
  static Future<Map<String, dynamic>> sendLocationPing({
    required String employeeName,
    required double latitude,
    required double longitude,
    String? address,
    String? activityNote,
  }) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final uri = Uri.parse('$baseUrl/api/field-worker/location-ping');

    try {
      final response = await http.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: json.encode({
          'company_id': companyId,
          'employee_name': employeeName,
          'latitude': latitude,
          'longitude': longitude,
          'address': address ?? '',
          'activity_note': activityNote ?? 'Active field route tracking',
        }),
      ).timeout(const Duration(seconds: 15));

      return json.decode(response.body) as Map<String, dynamic>;
    } catch (e) {
      return {'success': false, 'error': e.toString()};
    }
  }

  /// Uploads a completed Customer Visit with recorded Tamil Audio file for Gemini AI Speech-to-Text
  static Future<Map<String, dynamic>> uploadCustomerVisitWithAudio({
    required Map<String, String> visitData,
    String? audioFilePath,
    double durationSeconds = 0.0,
  }) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final uri = Uri.parse('$baseUrl/api/field-worker/customer-visits');

    final request = http.MultipartRequest('POST', uri);
    request.fields.addAll(visitData);
    if (companyId != null && companyId.isNotEmpty && !request.fields.containsKey('company_id')) {
      request.fields['company_id'] = companyId;
    }
    request.fields['duration_seconds'] = durationSeconds.toString();

    if (audioFilePath != null && audioFilePath.isNotEmpty && File(audioFilePath).existsSync()) {
      final audioFile = await http.MultipartFile.fromPath(
        'audio_file',
        audioFilePath,
      );
      request.files.add(audioFile);
    }

    try {
      final streamedResponse = await request.send().timeout(const Duration(seconds: 45));
      final response = await http.Response.fromStream(streamedResponse);
      final body = json.decode(response.body);
      if (body is Map<String, dynamic>) {
        return body;
      }
      return {'success': false, 'error': 'Unexpected server response'};
    } catch (e) {
      return {'success': false, 'error': 'Upload failed: ${e.toString()}'};
    }
  }

  /// Fetches scheduled or logged customer visits for field worker
  static Future<List<dynamic>> fetchCustomerVisits({String? employeeName}) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    var url = '$baseUrl/api/field-worker/customer-visits?company_id=$companyId';
    if (employeeName != null && employeeName.isNotEmpty) {
      url += '&employee_name=${Uri.encodeComponent(employeeName)}';
    }

    try {
      final response = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 15));
      final data = json.decode(response.body);
      if (data is Map<String, dynamic> && data['success'] == true) {
        return data['visits'] as List<dynamic>? ?? [];
      }
      return [];
    } catch (_) {
      return [];
    }
  }

  /// Fetches Tamil transcript and AI summary for a specific visit
  static Future<Map<String, dynamic>?> fetchVisitTranscript(String visitId) async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final url = '$baseUrl/api/field-worker/visits/$visitId/transcript?company_id=$companyId';

    try {
      final response = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 15));
      final data = json.decode(response.body);
      if (data is Map<String, dynamic> && data['success'] == true) {
        return data;
      }
      return null;
    } catch (_) {
      return null;
    }
  }

  /// Fetches dynamic Product Warehouse items and pricing from Google Sheets / Flask backend
  static Future<List<Map<String, dynamic>>> fetchWarehouseProducts() async {
    final baseUrl = await getBaseUrl();
    final companyId = await getActiveCompanyId();
    final url = '$baseUrl/api/field-worker/products?company_id=$companyId';

    try {
      final response = await http.get(Uri.parse(url)).timeout(const Duration(seconds: 15));
      final data = json.decode(response.body);
      if (data is Map<String, dynamic> && data['success'] == true && data['products'] is List) {
        return List<Map<String, dynamic>>.from(data['products']);
      }
      return [];
    } catch (_) {
      return [];
    }
  }
}
