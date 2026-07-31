import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/theme/breakpoints.dart';
import '../../state/session_providers.dart';

class _Slide {
  const _Slide(this.icon, this.title, this.body);
  final IconData icon;
  final String title;
  final String body;
}

const _slides = [
  _Slide(Icons.inventory_2_outlined, 'Stok mau kadaluarsa?\nJangan dibuang.',
      'Cek barangmu dan dapatkan solusi dalam hitungan detik.'),
  _Slide(Icons.auto_awesome, 'AI hitung harga diskon yang pas.',
      'Nggak rugi, nggak kebanyakan — angka dari perhitungan, bukan tebakan.'),
  _Slide(Icons.storefront, 'Pembeli sekitar langsung\nlihat promomu.',
      'Sekali publikasi, deal tayang dan siap diklaim.'),
];

class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final _controller = PageController();
  int _page = 0;

  void _finish() {
    ref.read(hasSeenOnboardingProvider.notifier).state = true;
    context.go(RoutePaths.role);
  }

  @override
  Widget build(BuildContext context) {
    final isTablet = Breakpoints.isTabletOf(context);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.md),
                child: TextButton(onPressed: _finish, child: const Text('Lewati')),
              ),
            ),
            Expanded(
              child: PageView.builder(
                controller: _controller,
                itemCount: _slides.length,
                onPageChanged: (i) => setState(() => _page = i),
                itemBuilder: (context, i) {
                  final slide = _slides[i];
                  if (isTablet) {
                    return Padding(
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xxl),
                      child: Row(
                        children: [
                          Expanded(child: _Illustration(icon: slide.icon)),
                          const SizedBox(width: AppSpacing.xxl),
                          Expanded(child: _SlideText(slide: slide)),
                        ],
                      ),
                    );
                  }
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: AppSpacing.xl),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        _Illustration(icon: slide.icon),
                        const SizedBox(height: AppSpacing.xxl),
                        _SlideText(slide: slide),
                      ],
                    ),
                  );
                },
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: List.generate(_slides.length, (i) {
                final active = i == _page;
                return AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  margin: const EdgeInsets.symmetric(horizontal: 4),
                  width: active ? 22 : 8,
                  height: 8,
                  decoration: BoxDecoration(
                    color: active ? AppColors.primary : AppColors.border,
                    borderRadius: BorderRadius.circular(AppSpacing.radiusPill),
                  ),
                );
              }),
            ),
            Padding(
              padding: const EdgeInsets.all(AppSpacing.xl),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    if (_page == _slides.length - 1) {
                      _finish();
                    } else {
                      _controller.nextPage(
                        duration: const Duration(milliseconds: 250),
                        curve: Curves.easeOut,
                      );
                    }
                  },
                  child: Text(_page == _slides.length - 1 ? 'Mulai' : 'Lanjut'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Illustration extends StatelessWidget {
  const _Illustration({required this.icon});
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 200,
      decoration: BoxDecoration(
        color: AppColors.primaryLight,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
      ),
      child: Icon(icon, size: 72, color: AppColors.primary),
    );
  }
}

class _SlideText extends StatelessWidget {
  const _SlideText({required this.slide});
  final _Slide slide;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(slide.title, style: AppTypography.h1),
        const SizedBox(height: AppSpacing.sm),
        Text(slide.body, style: AppTypography.body.copyWith(color: AppColors.textSecondary)),
      ],
    );
  }
}
