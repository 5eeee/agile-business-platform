import ru from './ru';
import ka from './ka';
import en from './en';
import ar from './ar';

export type Translations = typeof ru;

const translations: Record<string, Translations> = { ru, ka, en, ar };

export const RTL_LANGUAGES = ['ar'];

export function t(lang: string): Translations {
  return translations[lang] || translations.ru;
}

export { ru, ka, en, ar };
