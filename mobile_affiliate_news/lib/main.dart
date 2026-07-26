import 'package:flutter/material.dart';
import 'features/products/product_search_page.dart';

void main() => runApp(const AffiliateApp());

class AffiliateApp extends StatelessWidget {
  const AffiliateApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Affiliate News Factory',
      theme: ThemeData(useMaterial3: true),
      home: const ProductSearchPage(),
    );
  }
}
