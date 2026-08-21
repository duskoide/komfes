import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/theme/app_colors.dart';
import '../core/theme/app_spacing.dart';
import '../core/theme/app_typography.dart';

enum OtpInputState { idle, typing, verifying, error }

/// Input OTP 6 digit — kotak terpisah, autofocus kotak pertama, auto-submit
/// begitu kotak ke-6 terisi, mendukung paste 6 digit sekaligus (SMS autofill
/// Android biasa mem-paste ke satu field), dan getar halus saat salah.
class OtpInputWidget extends StatefulWidget {
  const OtpInputWidget({
    super.key,
    required this.state,
    required this.onCompleted,
    this.onChanged,
  });

  final OtpInputState state;
  final ValueChanged<String> onCompleted;
  final ValueChanged<String>? onChanged;

  @override
  State<OtpInputWidget> createState() => OtpInputWidgetState();
}

class OtpInputWidgetState extends State<OtpInputWidget>
    with SingleTickerProviderStateMixin {
  final List<TextEditingController> _controllers =
      List.generate(6, (_) => TextEditingController());
  final List<FocusNode> _nodes = List.generate(6, (_) => FocusNode());
  late AnimationController _shakeController;

  @override
  void initState() {
    super.initState();
    _shakeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 380),
    );
  }

  @override
  void didUpdateWidget(covariant OtpInputWidget oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.state == OtpInputState.error && oldWidget.state != OtpInputState.error) {
      _shakeController.forward(from: 0);
      Future.microtask(clearAndRefocus);
    }
  }

  void clearAndRefocus() {
    for (final c in _controllers) {
      c.clear();
    }
    if (mounted) {
      FocusScope.of(context).requestFocus(_nodes.first);
    }
  }

  String get _value => _controllers.map((c) => c.text).join();

  void _handleChanged(int index, String value) {
    if (value.length > 1) {
      // Paste 6 digit sekaligus.
      final digits = value.replaceAll(RegExp(r'[^0-9]'), '');
      for (var i = 0; i < 6; i++) {
        _controllers[i].text = i < digits.length ? digits[i] : '';
      }
      if (digits.length >= 6) {
        _nodes.last.unfocus();
        widget.onCompleted(_value);
      } else if (digits.isNotEmpty) {
        _nodes[digits.length.clamp(0, 5)].requestFocus();
      }
      widget.onChanged?.call(_value);
      setState(() {});
      return;
    }

    if (value.isNotEmpty && index < 5) {
      _nodes[index + 1].requestFocus();
    }
    widget.onChanged?.call(_value);
    setState(() {});

    if (_value.length == 6) {
      FocusScope.of(context).unfocus();
      widget.onCompleted(_value);
    }
  }

  void _handleBackspace(int index) {
    if (_controllers[index].text.isEmpty && index > 0) {
      _nodes[index - 1].requestFocus();
      _controllers[index - 1].clear();
      setState(() {});
    }
  }

  @override
  void dispose() {
    for (final c in _controllers) {
      c.dispose();
    }
    for (final n in _nodes) {
      n.dispose();
    }
    _shakeController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isError = widget.state == OtpInputState.error;
    final isLocked = widget.state == OtpInputState.verifying;

    return AnimatedBuilder(
      animation: _shakeController,
      builder: (context, child) {
        final t = _shakeController.value;
        final dx = (t == 0) ? 0.0 : (16 * (1 - t)) * ((t * 12).floor().isEven ? 1 : -1);
        return Transform.translate(offset: Offset(dx, 0), child: child);
      },
      child: AutofillGroup(
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: List.generate(6, (i) {
            return SizedBox(
              width: 44,
              height: 56,
              child: Stack(
                alignment: Alignment.center,
                children: [
                  Focus(
                    onKeyEvent: (node, event) {
                      if (event is KeyDownEvent &&
                          event.logicalKey == LogicalKeyboardKey.backspace &&
                          _controllers[i].text.isEmpty) {
                        _handleBackspace(i);
                        return KeyEventResult.handled;
                      }
                      return KeyEventResult.ignored;
                    },
                    child: TextField(
                    controller: _controllers[i],
                    focusNode: _nodes[i],
                    enabled: !isLocked,
                    autofocus: i == 0,
                    textAlign: TextAlign.center,
                    keyboardType: TextInputType.number,
                    maxLength: i == 0 ? 6 : 1,
                    autofillHints: i == 0 ? const [AutofillHints.oneTimeCode] : null,
                    style: AppTypography.h1,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    decoration: InputDecoration(
                      counterText: '',
                      contentPadding: EdgeInsets.zero,
                      filled: true,
                      fillColor: isLocked ? AppColors.surfaceAlt : AppColors.surface,
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                        borderSide: BorderSide(
                          color: isError ? AppColors.error : AppColors.border,
                          width: isError ? 1.8 : 1,
                        ),
                      ),
                      focusedBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                        borderSide: BorderSide(
                          color: isError ? AppColors.error : AppColors.primary,
                          width: 1.8,
                        ),
                      ),
                      enabledBorder: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(AppSpacing.radiusMd),
                        borderSide: BorderSide(
                          color: isError ? AppColors.error : AppColors.border,
                        ),
                      ),
                    ),
                    onChanged: (v) => _handleChanged(i, v),
                    onTap: () {
                      _controllers[i].selection = TextSelection(
                        baseOffset: 0,
                        extentOffset: _controllers[i].text.length,
                      );
                    },
                    onSubmitted: (_) {},
                    ),
                  ),
                  if (isLocked && i == 0)
                    const Positioned(
                      child: SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      ),
                    ),
                ],
              ),
            );
          }).map((w) {
            return Expanded(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 3), child: w));
          }).toList(),
        ),
      ),
    );
  }
}
