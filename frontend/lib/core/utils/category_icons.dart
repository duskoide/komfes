import '../../models/enums.dart';

String categoryEmoji(ItemCategory category) {
  switch (category) {
    case ItemCategory.bakery:
      return '🍞';
    case ItemCategory.makananSiapSaji:
      return '🍱';
    case ItemCategory.susuOlahan:
      return '🥛';
    case ItemCategory.minuman:
      return '🥤';
    case ItemCategory.sayurBuah:
      return '🥬';
    case ItemCategory.snack:
      return '🍪';
    case ItemCategory.kalengan:
      return '🥫';
    case ItemCategory.lainnya:
      return '🛍️';
  }
}
