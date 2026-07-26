import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../api_client.dart';

class ContentPreviewPage extends StatefulWidget {
  final Map<String, dynamic> product;
  const ContentPreviewPage({super.key, required this.product});

  @override
  State<ContentPreviewPage> createState() => _ContentPreviewPageState();
}

class _ContentPreviewPageState extends State<ContentPreviewPage> {
  final api = ApiClient();
  List<dynamic> newsItems = [];
  Map<String, dynamic>? selectedNews;
  Map<String, dynamic>? content;
  bool loading = true;
  String angle = 'news_problem';
  String? error;

  @override
  void initState() {
    super.initState();
    loadNews();
  }

  Future<void> loadNews() async {
    try {
      newsItems = await api.listNews();
      if (newsItems.isNotEmpty) selectedNews = newsItems.first as Map<String, dynamic>;
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> generate() async {
    if (selectedNews == null) return;
    setState(() { loading = true; error = null; });
    try {
      content = await api.generateContent(product: widget.product, news: selectedNews!, angle: angle);
    } catch (e) {
      error = e.toString();
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> openShopee() async {
    await api.trackClick(widget.product);
    final uri = Uri.parse(widget.product['affiliate_url'] as String);
    if (!await launchUrl(uri, mode: LaunchMode.externalApplication)) {
      throw Exception('ไม่สามารถเปิด Shopee ได้');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('News Content Factory')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(widget.product['title']?.toString() ?? '-', style: Theme.of(context).textTheme.titleLarge),
          Text('โหมดข้อมูล: ${widget.product['data_mode']} • Ad Potential ${widget.product['ad_potential_score']}/100'),
          const SizedBox(height: 16),
          if (loading) const Center(child: CircularProgressIndicator()),
          if (error != null) Text(error!, style: const TextStyle(color: Colors.red)),
          if (newsItems.isNotEmpty) ...[
            DropdownButtonFormField<Map<String, dynamic>>(
              value: selectedNews,
              decoration: const InputDecoration(labelText: 'เลือกข่าวจริง', border: OutlineInputBorder()),
              items: newsItems.map((raw) {
                final item = raw as Map<String, dynamic>;
                return DropdownMenuItem(value: item, child: Text(item['headline']?.toString() ?? '-', overflow: TextOverflow.ellipsis));
              }).toList(),
              onChanged: (value) => setState(() => selectedNews = value),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              value: angle,
              decoration: const InputDecoration(labelText: 'มุมคอนเทนต์', border: OutlineInputBorder()),
              items: const [
                DropdownMenuItem(value: 'news_problem', child: Text('ข่าวเชื่อมปัญหา')),
                DropdownMenuItem(value: 'checklist', child: Text('Checklist')),
                DropdownMenuItem(value: 'comparison', child: Text('เปรียบเทียบ')),
                DropdownMenuItem(value: 'advertorial', child: Text('Advertorial')),
              ],
              onChanged: (value) => setState(() => angle = value ?? 'news_problem'),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(onPressed: loading ? null : generate, icon: const Icon(Icons.auto_awesome), label: const Text('สร้างคอนเทนต์จากข่าว')),
          ],
          if (content != null) ...[
            const SizedBox(height: 20),
            _section('Hook', content!['hook']),
            _section('เนื้อหา', content!['body']),
            _section('CTA', content!['cta']),
            _section('Prompt ภาพ', content!['image_prompt']),
            _section('แหล่งข่าว', content!['source_line']),
            Card(child: ListTile(
              leading: Icon(content!['publish_ready'] == true ? Icons.verified : Icons.warning),
              title: Text(content!['publish_ready'] == true ? 'พร้อมตรวจเผยแพร่' : 'ต้องตรวจเพิ่มเติม'),
              subtitle: Text('Claim risk: ${content!['claim_risk']}'),
            )),
          ],
          const SizedBox(height: 16),
          FilledButton.tonalIcon(onPressed: openShopee, icon: const Icon(Icons.open_in_new), label: const Text('เช็กราคาและรีวิวใน Shopee')),
          const SizedBox(height: 8),
          const Text('ลิงก์ Affiliate: ผู้จัดทำอาจได้รับค่าคอมมิชชัน โดยผู้ซื้อไม่มีค่าใช้จ่ายเพิ่ม', textAlign: TextAlign.center),
        ],
      ),
    );
  }

  Widget _section(String title, dynamic value) => Card(
    child: Padding(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        SelectableText(value?.toString() ?? ''),
      ]),
    ),
  );
}
