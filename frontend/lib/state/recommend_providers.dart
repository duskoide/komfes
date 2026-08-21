import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/deal.dart';
import '../models/recommendation.dart';
import '../services/app_exception.dart';
import 'repository_providers.dart';

/// Menampung draft input + hasil terakhir
class RecommendFlowState {
  const RecommendFlowState({
    this.draft,
    this.result,
    this.isLoading = false,
    this.error,
    this.lastPublishedDeal,
  });

  final ItemInputDraft? draft;
  final RecommendResult? result;
  final bool isLoading;
  final AppException? error;
  final Deal? lastPublishedDeal;

  RecommendFlowState copyWith({
    ItemInputDraft? draft,
    RecommendResult? result,
    bool? isLoading,
    AppException? error,
    bool clearError = false,
    Deal? lastPublishedDeal,
  }) {
    return RecommendFlowState(
      draft: draft ?? this.draft,
      result: result ?? this.result,
      isLoading: isLoading ?? this.isLoading,
      error: clearError ? null : (error ?? this.error),
      lastPublishedDeal: lastPublishedDeal ?? this.lastPublishedDeal,
    );
  }
}

class RecommendFlowNotifier extends StateNotifier<RecommendFlowState> {
  RecommendFlowNotifier(this._ref) : super(const RecommendFlowState());

  final Ref _ref;

  void setDraft(ItemInputDraft draft) {
    state = state.copyWith(draft: draft, clearError: true);
  }

  void reset() {
    state = const RecommendFlowState();
  }

  Future<void> submit(ItemInputDraft draft) async {
    state = state.copyWith(draft: draft, isLoading: true, clearError: true);
    try {
      final result = await _ref.read(recommendRepositoryProvider).recommend(draft);
      state = state.copyWith(result: result, isLoading: false, clearError: true);
    } on AppException catch (e) {
      state = state.copyWith(isLoading: false, error: e);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        error: const RequestFailedException(),
      );
      if (kDebugMode) print('recommend error: $e');
    }
  }

  void recordPublished(Deal deal) {
    state = state.copyWith(lastPublishedDeal: deal);
  }
}

final recommendFlowProvider =
    StateNotifierProvider<RecommendFlowNotifier, RecommendFlowState>(
  (ref) => RecommendFlowNotifier(ref),
);

bool isPriceBelowFloor({required int price, required int cost}) {
  return price < cost + 500;
}
