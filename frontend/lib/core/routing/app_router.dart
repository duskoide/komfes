import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../models/recommendation.dart';
import '../../features/auth/otp_screen.dart';
import '../../features/auth/phone_input_screen.dart';
import '../../features/consumer/claim_code_screen.dart';
import '../../features/consumer/consumer_profile_screen.dart';
import '../../features/consumer/deal_detail_screen.dart';
import '../../features/consumer/feed_screen.dart';
import '../../features/consumer/my_claims_screen.dart';
import '../../features/onboarding/onboarding_screen.dart';
import '../../features/role/role_select_screen.dart';
import '../../features/shell/consumer_shell.dart';
import '../../features/shell/vendor_shell.dart';
import '../../features/splash/splash_screen.dart';
import '../../features/vendor/active_deals_screen.dart';
import '../../features/vendor/ai_processing_screen.dart';
import '../../features/vendor/chat_screen.dart';
import '../../features/vendor/check_item_screen.dart';
import '../../features/vendor/confirm_data_screen.dart';
import '../../features/vendor/dashboard_screen.dart';
import '../../features/vendor/deal_detail_screen.dart';
import '../../features/vendor/input_warning_screen.dart';
import '../../features/vendor/no_action_screen.dart';
import '../../features/vendor/recommendation_result_screen.dart';
import '../../features/vendor/setup_shop_screen.dart';
import '../../features/vendor/shop_profile_screen.dart';
import '../../features/vendor/verify_code_screen.dart';
import '../../features/vendor/verify_result_screen.dart';
import 'route_paths.dart';

final routerProvider = Provider<GoRouter>((ref) {
  return GoRouter(
    initialLocation: RoutePaths.splash,
    overridePlatformDefaultLocation: true,
    routes: [
      GoRoute(path: RoutePaths.splash, builder: (context, state) => const SplashScreen()),
      GoRoute(path: RoutePaths.onboarding, builder: (context, state) => const OnboardingScreen()),
      GoRoute(path: RoutePaths.role, builder: (context, state) => const RoleSelectScreen()),
      GoRoute(
        path: RoutePaths.phone,
        builder: (context, state) {
          final extra = (state.extra as Map?) ?? {};
          return PhoneInputScreen(
            extraContext: extra['context'] as String? ?? 'vendor',
            pendingDealId: extra['dealId'] as String?,
          );
        },
      ),
      GoRoute(
        path: RoutePaths.otp,
        builder: (context, state) {
          final extra = (state.extra as Map?) ?? {};
          return OtpVerifyScreen(
            phone: extra['phone'] as String,
            extraContext: extra['context'] as String? ?? 'vendor',
            pendingDealId: extra['dealId'] as String?,
          );
        },
      ),
      GoRoute(path: RoutePaths.setupShop, builder: (context, state) => const SetupShopScreen()),

      // === Vendor sub-halaman (di atas shell, tanpa bottom nav) ===
      GoRoute(path: RoutePaths.vendorChat, builder: (context, state) => const ChatScreen()),
      GoRoute(
        path: RoutePaths.vendorCheckItem,
        builder: (context, state) => CheckItemScreen(prefill: state.extra as ItemInputDraft?),
      ),
      GoRoute(path: RoutePaths.vendorConfirm, builder: (context, state) => const ConfirmDataScreen()),
      GoRoute(
        path: RoutePaths.vendorProcessing,
        builder: (context, state) => AiProcessingScreen(draft: state.extra as ItemInputDraft),
      ),
      GoRoute(
        path: RoutePaths.vendorResult,
        builder: (context, state) => const RecommendationResultScreen(),
      ),
      GoRoute(path: RoutePaths.vendorNoAction, builder: (context, state) => const NoActionScreen()),
      GoRoute(path: RoutePaths.vendorWarning, builder: (context, state) => const InputWarningScreen()),
      GoRoute(
        path: RoutePaths.vendorDealDetail,
        builder: (context, state) =>
            VendorDealDetailScreen(dealId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: RoutePaths.vendorVerifyResult,
        builder: (context, state) => const VerifyResultScreen(),
      ),

      // === Consumer sub-halaman ===
      GoRoute(
        path: RoutePaths.consumerDealDetail,
        builder: (context, state) =>
            ConsumerDealDetailScreen(dealId: state.pathParameters['id']!),
      ),
      GoRoute(
        path: RoutePaths.consumerClaimCode,
        builder: (context, state) =>
            ClaimCodeScreen(code: state.pathParameters['code']!),
      ),

      // === Shell Vendor: Beranda / Deal Saya / Verifikasi / Profil ===
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => VendorShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.vendorHome, builder: (context, state) => const VendorDashboardScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.vendorDeals, builder: (context, state) => const ActiveDealsScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.vendorVerify, builder: (context, state) => const VerifyCodeScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.vendorProfile, builder: (context, state) => const VendorProfileScreen()),
          ]),
        ],
      ),

      // === Shell Konsumen: Deals / Klaim Saya / Profil ===
      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => ConsumerShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.consumerFeed, builder: (context, state) => const ConsumerFeedScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(path: RoutePaths.consumerClaims, builder: (context, state) => const MyClaimsScreen()),
          ]),
          StatefulShellBranch(routes: [
            GoRoute(
              path: RoutePaths.consumerProfile,
              builder: (context, state) => const ConsumerProfileScreen(),
            ),
          ]),
        ],
      ),
    ],
  );
});