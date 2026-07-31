import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import '../../widgets/offline_banner.dart';

/// Tab bar Konsumen: Deals / Klaim Saya / Profil.
class ConsumerShell extends StatelessWidget {
  const ConsumerShell({super.key, required this.navigationShell});

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
          BottomNavigationBarItem(icon: Icon(Icons.local_offer_outlined), label: 'Deals'),
          BottomNavigationBarItem(icon: Icon(Icons.confirmation_number_outlined), label: 'Klaim Saya'),
          BottomNavigationBarItem(icon: Icon(Icons.person_outline), label: 'Profil'),
        ],
      ),
    );
  }
}
