import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import '../core/utils/currency_formatter.dart';

class _RupiahInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digits = newValue.text.replaceAll(RegExp(r'[^0-9]'), '');
    if (digits.isEmpty) {
      return const TextEditingValue(text: '');
    }
    final value = int.parse(digits);
    final formatted = CurrencyFormatter.formatDigitsOnly(value);
    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: formatted.length),
    );
  }
}

/// Field Rupiah — prefix `Rp` tetap di kiri, angka diformat otomatis
/// (`15000` -> `15.000`) sambil user mengetik.
class RupiahField extends StatelessWidget {
  const RupiahField({
    super.key,
    required this.controller,
    required this.label,
    this.hint,
    this.helperText,
    this.errorText,
    this.autofocus = false,
    this.onChanged,
  });

  final TextEditingController controller;
  final String label;
  final String? hint;
  final String? helperText;
  final String? errorText;
  final bool autofocus;
  final ValueChanged<int>? onChanged;

  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      autofocus: autofocus,
      keyboardType: TextInputType.number,
      inputFormatters: [_RupiahInputFormatter()],
      onChanged: (v) => onChanged?.call(CurrencyFormatter.parseDigits(v)),
      decoration: InputDecoration(
        prefixText: 'Rp',
        labelText: label,
        hintText: hint,
        helperText: helperText,
        helperMaxLines: 3,
        errorText: errorText,
      ),
    );
  }
}
