"use client";

import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { ApiClientError, loginOwner } from "@/lib/api/client";
import { type Locale, localizedPath } from "@/lib/i18n/routing";

type Props = {
  locale: Locale;
  login?: typeof loginOwner;
  onComplete?: () => void;
};

export function LoginForm({locale, login = loginOwner, onComplete}: Props) {
  const t = useTranslations("auth.login");
  const errors = useTranslations("errors");
  const [loginName, setLoginName] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fieldError, setFieldError] = useState<"login" | "password" | null>(
    null,
  );
  const [apiError, setApiError] = useState<ApiClientError | null>(null);
  const loginRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!loginName) {
      setFieldError("login");
      loginRef.current?.focus();
      return;
    }
    if (!password) {
      setFieldError("password");
      passwordRef.current?.focus();
      return;
    }
    setFieldError(null);
    setApiError(null);
    setSubmitting(true);
    try {
      await login({login_name: loginName, password});
      if (onComplete) {
        onComplete();
      } else {
        window.location.assign(
          localizedPath(locale, "/agents/calculator-agent"),
        );
      }
    } catch (error) {
      setApiError(
        error instanceof ApiClientError
          ? error
          : new ApiClientError("unknown", null, false),
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="formStack" noValidate onSubmit={submit}>
      <div className="fieldGroup">
        <label htmlFor="login-name">{t("loginLabel")}</label>
        <input
          ref={loginRef}
          id="login-name"
          autoComplete="username"
          value={loginName}
          aria-invalid={fieldError === "login"}
          onChange={(event) => setLoginName(event.target.value)}
        />
        {fieldError === "login" ? (
          <p className="fieldError" role="alert">
            {t("validation.loginRequired")}
          </p>
        ) : null}
      </div>
      <div className="fieldGroup">
        <label htmlFor="login-password">{t("passwordLabel")}</label>
        <input
          ref={passwordRef}
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          aria-invalid={fieldError === "password"}
          onChange={(event) => setPassword(event.target.value)}
        />
        {fieldError === "password" ? (
          <p className="fieldError" role="alert">
            {t("validation.passwordRequired")}
          </p>
        ) : null}
      </div>
      {apiError ? (
        <p className="apiError" role="alert">
          {errors.has(apiError.code)
            ? errors(apiError.code)
            : errors("unknown")}
        </p>
      ) : null}
      <button className="buttonPrimary" type="submit" disabled={submitting}>
        {submitting ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
