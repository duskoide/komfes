import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../widgets/offline_banner.dart';

/// Tab bar Vendor: Beranda / Deal Saya / Verifikasi / Profil.
class VendorShell extends StatelessWidget {
  const VendorShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          const OfflineBanner(),
          Expanded(child: navigationShell),
        ],
      ),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: navigationShell.currentIndex,
        onTap: (i) => navigationShell.goBranch(i, initialLocation: i == navigationShell.currentIndex),
        items: const [
          BottomNavigationBarItem(icon: Icon(Icons.storefront_outlined), label: 'Beranda'),
          BottomNavigationBarItem(icon: Icon(Icons.local_offer_outlined), label: 'Deal Saya'),
          BottomNavigationBarItem(icon: Icon(Icons.qr_code_scanner_outlined), label: 'Verifikasi'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'Profil'),
        ],
      ),
    );
  }
}
