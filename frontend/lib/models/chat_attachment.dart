import 'dart:typed_data';

/// A local image attachment. Only bytes leave the device; [fileName] is used
/// for multipart metadata and is never a local path.
class ChatAttachment {
  const ChatAttachment({
    required this.fileName,
    required this.bytes,
    required this.mimeType,
  });

  final String fileName;
  final Uint8List bytes;
  final String mimeType;

  int get sizeInBytes => bytes.lengthInBytes;

  String get extension {
    final dot = fileName.lastIndexOf('.');
    return dot < 0 ? '' : fileName.substring(dot + 1).toLowerCase();
  }
}

class ChatAttachmentValidator {
  ChatAttachmentValidator._();

  static const maxBytes = 5 * 1024 * 1024;
  static const supportedExtensions = {'jpg', 'jpeg', 'png', 'webp'};
  static const supportedMimeTypes = {
    'image/jpeg',
    'image/png',
    'image/webp',
  };
  static const invalidMessage =
      'Gambar tidak valid atau terlalu besar. Pilih JPEG, PNG, atau WebP maksimal 5 MB.';

  static String? errorFor(ChatAttachment attachment) {
    if (attachment.bytes.isEmpty ||
        attachment.sizeInBytes > maxBytes ||
        !supportedExtensions.contains(attachment.extension) ||
        !supportedMimeTypes.contains(attachment.mimeType.toLowerCase())) {
      return invalidMessage;
    }
    final expectedMime = switch (attachment.extension) {
      'jpg' || 'jpeg' => 'image/jpeg',
      'png' => 'image/png',
      'webp' => 'image/webp',
      _ => null,
    };
    return expectedMime == attachment.mimeType.toLowerCase()
        ? null
        : invalidMessage;
  }
}
