import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_typography.dart';
import '../../models/user.dart';
import '../../state/session_providers.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen> {
  @override
  void initState() {
    super.initState();
    _decideNext();
  }

  Future<void> _decideNext() async {
    final sessionCheck = _checkSessionInBackground();
    await Future.wait([
      Future.delayed(const Duration(milliseconds: 900)),
      sessionCheck.timeout(const Duration(milliseconds: 1800), onTimeout: () => null),
    ]);
    if (!mounted) return;

    final hasSeenOnboarding = ref.read(hasSeenOnboardingProvider);
    final session = ref.read(sessionProvider);
    final role = ref.read(activeRoleProvider);

    if (!hasSeenOnboarding) {
      context.go(RoutePaths.onboarding);
      return;
    }
    if (session != null && role == AppRole.vendor) {
      context.go(RoutePaths.vendorHome);
      return;
    }
    if (role == AppRole.consumer) {
      context.go(RoutePaths.consumerFeed);
      return;
    }
    context.go(RoutePaths.role);
  }

  Future<UserSession?> _checkSessionInBackground() async {
    return ref.read(sessionProvider);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppColors.primary,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 96,
              height: 96,
              decoration: const BoxDecoration(color: Colors.white, shape: BoxShape.circle),
              child: const Icon(Icons.trending_down_rounded, color: AppColors.primary, size: 52),
            ),
            const SizedBox(height: 20),
            Text(
              'HargaTurun',
              style: AppTypography.h1.copyWith(color: Colors.white, fontSize: 28),
            ),
            const SizedBox(height: 8),
            Text(
              'Jangan buang, turunkan harganya.',
              style: AppTypography.body.copyWith(color: Colors.white.withOpacity(0.9)),
            ),
            const SizedBox(height: 40),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(strokeWidth: 2.4, color: Colors.white),
            ),
          ],
        ),
      ),
    );
  }
}
