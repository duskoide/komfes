import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../core/utils/validators.dart';
import '../../state/repository_providers.dart';
import '../../state/session_providers.dart';

class PhoneInputScreen extends ConsumerStatefulWidget {
  const PhoneInputScreen({
    super.key,
    this.extraContext = 'vendor',
    this.pendingDealId,
  });

  final String extraContext;
  final String? pendingDealId;

  @override
  ConsumerState<PhoneInputScreen> createState() => _PhoneInputScreenState();
}

class _PhoneInputScreenState extends ConsumerState<PhoneInputScreen> {
  final _controller = TextEditingController();
  bool _submitting = false;
  bool _touched = false;

  String get _digits => Validators.normalizePhoneLocal(_controller.text);
  bool get _isValid => Validators.isPhoneValid(_digits);

  Future<void> _submit() async {
    if (!_isValid) return;
    setState(() => _submitting = true);
    final fullPhone = '+62$_digits';
    try {
      await ref.read(authRepositoryProvider).requestOtp(fullPhone);
      if (!mounted) return;
      if (widget.pendingDealId != null) {
        ref.read(pendingClaimDealIdProvider.notifier).state = widget.pendingDealId;
      }
      context.push(
        RoutePaths.otp,
        extra: {'phone': fullPhone, 'context': widget.extraContext, 'dealId': widget.pendingDealId},
      );
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isClaimContext = widget.extraContext == 'claim';

    return Scaffold(
      appBar: AppBar(title: const Text('Masuk atau Daftar')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (isClaimContext) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(AppSpacing.md),
                    decoration: BoxDecoration(
                      color: AppColors.primaryLight,
                      borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                    ),
                    child: Text(
                      'Masuk dulu untuk klaim deal ini',
                      style: AppTypography.bodyStrong.copyWith(color: AppColors.primaryDark),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.lg),
                ],
                Text(
                  'Kami kirim kode verifikasi ke WhatsApp/SMS kamu.',
                  style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                ),
                const SizedBox(height: AppSpacing.xl),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      height: 56,
                      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.lg),
                      decoration: BoxDecoration(
                        color: AppColors.surfaceAlt,
                        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                        border: Border.all(color: AppColors.border),
                      ),
                      alignment: Alignment.center,
                      child: const Text('+62', style: AppTypography.bodyStrong),
                    ),
                    const SizedBox(width: AppSpacing.sm),
                    Expanded(
                      child: TextField(
                        controller: _controller,
                        autofocus: true,
                        keyboardType: TextInputType.number,
                        inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                        onChanged: (_) => setState(() {}),
                        onTapOutside: (_) => setState(() => _touched = true),
                        decoration: InputDecoration(
                          hintText: '812xxxxxxx',
                          errorText: _touched && _controller.text.isNotEmpty && !_isValid
                              ? 'Nomor HP tidak valid'
                              : null,
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xl),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _isValid && !_submitting ? _submit : null,
                    child: _submitting
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Text('Kirim Kode'),
                  ),
                ),
                const SizedBox(height: AppSpacing.lg),
                Text(
                  'Dengan melanjutkan, kamu menyetujui Syarat & Ketentuan serta '
                  'Kebijakan Privasi HargaTurun.',
                  style: AppTypography.caption,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
