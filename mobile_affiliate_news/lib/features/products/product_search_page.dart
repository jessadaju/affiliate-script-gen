import 'package:flutter/material.dart';
import '../../api_client.dart';
import '../content/content_preview_page.dart';

class ProductSearchPage extends StatefulWidget {
  const ProductSearchPage({super.key});

  @override
  State<ProductSearchPage> createState() => _ProductSearchPageState();
}

class _ProductSearchPageState extends State<ProductSearchPage> {
  final controller = TextEditingController(text: 'เครื่องอบรองเท้า');
  final api = ApiClient();
  bool loading = false;
  List<dynamic> products = [];
  String? error;

  Future<void> search() async {
    setState(() { loading = true; error = null; });
    try {
      products = await api.searchProducts(controller.text.trim());
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Product Hunter')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(children: [
          TextField(
            controller: controller,
            decoration: const InputDecoration(
              labelText: 'ค้นหาสินค้า Shopee',
              border: OutlineInputBorder(),
            ),
            onSubmitted: (_) => search(),
          ),
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: loading ? null : search,
            icon: const Icon(Icons.search),
            label: const Text('ค้นหาและจัดอันดับ'),
          ),
          if (loading) const Padding(
            padding: EdgeInsets.all(16), child: CircularProgressIndicator()),
          if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
          const SizedBox(height: 8),
          Expanded(
            child: ListView.builder(
              itemCount: products.length,
              itemBuilder: (context, index) {
                final p = products[index] as Map<String, dynamic>;
                return Card(
                  child: ListTile(
                    title: Text(p['title']?.toString() ?? '-'),
                    subtitle: Text(
                      '฿${p['price_thb']} • ขาย ${p['sold']} • รีวิว ${p['rating']} • คอม ${p['commission_rate']}%\nAd Potential ${p['ad_potential_score']}/100',
                    ),
                    isThreeLine: true,
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => Navigator.push(
                      context,
                      MaterialPageRoute(builder: (_) => ContentPreviewPage(product: p)),
                    ),
                  ),
                );
              },
            ),
          ),
        ]),
      ),
    );
  }
}
