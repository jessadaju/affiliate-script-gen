import 'dart:convert';
import 'package:http/http.dart' as http;
import 'app_config.dart';

class ApiClient {
  static String accessToken = '';

  Map<String, String> get _headers {
    final token = accessToken.trim();
    return {
      'Content-Type': 'application/json',
      if (token.isNotEmpty) 'Authorization': 'Bearer $token',
      if (token.isNotEmpty) 'x-api-key': token,
    };
  }

  Future<List<dynamic>> searchProducts(String keyword) async {
    final response = await http.post(
      AppConfig.apiUri('/products/search'),
      headers: _headers,
      body: jsonEncode({
        'keyword': keyword,
        'min_commission_rate': 0,
        'min_rating': 4.5,
        'limit': 10,
      }),
    );
    if (response.statusCode == 401) {
      throw Exception('Backend ไม่อนุญาต: กรุณาใส่ Mobile Access Token ให้ถูกต้อง');
    }
    if (response.statusCode != 200) {
      throw Exception('ค้นหาสินค้าไม่สำเร็จ (${response.statusCode}): ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is List<dynamic>) return decoded;
    if (decoded is Map<String, dynamic>) {
      final items = decoded['items'] ?? decoded['products'] ?? decoded['data'];
      if (items is List<dynamic>) return items;
    }
    throw Exception('รูปแบบข้อมูลสินค้าจาก Backend ไม่ถูกต้อง');
  }

  Future<List<dynamic>> listNews() async {
    final response = await http.post(
      AppConfig.apiUri('/news/list'),
      headers: _headers,
      body: jsonEncode({'limit': 10}),
    );
    if (response.statusCode == 401) {
      throw Exception('Backend ไม่อนุญาต: Mobile Access Token ไม่ถูกต้อง');
    }
    if (response.statusCode != 200) {
      throw Exception('โหลดข่าวไม่สำเร็จ (${response.statusCode}): ${response.body}');
    }
    final decoded = jsonDecode(response.body);
    if (decoded is List<dynamic>) return decoded;
    if (decoded is Map<String, dynamic>) {
      final items = decoded['items'] ?? decoded['news'] ?? decoded['data'];
      if (items is List<dynamic>) return items;
    }
    throw Exception('รูปแบบข้อมูลข่าวจาก Backend ไม่ถูกต้อง');
  }

  Future<Map<String, dynamic>> generateContent({
    required Map<String, dynamic> product,
    required Map<String, dynamic> news,
    String angle = 'news_problem',
  }) async {
    final response = await http.post(
      AppConfig.apiUri('/content/generate'),
      headers: _headers,
      body: jsonEncode({
        'product': product,
        'news': news,
        'angle': angle,
        'tone_level': 4,
      }),
    );
    if (response.statusCode == 401) {
      throw Exception('Backend ไม่อนุญาต: Mobile Access Token ไม่ถูกต้อง');
    }
    if (response.statusCode != 200) {
      throw Exception('สร้างคอนเทนต์ไม่สำเร็จ (${response.statusCode}): ${response.body}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> trackClick(Map<String, dynamic> product) async {
    final response = await http.post(
      AppConfig.apiUri('/tracking/outbound-click'),
      headers: _headers,
      body: jsonEncode({
        'product_id': product['item_id'],
        'placement': 'mobile_app',
        'consented_navigation': true,
        'destination_url': product['affiliate_url'],
      }),
    );
    if (response.statusCode != 200) {
      throw Exception('บันทึกคลิกไม่สำเร็จ (${response.statusCode})');
    }
  }
}
