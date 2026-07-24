# Localization and internationalization

## 1. Initial locales

- `ru-RU`
- `en-US`

## 2. Separate concepts

The product must not conflate:

- UI locale;
- conversation language;
- output language;
- document locale/jurisdiction;
- timezone;
- number/date/currency formats.

## 3. UI rules

- all strings use translation keys;
- ICU-compatible pluralization;
- locale-aware formatting;
- no concatenated sentence fragments;
- no layout assumptions based on English string length;
- test long Russian strings;
- support reduced motion and accessibility labels in each locale.

## 4. Agent assets

Prompts and skills may have:

- shared language-neutral metadata;
- locale-specific instructions;
- locale-specific examples;
- separate eval results.

Example:

```text
prompts/
├── system.ru-RU.md
└── system.en-US.md
```

Machine translation does not automatically make an asset Verified.

## 5. API

API field names remain stable and language-neutral. User-visible labels are localized separately.

## 6. Testing

- snapshot/visual tests for both locales;
- pluralization;
- dates and currencies;
- fallback behavior;
- mixed-language input;
- output-language enforcement;
- missing translation detection in CI.
