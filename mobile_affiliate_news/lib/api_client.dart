import 'dart:convert';
import 'package:http/http.dart' as http;
import 'app_config.dart';

class ApiClient {
  Future<List<dynamic>> searchProducts(String keyword) async {
    final response = await http.post(
      AppConfig.apiUri('/products/search'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'keyword': keyword,
        'min_commission_rate': 0,
        'min_rating': 4.5,
        'limit': 10,
      }),
    );
    if (response.statusCode != 200) {
      throw Exception('ค้นหาสินค้าไม่สำเร็จ: ${response.body}');
    }
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<List<dynamic>> listNews() async {
    final response = await http.post(
      AppConfig.apiUri('/news/list'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'limit': 10}),
    );
    if (response.statusCode != 200) {
      throw Exception('โหลดข่าวไม่สำเร็จ: ${response.body}');
    }
    return jsonDecode(response.body) as List<dynamic>;
  }

  Future<Map<String, dynamic>> generateContent({
    required Map<String, dynamic> product,
    required Map<String, dynamic> news,
    String angle = 'news_problem',
  }) async {
    final response = await http.post(
      AppConfig.apiUri('/content/generate'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'product': product,
        'news': news,
        'angle': angle,
        'tone_level': 4,
      }),
    );
    if (response.statusCode != 200) {
      throw Exception('สร้างคอนเทนต์ไม่สำเร็จ: ${response.body}');
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<void> trackClick(Map<String, dynamic> product) async {
    final response = await http.post(
      AppConfig.apiUri('/tracking/outbound-click'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'product_id': product['item_id'],
        'placement': 'mobile_app',
        'consented_navigation': true,
        'destination_url': product['affiliate_url'],
      }),
    );
    if (response.statusCode != 200) {
      throw Exception('บันทึกคลิกไม่สำเร็จ');
    }
  }
}
