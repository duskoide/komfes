import '../models/recommendation.dart';

sealed class AppException implements Exception {
  const AppException(this.message);
  final String message;
}

/// Tidak ada koneksi internet sama sekali
class NetworkOfflineException extends AppException {
  const NetworkOfflineException() : super('Tidak ada koneksi. Menampilkan data terakhir.');
}

/// Request gagal karena masalah server/jaringan lain
class RequestFailedException extends AppException {
  const RequestFailedException([super.message = 'Terjadi kesalahan. Coba lagi.']);
}

/// `502 model_unavailable`
class ModelUnavailableException extends AppException {
  const ModelUnavailableException([
    super.message = 'Sistem AI sedang tidak tersedia. Coba lagi sebentar.',
  ]);
}

/// `422 needs_confirmation` — bukan error sesungguhnya, tapi alur normal;
/// dibawa sebagai exception supaya pemanggil (state layer) tetap bisa pakai
/// try-catch yang sama dengan kasus lain lalu redirect ke V-03.
class NeedsConfirmationException extends AppException {
  const NeedsConfirmationException(this.result) : super('needs_confirmation');
  final RecommendResult result;
}

/// `422 invalid_input`
class InvalidInputException extends AppException {
  const InvalidInputException(super.message);
}

/// `409` — stok habis / kode sudah dipakai / deal tidak tersedia
class ConflictException extends AppException {
  const ConflictException(super.message);
}

/// `404` — kode klaim tidak ditemukan
class NotFoundException extends AppException {
  const NotFoundException([super.message = 'Kode tidak ditemukan. Cek lagi hurufnya.']);
}

/// `404` dari `/api/chat` — sesi konsultasi sudah tidak dikenal server.
/// UI harus memulai sesi baru dan mengatakannya, bukan diam-diam gagal.
class SessionExpiredException extends AppException {
  const SessionExpiredException([
    super.message = 'Sesi konsultasi sudah berakhir. Mulai lagi dari awal, ya.',
  ]);
}

/// OTP salah / kadaluarsa / terlalu banyak percobaan
class OtpException extends AppException {
  const OtpException(super.message);
}
