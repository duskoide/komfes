import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:hargaturun/app.dart';
import 'package:hargaturun/core/routing/app_router.dart';
import 'package:hargaturun/core/routing/route_paths.dart';

void main() {
  testWidgets('opening /otp without extra redirects to phone input instead of crashing',
      (tester) async {
    final container = ProviderContainer();
    addTearDown(container.dispose);
    final router = container.read(routerProvider);

    router.go(RoutePaths.otp); // no extra — mirrors a web reload / deep-link

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const HargaTurun(),
      ),
    );
    await tester.pumpAndSettle();

    // Must not throw a null-cast during build.
    expect(tester.takeException(), isNull);
    // Should land on the phone-entry screen.
    expect(find.text('Masuk atau Daftar'), findsOneWidget);
  });
}
