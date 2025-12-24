// src/i18n.ts
import { createI18n } from 'vue-i18n';  // Правильно: vue-i18n (с цифрой 1)
import en from './locales/en.json';
import ru from './locales/ru.json';

const i18n = createI18n({
  legacy: false,
  locale: 'en',
  fallbackLocale: 'en',
  messages: { en, ru }
});

export default i18n;
