import 'package:flutter/material.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';

/// Bar aksi sticky di bawah layar — otomatis naik di atas keyboard, dan
/// menghormati safe area / gesture bar (min 16 dp, §2.1).
class StickyBottomBar extends StatelessWidget {
  const StickyBottomBar({
    super.key,
    required this.child,
    this.secondaryChild,
  });

  final Widget child;
  final Widget? secondaryChild;

  @override
  Widget build(BuildContext context) {
    final bottomInset = MediaQuery.viewInsetsOf(context).bottom;
    return Container(
      padding: EdgeInsets.fromLTRB(
        AppSpacing.lg,
        AppSpacing.md,
        AppSpacing.lg,
        AppSpacing.md + (bottomInset > 0 ? 0 : MediaQuery.paddingOf(context).bottom),
      ),
      decoration: const BoxDecoration(
        color: AppColors.surface,
        border: Border(top: BorderSide(color: AppColors.border)),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          child,
          if (secondaryChild != null) ...[
            const SizedBox(height: AppSpacing.sm),
            secondaryChild!,
          ],
        ],
      ),
    );
  }
}
