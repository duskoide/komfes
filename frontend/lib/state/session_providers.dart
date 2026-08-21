import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/user.dart';

/// Sesi user saat ini. `null` = belum login (tamu). Konsumen BOLEH null
/// (browsing tanpa login), vendor wajib terisi sebelum masuk
class SessionNotifier extends StateNotifier<UserSession?> {
  SessionNotifier() : super(null);

  void setSession(UserSession session) => state = session;

  void updateShop(ShopProfile shop) {
    if (state != null) state = state!.copyWith(shop: shop);
  }

  void logout() => state = null;
}

final sessionProvider = StateNotifierProvider<SessionNotifier, UserSession?>(
  (ref) => SessionNotifier(),
);

final isLoggedInProvider = Provider<bool>((ref) => ref.watch(sessionProvider) != null);

/// Role tampilan aktif: terpisah dari sesi karena satu nomor HP
/// bisa punya dua role dan guest konsumen belum tentu punya sesi sama sekali.
final activeRoleProvider = StateProvider<AppRole?>((ref) => null);

/// Flag onboarding sudah dilihat
final hasSeenOnboardingProvider = StateProvider<bool>((ref) => false);

/// Konteks "kembali ke sini setelah login" dipakai saat konsumen menekan
/// Klaim tanpa login
final pendingClaimDealIdProvider = StateProvider<String?>((ref) => null);
