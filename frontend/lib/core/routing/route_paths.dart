class RoutePaths {
  RoutePaths._();

  static const splash = '/splash'; // S-01
  static const onboarding = '/onboarding'; // S-02
  static const role = '/role'; // S-03
  static const phone = '/phone'; // S-04
  static const otp = '/otp'; // S-05
  static const setupShop = '/setup-shop'; // S-06

  // Vendor shell (tab bar 4 item)
  static const vendorHome = '/vendor'; // V-01
  static const vendorDeals = '/vendor/deals'; // V-09
  static const vendorVerify = '/vendor/verify'; // V-11
  static const vendorProfile = '/vendor/profile'; // V-13

  // Vendor sub-halaman (push di atas shell)
  static const vendorChat = '/vendor/chat';
  static const vendorManualForm = '/vendor/manual-form'; // outage/accessibility fallback
  static const vendorManualConfirm = '/vendor/manual-form/confirm';
  static const vendorManualProcessing = '/vendor/manual-form/processing';
  static const vendorCheckItem = '/vendor/check-item'; // legacy alias
  static const vendorConfirm = '/vendor/check-item/confirm'; // legacy alias
  static const vendorProcessing = '/vendor/check-item/processing'; // legacy alias
  static const vendorResult = '/vendor/check-item/result'; // result screen
  static const vendorNoAction = '/vendor/check-item/no-action'; // V-06
  static const vendorWarning = '/vendor/check-item/warning'; // V-07
  static const vendorDealDetail = '/vendor/deals/:id'; // V-10
  static const vendorVerifyResult = '/vendor/verify/result'; // V-12
  static String vendorDealDetailPath(String id) => '/vendor/deals/$id';

  // Consumer shell (tab bar 3 item)
  static const consumerFeed = '/consumer'; // C-01
  static const consumerClaims = '/consumer/claims'; // C-04
  static const consumerProfile = '/consumer/profile'; // C-05

  // Consumer sub-halaman
  static const consumerDealDetail = '/consumer/deal/:id'; // C-02
  static const consumerClaimCode = '/consumer/claim/:code'; // C-03
  static String consumerDealDetailPath(String id) => '/consumer/deal/$id';
  static String consumerClaimCodePath(String code) => '/consumer/claim/$code';
}