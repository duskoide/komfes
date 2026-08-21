import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'dart:async';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../models/user.dart';
import '../../services/app_exception.dart';
import '../../state/repository_providers.dart';
import '../../state/session_providers.dart';
import '../../widgets/otp_input.dart';

class OtpVerifyScreen extends ConsumerStatefulWidget {
  const OtpVerifyScreen({
    super.key,
    required this.phone,
    this.extraContext = 'vendor',
    this.pendingDealId,
  });

  final String phone;
  final String extraContext;
  final String? pendingDealId;

  @override
  ConsumerState<OtpVerifyScreen> createState() => _OtpVerifyScreenState();
}

class _OtpVerifyScreenState extends ConsumerState<OtpVerifyScreen> {
  OtpInputState _state = OtpInputState.idle;
  String? _errorText;
  Timer? _timer;
  int _secondsLeft = 59;

  @override
  void initState() {
    super.initState();
    _startTimer();
  }

  void _startTimer() {
    _secondsLeft = 59;
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(seconds: 1), (t) {
      if (_secondsLeft <= 0) {
        t.cancel();
      } else {
        setState(() => _secondsLeft--);
      }
    });
  }

  Future<void> _resend() async {
    await ref.read(authRepositoryProvider).requestOtp(widget.phone);
    if (mounted) _startTimer();
  }

  Future<void> _handleCompleted(String otp) async {
    setState(() {
      _state = OtpInputState.verifying;
      _errorText = null;
    });
    try {
      final session = await ref.read(authRepositoryProvider).verifyOtp(widget.phone, otp);
      if (!mounted) return;
      ref.read(sessionProvider.notifier).setSession(session);
      _navigateAfterSuccess(session);
    } on OtpException catch (e) {
      setState(() {
        _state = OtpInputState.error;
        _errorText = e.message;
      });
    } catch (_) {
      setState(() {
        _state = OtpInputState.error;
        _errorText = 'Terjadi kesalahan. Coba lagi.';
      });
    }
  }

  void _navigateAfterSuccess(UserSession session) {
    if (widget.extraContext == 'claim') {
      // Kembali ke deal yang tadi (konteks asal)
      ref.read(activeRoleProvider.notifier).state = AppRole.consumer;
      final dealId = widget.pendingDealId;
      if (dealId != null) {
        context.go(RoutePaths.consumerDealDetailPath(dealId));
      } else {
        context.go(RoutePaths.consumerFeed);
      }
      return;
    }
    ref.read(activeRoleProvider.notifier).state = AppRole.vendor;
    if (session.isNewVendor) {
      context.go(RoutePaths.setupShop);
    } else {
      context.go(RoutePaths.vendorHome);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Masukkan Kode')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.xl),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 480),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Wrap(
                  children: [
                    Text(
                      'Kode dikirim ke ${widget.phone}. ',
                      style: AppTypography.body.copyWith(color: AppColors.textSecondary),
                    ),
                    GestureDetector(
                      onTap: () => context.pop(),
                      child: Text(
                        'Ubah nomor',
                        style: AppTypography.bodyStrong.copyWith(color: AppColors.primary),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.xxl),
                OtpInputWidget(
                  state: _state,
                  onChanged: (_) {
                    if (_state == OtpInputState.error) {
                      setState(() => _state = OtpInputState.idle);
                    } else if (_state == OtpInputState.idle) {
                      setState(() => _state = OtpInputState.typing);
                    }
                  },
                  onCompleted: _handleCompleted,
                ),
                if (_errorText != null) ...[
                  const SizedBox(height: AppSpacing.md),
                  Text(_errorText!, style: AppTypography.caption.copyWith(color: AppColors.error)),
                ],
                const SizedBox(height: AppSpacing.xl),
                if (_secondsLeft > 0)
                  Text(
                    'Kirim ulang kode dalam 00:${_secondsLeft.toString().padLeft(2, '0')}',
                    style: AppTypography.caption,
                  )
                else
                  TextButton(onPressed: _resend, child: const Text('Kirim Ulang Kode')),
                const SizedBox(height: AppSpacing.md),
                TextButton(
                  onPressed: () {
                    showModalBottomSheet(
                      context: context,
                      builder: (_) => Padding(
                        padding: const EdgeInsets.all(AppSpacing.xl),
                        child: Text(
                          'Pastikan nomor HP kamu benar dan sinyal stabil. '
                          'Kode dikirim lewat SMS atau WhatsApp, bisa makan waktu '
                          'sampai 1 menit. Kalau masih belum masuk, coba "Kirim Ulang Kode".',
                          style: AppTypography.body,
                        ),
                      ),
                    );
                  },
                  child: const Text('Tidak menerima kode?'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
