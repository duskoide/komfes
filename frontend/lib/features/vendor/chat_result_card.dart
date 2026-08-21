import 'package:flutter/material.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/currency_formatter.dart';
import '../../models/enums.dart';
import '../../models/recommendation.dart';
import '../../widgets/ai_explanation_card.dart';

/// Hasil konsultasi, ditampilkan langsung di dalam percakapan.
///
/// Tidak ada satu pun angka yang dihitung di sini — semuanya diambil apa
/// adanya dari hasil tool pricing. Tidak ada aksi publikasi, sesuai SRS
/// Penyisihan yang melarang publishing di babak ini.
class ChatResultCard extends StatelessWidget {
  const ChatResultCard({super.key, required this.result});

  final RecommendResult result;

  @override
  Widget build(BuildContext context) {
    return switch (result.status) {
      RecommendResultStatus.recommendation => _Recommendation(result: result),
      RecommendResultStatus.noAction => _NoAction(result: result),
      RecommendResultStatus.invalidInput => _Warning(
          message: result.message ?? 'Ada data yang perlu diperiksa lagi.',
        ),
      RecommendResultStatus.modelUnavailable => _Warning(
          message: result.message ?? 'Sistem AI sedang tidak tersedia.',
        ),
      // needs_confirmation tidak dirender sebagai hasil: orchestrator
      // menanganinya lewat action SHOW_CONFIRMATION.
      RecommendResultStatus.needsConfirmation => const SizedBox.shrink(),
    };
  }
}

class _Shell extends StatelessWidget {
  const _Shell({required this.child, required this.borderColor});

  final Widget child;
  final Color borderColor;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.only(bottom: AppSpacing.md),
      padding: const EdgeInsets.all(AppSpacing.lg),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppSpacing.radiusLg),
        border: Border.all(color: borderColor, width: 1.4),
      ),
      child: child,
    );
  }
}

class _Recommendation extends StatelessWidget {
  const _Recommendation({required this.result});

  final RecommendResult result;

  @override
  Widget build(BuildContext context) {
    final rec = result.recommendation;
    final input = result.normalizedInput;
    if (rec == null) return const SizedBox.shrink();

    return _Shell(
      borderColor: AppColors.primary,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Harga rekomendasi adalah elemen terbesar, diskon jadi badge,
          // harga asli dicoret — hierarki yang sama dengan V-05.
          Text(
            CurrencyFormatter.format(rec.recommendedPrice),
            style: AppTypography.displayNumber,
          ),
          const SizedBox(height: AppSpacing.sm),
          Wrap(
            crossAxisAlignment: WrapCrossAlignment.center,
            spacing: AppSpacing.sm,
            runSpacing: AppSpacing.xs,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: AppSpacing.md,
                  vertical: AppSpacing.xs,
                ),
                decoration: BoxDecoration(
                  color: AppColors.primaryLight,
                  borderRadius: BorderRadius.circular(AppSpacing.radiusPill),
                ),
                child: Text(
                  'Diskon ${rec.discountPercent}%',
                  style: AppTypography.bodyStrong.copyWith(
                    color: AppColors.primary,
                  ),
                ),
              ),
              if (input?.originalPrice != null) ...[
                const Text('harga asli', style: AppTypography.caption),
                Text(
                  CurrencyFormatter.format(input!.originalPrice!),
                  style: AppTypography.strikethrough,
                ),
              ],
            ],
          ),
          const SizedBox(height: AppSpacing.lg),
          _Line(icon: Icons.schedule_rounded, text: rec.timing),
          const SizedBox(height: AppSpacing.xs),
          _Line(
            icon: Icons.sell_outlined,
            text: 'Perkiraan terjual ${rec.expectedSellThrough} — '
                'pemasukan ${CurrencyFormatter.format(rec.expectedRevenue)}',
          ),
          const SizedBox(height: AppSpacing.xs),
          _Line(
            icon: Icons.trending_down_rounded,
            color: AppColors.kritis,
            text: 'Kalau dibiarkan, potensi rugi '
                '${CurrencyFormatter.format(rec.expectedLossNoAction)}',
          ),
          if ((result.explanation ?? '').trim().isNotEmpty) ...[
            const SizedBox(height: AppSpacing.lg),
            AiExplanationCard(text: result.explanation!.trim()),
          ],
          if ((result.promoCopy ?? '').trim().isNotEmpty) ...[
            const SizedBox(height: AppSpacing.lg),
            const Text('Teks promo siap pakai', style: AppTypography.label),
            const SizedBox(height: AppSpacing.xs),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.surfaceAlt,
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              ),
              child: Text(result.promoCopy!.trim(), style: AppTypography.body),
            ),
          ],
          const SizedBox(height: AppSpacing.md),
          Row(
            children: [
              const Icon(Icons.verified_outlined,
                  size: 15, color: AppColors.textSecondary),
              const SizedBox(width: AppSpacing.xs),
              Text('Prediksi ${rec.confidence}', style: AppTypography.caption),
            ],
          ),
        ],
      ),
    );
  }
}

class _NoAction extends StatelessWidget {
  const _NoAction({required this.result});

  final RecommendResult result;

  @override
  Widget build(BuildContext context) {
    // Nada tenang, bukan error: tidak mendiskon adalah jawaban yang benar
    // dan vendor menghemat margin.
    return _Shell(
      borderColor: AppColors.aman,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.check_circle_outline, color: AppColors.aman),
              SizedBox(width: AppSpacing.sm),
              Text('Belum perlu diskon', style: AppTypography.h3),
            ],
          ),
          const SizedBox(height: AppSpacing.sm),
          Text(
            result.message ??
                'Barang ini kemungkinan terjual normal sebelum kadaluarsa.',
            style: AppTypography.body.copyWith(color: AppColors.textSecondary),
          ),
          if (result.reassessInDays != null) ...[
            const SizedBox(height: AppSpacing.md),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(AppSpacing.md),
              decoration: BoxDecoration(
                color: AppColors.amanBg,
                borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
              ),
              child: Text(
                'Cek lagi dalam ${result.reassessInDays} hari.',
                style: AppTypography.bodyStrong.copyWith(color: AppColors.aman),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Warning extends StatelessWidget {
  const _Warning({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    // Tidak ada angka diskon apa pun yang ditampilkan di jalur ini.
    return _Shell(
      borderColor: AppColors.kritis,
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Icon(Icons.error_outline, color: AppColors.kritis),
          const SizedBox(width: AppSpacing.sm),
          Expanded(
            child: Text(
              message,
              style: AppTypography.body.copyWith(color: AppColors.kritis),
            ),
          ),
        ],
      ),
    );
  }
}

class _Line extends StatelessWidget {
  const _Line({required this.icon, required this.text, this.color});

  final IconData icon;
  final String text;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, size: 16, color: color ?? AppColors.textSecondary),
        const SizedBox(width: AppSpacing.sm),
        Expanded(
          child: Text(
            text,
            style: AppTypography.body.copyWith(color: color),
          ),
        ),
      ],
    );
  }
}
