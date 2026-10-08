import { useAuth } from './auth';
import { example } from './examples';
import { useI18n } from './i18n';

/** Placeholder examples in the interface language, for the company's own field. */
export function useExample() {
  const { user } = useAuth();
  const { lang } = useI18n();
  const industry = user?.org?.industry || 'general';
  return (field) => example(industry, lang, field);
}
