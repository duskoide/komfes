import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/deal.dart';
import '../services/app_exception.dart';
import 'repository_providers.dart';

enum VerifyOutcomeKind { berhasil, sudahDipakai, tidakDitemukan, dealDihapus }

class VerifyOutcome {
  const VerifyOutcome({required this.kind, this.claim, this.message});
  final VerifyOutcomeKind kind;
  final Claim? claim;
  final String? message;
}

class VerifyNotifier extends StateNotifier<AsyncValue<VerifyOutcome?>> {
  VerifyNotifier(this._ref) : super(const AsyncData(null));
  final Ref _ref;

  Future<void> verify(String rawCode) async {
    state = const AsyncLoading();
    final code = _normalize(rawCode);
    try {
      final claim = await _ref.read(dealRepositoryProvider).redeem(code);
      state = AsyncData(VerifyOutcome(kind: VerifyOutcomeKind.berhasil, claim: claim));
    } on NotFoundException {
      state = const AsyncData(
        VerifyOutcome(kind: VerifyOutcomeKind.tidakDitemukan),
      );
    } on ConflictException catch (e) {
      final isRemoved = e.message.toLowerCase().contains('dihapus');
      state = AsyncData(
        VerifyOutcome(
          kind: isRemoved ? VerifyOutcomeKind.dealDihapus : VerifyOutcomeKind.sudahDipakai,
          message: e.message,
        ),
      );
    } catch (e) {
      state = AsyncError(e, StackTrace.current);
    }
  }

  void resetToIdle() => state = const AsyncData(null);

  String _normalize(String raw) {
    var v = raw.trim().toUpperCase().replaceAll(' ', '');
    if (!v.startsWith('HT-')) {
      v = v.replaceAll('HT-', '').replaceAll('HT', '');
      v = 'HT-$v';
    }
    return v;
  }
}

final verifyProvider = StateNotifierProvider<VerifyNotifier, AsyncValue<VerifyOutcome?>>(
  (ref) => VerifyNotifier(ref),
);

/// Klaim belum diambil milik semua deal vendor
final pendingClaimsProvider = FutureProvider.autoDispose<List<Claim>>((ref) async {
  final repo = ref.read(dealRepositoryProvider);
  final deals = await repo.listDeals();
  final result = <Claim>[];
  for (final d in deals) {
    final claims = await repo.listClaimsForDeal(d.id);
    result.addAll(claims.where((c) => c.status.name == 'claimed'));
  }
  return result;
});
