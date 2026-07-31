import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'core/routing/app_router.dart';
import 'core/theme/app_theme.dart';

class HargaTurun extends ConsumerWidget {
  const HargaTurun({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final router = ref.watch(routerProvider);

    return MaterialApp.router(
      title: 'HargaTurun',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      routerConfig: router,
      locale: const Locale('id', 'ID'),
      supportedLocales: const [Locale('id', 'ID')],
      builder: (context, child) {
        final mq = MediaQuery.of(context);
        final clampedScaler = mq.textScaler.clamp(minScaleFactor: 0.9, maxScaleFactor: 1.3);
        return MediaQuery(
          data: mq.copyWith(textScaler: clampedScaler),
          child: child!,
        );
      },
    );
  }
}