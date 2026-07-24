import {getRequestConfig} from "next-intl/server";

import {getMessages, isLocale} from "@/lib/i18n/routing";

export default getRequestConfig(async ({requestLocale}) => {
  const requested = await requestLocale;
  const locale = requested && isLocale(requested) ? requested : "ru-RU";

  return {
    locale,
    messages: getMessages(locale),
  };
});
