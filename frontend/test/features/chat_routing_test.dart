import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';
import 'package:hargaturun/core/routing/route_paths.dart';
import 'package:hargaturun/features/vendor/chat_screen.dart';
import 'package:hargaturun/features/vendor/check_item_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

void main() {
  testWidgets('legacy parsing route redirects to primary chat', (tester) async {
    final router = GoRouter(
      initialLocation: RoutePaths.vendorCheckItem,
      routes: [
        GoRoute(path: RoutePaths.vendorChat, builder: (_, __) => const ChatScreen()),
        GoRoute(path: RoutePaths.vendorCheckItem, redirect: (_, __) => RoutePaths.vendorChat),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(router.routeInformationProvider.value.uri.path, RoutePaths.vendorChat);
    expect(find.byType(ChatScreen), findsOneWidget);
  });

  testWidgets('manual fallback route remains reachable without toggle', (tester) async {
    final router = GoRouter(
      initialLocation: RoutePaths.vendorManualForm,
      routes: [
        GoRoute(path: RoutePaths.vendorManualForm, builder: (_, __) => const CheckItemScreen()),
      ],
    );
    await tester.pumpWidget(
      ProviderScope(
        child: MaterialApp.router(routerConfig: router),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.byType(CheckItemScreen), findsOneWidget);
    expect(find.text('Ketik Bebas'), findsNothing);
    expect(find.text('Isi Form'), findsNothing);
  });
}
