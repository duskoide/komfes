import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/user.dart';
import '../../state/session_providers.dart';

class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});

  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _intro = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 420),
  );

  @override
  void initState() {
    super.initState();
    _intro.forward();
    _decideNext();
  }

  @override
  void dispose() {
    _intro.dispose();
    super.dispose();
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
    final fade = CurvedAnimation(parent: _intro, curve: Curves.easeOut);

    return Scaffold(
      backgroundColor: AppColors.primary,
      body: Semantics(
        label: 'HargaTurun sedang memuat',
        child: Stack(
          children: [
            // Tengah optik: sedikit di atas titik tengah matematis, supaya
            // logo tidak terlihat "jatuh" — terutama di layar tablet.
            Align(
              alignment: const Alignment(0, -0.18),
              child: FadeTransition(
                opacity: fade,
                child: SlideTransition(
                  position: Tween<Offset>(
                    begin: const Offset(0, 0.06),
                    end: Offset.zero,
                  ).animate(fade),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 96,
                        height: 96,
                        decoration: const BoxDecoration(
                          color: Colors.white,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.trending_down_rounded,
                          color: AppColors.primary,
                          size: 52,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.xl),
                      Text(
                        'HargaTurun',
                        style: AppTypography.h1.copyWith(
                          color: Colors.white,
                          fontSize: 28,
                          letterSpacing: -0.3,
                        ),
                      ),
                      const SizedBox(height: AppSpacing.sm),
                      Text(
                        'Jangan buang, turunkan harganya.',
                        textAlign: TextAlign.center,
                        style: AppTypography.body.copyWith(
                          color: Colors.white.withValues(alpha: 0.92),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),

            // Indikator halus, tidak bersaing perhatian dengan logo.
            Align(
              alignment: const Alignment(0, 0.72),
              child: FadeTransition(
                opacity: fade,
                child: SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(
                    strokeWidth: 2,
                    strokeCap: StrokeCap.round,
                    color: Colors.white.withValues(alpha: 0.85),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
