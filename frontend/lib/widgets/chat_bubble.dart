import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';
import '../state/chat_providers.dart';

/// Satu gelembung percakapan.
///
/// Pesan sistem dibedakan tegas dari pesan asisten supaya pemberitahuan
/// klien (misal sesi berakhir) tidak terbaca seolah model yang bicara.
class ChatBubble extends StatelessWidget {
  const ChatBubble({super.key, required this.message});

  final ChatMessage message;

  @override
  Widget build(BuildContext context) {
    if (message.author == ChatAuthor.system) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: AppSpacing.sm),
        child: Center(
          child: Text(
            message.text,
            textAlign: TextAlign.center,
            style: AppTypography.caption,
          ),
        ),
      );
    }

    final isVendor = message.author == ChatAuthor.vendor;

    return Align(
      alignment: isVendor ? Alignment.centerRight : Alignment.centerLeft,
      child: Padding(
        padding: const EdgeInsets.only(bottom: AppSpacing.md),
        child: Opacity(
          // Pesan yang belum sampai server ditampilkan lebih redup, bukan
          // disembunyikan — vendor tetap melihat apa yang dia kirim.
          opacity: message.isPending ? 0.55 : 1,
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.sizeOf(context).width * 0.82,
            ),
            child: Container(
              padding: const EdgeInsets.symmetric(
                horizontal: AppSpacing.lg,
                vertical: AppSpacing.md,
              ),
              decoration: BoxDecoration(
                color: isVendor ? AppColors.primary : AppColors.surface,
                border: isVendor ? null : Border.all(color: AppColors.border),
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(AppSpacing.radiusLg),
                  topRight: const Radius.circular(AppSpacing.radiusLg),
                  bottomLeft: Radius.circular(
                    isVendor ? AppSpacing.radiusLg : AppSpacing.radiusSm,
                  ),
                  bottomRight: Radius.circular(
                    isVendor ? AppSpacing.radiusSm : AppSpacing.radiusLg,
                  ),
                ),
              ),
              child: Text(
                message.text,
                style: AppTypography.body.copyWith(
                  color: isVendor ? Colors.white : AppColors.textPrimary,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
