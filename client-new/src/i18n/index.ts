import ru from './ru';
import ka from './ka';
import en from './en';

export type Translations = typeof ru;

const translations: Record<string, Translations> = { ru, ka, en };

export function t(lang: string): Translations {
  return translations[lang] || translations.ru;
}

export { ru, ka, en };
