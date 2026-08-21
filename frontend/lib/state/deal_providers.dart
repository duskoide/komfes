import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/deal.dart';
import '../models/enums.dart';
import '../services/app_exception.dart';
import 'repository_providers.dart';

/// Daftar deal aktif untuk feed konsumen
final consumerFeedProvider =
    AsyncNotifierProvider<ConsumerFeedNotifier, List<Deal>>(ConsumerFeedNotifier.new);

class ConsumerFeedNotifier extends AsyncNotifier<List<Deal>> {
  @override
  Future<List<Deal>> build() => _fetch();

  Future<List<Deal>> _fetch() async {
    final active = await ref.read(dealRepositoryProvider).listDeals(status: DealStatus.active);
    final soldOut = await ref.read(dealRepositoryProvider).listDeals(status: DealStatus.soldOut);
    return [...active, ...soldOut];
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(_fetch);
  }
}

/// Semua deal vendor tanpa filter
final allVendorDealsProvider = FutureProvider.autoDispose<List<Deal>>((ref) {
  return ref.read(dealRepositoryProvider).listDeals();
});

/// Filter segmen: Aktif / Habis / Dihapus.
final vendorDealFilterProvider = StateProvider<DealStatus?>((ref) => DealStatus.active);

final vendorDealsProvider =
    AsyncNotifierProvider<VendorDealsNotifier, List<Deal>>(VendorDealsNotifier.new);

class VendorDealsNotifier extends AsyncNotifier<List<Deal>> {
  @override
  Future<List<Deal>> build() async {
    final filter = ref.watch(vendorDealFilterProvider);
    return ref.read(dealRepositoryProvider).listDeals(status: filter);
  }

  Future<void> refresh() async {
    state = const AsyncLoading();
    state = await AsyncValue.guard(
      () => ref.read(dealRepositoryProvider).listDeals(status: ref.read(vendorDealFilterProvider)),
    );
  }

  Future<void> removeDeal(String dealId) async {
    await ref.read(dealRepositoryProvider).removeDeal(dealId);
    await refresh();
    ref.invalidate(consumerFeedProvider);
  }
}

/// Satu deal by id
final dealByIdProvider = FutureProvider.family<Deal?, String>((ref, id) async {
  final all = await ref.read(dealRepositoryProvider).listDeals();
  try {
    return all.firstWhere((d) => d.id == id);
  } catch (_) {
    return null;
  }
});

final claimsForDealProvider = FutureProvider.family<List<Claim>, String>((ref, dealId) async {
  return ref.read(dealRepositoryProvider).listClaimsForDeal(dealId);
});

/// Klaim milik konsumen
final myClaimsProvider = FutureProvider.autoDispose((ref) {
  return ref.read(dealRepositoryProvider).listClaimsForConsumer();
});

/// Hasil aksi "Klaim Sekarang"
class ClaimActionNotifier extends AsyncNotifier<void> {
  @override
  void build() {}

  Future<String?> claim(String dealId) async {
    state = const AsyncLoading();
    try {
      final claim = await ref.read(dealRepositoryProvider).claim(dealId);
      state = const AsyncData(null);
      ref.invalidate(consumerFeedProvider);
      return claim.code;
    } on ConflictException catch (e) {
      state = AsyncError(e, StackTrace.current);
      return null;
    }
  }
}

final claimActionProvider =
    AsyncNotifierProvider<ClaimActionNotifier, void>(ClaimActionNotifier.new);
