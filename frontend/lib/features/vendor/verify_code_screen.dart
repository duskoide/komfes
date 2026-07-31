import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../core/routing/route_paths.dart';
import '../../core/theme/app_colors.dart';
import '../../core/theme/app_spacing.dart';
import '../../core/theme/app_typography.dart';
import '../../state/verify_providers.dart';

class VerifyCodeScreen extends ConsumerStatefulWidget {
  const VerifyCodeScreen({super.key});

  @override
  ConsumerState<VerifyCodeScreen> createState() => _VerifyCodeScreenState();
}

class _VerifyCodeScreenState extends ConsumerState<VerifyCodeScreen> {
  final _controller = TextEditingController(text: 'HT-');

  @override
  void initState() {
    super.initState();
    _controller.selection = TextSelection.collapsed(offset: _controller.text.length);
  }

  Future<void> _verify() async {
    final code = _controller.text.trim();
    if (code.replaceAll('HT-', '').isEmpty) return;
    await ref.read(verifyProvider.notifier).verify(code);
    if (!mounted) return;
    context.push(RoutePaths.vendorVerifyResult);
  }

  @override
  Widget build(BuildContext context) {
    final pendingAsync = ref.watch(pendingClaimsProvider);
    final verifyState = ref.watch(verifyProvider);
    final isLoading = verifyState.isLoading;

    return Scaffold(
      appBar: AppBar(automaticallyImplyLeading: false, title: const Text('Verifikasi Kode')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(AppSpacing.xl),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Minta pembeli tunjukkan kodenya, lalu masukkan di sini.',
              style: AppTypography.body.copyWith(color: AppColors.textSecondary),
            ),
            const SizedBox(height: AppSpacing.xl),
            TextField(
              controller: _controller,
              autofocus: true,
              textCapitalization: TextCapitalization.characters,
              style: AppTypography.codeDisplay.copyWith(fontSize: 28),
              textAlign: TextAlign.center,
              inputFormatters: [
                FilteringTextInputFormatter.allow(RegExp(r'[A-Za-z0-9\-]')),
              ],
              decoration: const InputDecoration(hintText: 'HT-XXXX'),
              onSubmitted: (_) => _verify(),
            ),
            const SizedBox(height: AppSpacing.lg),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: isLoading ? null : _verify,
                child: isLoading
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                      )
                    : const Text('Verifikasi'),
              ),
            ),
            const SizedBox(height: AppSpacing.xxl),
            Text('Menunggu diambil', style: AppTypography.h3),
            const SizedBox(height: AppSpacing.sm),
            pendingAsync.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (e, st) => const Text('Gagal memuat daftar.'),
              data: (claims) {
                if (claims.isEmpty) {
                  return Text('Belum ada klaim menunggu.', style: AppTypography.caption);
                }
                return Column(
                  children: [
                    for (final c in claims)
                      Card(
                        margin: const EdgeInsets.only(bottom: AppSpacing.sm),
                        child: ListTile(
                          leading: const Icon(Icons.confirmation_number_outlined),
                          title: Text(c.code, style: AppTypography.bodyStrong),
                          subtitle: Text(c.itemName ?? ''),
                          onTap: () {
                            _controller.text = c.code;
                            _verify();
                          },
                        ),
                      ),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }
}
