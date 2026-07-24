"use client";

import { Check, Eye, EyeOff, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { ApiClientError, bootstrapOwner } from "@/lib/api/client";
import { type Locale, localizedPath } from "@/lib/i18n/routing";

type FieldErrors = Partial<
  Record<"login" | "password" | "confirmation", string>
>;

type Props = {
  locale: Locale;
  setupOwner?: typeof bootstrapOwner;
  onComplete?: () => void;
};

export function OwnerSetupForm({
  locale,
  setupOwner = bootstrapOwner,
  onComplete,
}: Props) {
  const t = useTranslations("auth.setup");
  const common = useTranslations("common");
  const errors = useTranslations("errors");
  const [preferredLocale, setPreferredLocale] = useState<Locale>(locale);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [apiError, setApiError] = useState<ApiClientError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [completed, setCompleted] = useState(false);
  const loginRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const confirmationRef = useRef<HTMLInputElement>(null);

  function validate(): FieldErrors {
    const next: FieldErrors = {};
    if (!login) {
      next.login = t("validation.loginRequired");
    } else if (!/^[a-z0-9._-]{3,128}$/.test(login)) {
      next.login = t("validation.loginInvalid");
    }
    if (!password) {
      next.password = t("validation.passwordRequired");
    } else if (password.length < 12) {
      next.password = t("validation.passwordShort");
    }
    if (!confirmation) {
      next.confirmation = t("validation.confirmationRequired");
    } else if (password !== confirmation) {
      next.confirmation = t("validation.passwordMismatch");
    }
    return next;
  }

  function focusFirstError(next: FieldErrors) {
    if (next.login) {
      loginRef.current?.focus();
    } else if (next.password) {
      passwordRef.current?.focus();
    } else if (next.confirmation) {
      confirmationRef.current?.focus();
    }
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const next = validate();
    setFieldErrors(next);
    setApiError(null);
    if (Object.keys(next).length > 0) {
      focusFirstError(next);
      return;
    }
    setSubmitting(true);
    try {
      await setupOwner({
        login_name: login,
        password,
        preferred_locale: preferredLocale,
      });
      setCompleted(true);
      if (onComplete) {
        onComplete();
      } else {
        window.location.assign(
          localizedPath(preferredLocale, "/agents/calculator-agent"),
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

  const apiMessage = apiError
    ? errors.has(apiError.code)
      ? errors(apiError.code)
      : errors("unknown")
    : null;

  return (
    <form className="formStack" noValidate onSubmit={submit}>
      {Object.keys(fieldErrors).length > 1 ? (
        <div className="errorSummary" role="alert">
          <ul>
            {Object.entries(fieldErrors).map(([field, message]) => (
              <li key={field}>
                <a href={`#setup-${field}`}>{message}</a>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="fieldGroup">
        <label htmlFor="setup-locale">{t("localeLabel")}</label>
        <select
          id="setup-locale"
          value={preferredLocale}
          onChange={(event) =>
            setPreferredLocale(event.target.value as Locale)
          }
        >
          <option value="ru-RU">{common("russian")}</option>
          <option value="en-US">{common("english")}</option>
        </select>
      </div>

      <div className="fieldGroup">
        <label htmlFor="setup-login">{t("loginLabel")}</label>
        <input
          ref={loginRef}
          id="setup-login"
          name="login"
          autoComplete="username"
          value={login}
          aria-describedby="setup-login-hint setup-login-error"
          aria-invalid={Boolean(fieldErrors.login)}
          onChange={(event) => setLogin(event.target.value)}
        />
        <p className="fieldHint" id="setup-login-hint">
          {t("loginHint")}
        </p>
        {fieldErrors.login ? (
          <p className="fieldError" id="setup-login-error" role="alert">
            {fieldErrors.login}
          </p>
        ) : null}
      </div>

      <div className="fieldGroup">
        <label htmlFor="setup-password">{t("passwordLabel")}</label>
        <div className="inputWithAction">
          <input
            ref={passwordRef}
            id="setup-password"
            name="password"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            value={password}
            aria-describedby="setup-password-hint setup-password-error"
            aria-invalid={Boolean(fieldErrors.password)}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button
            className="iconButton"
            type="button"
            aria-label={
              showPassword
                ? common("hidePassword")
                : common("showPassword")
            }
            onClick={() => setShowPassword((value) => !value)}
          >
            {showPassword ? <EyeOff aria-hidden /> : <Eye aria-hidden />}
          </button>
        </div>
        <p className="fieldHint" id="setup-password-hint">
          {t("passwordHint")}
        </p>
        {fieldErrors.password ? (
          <p className="fieldError" id="setup-password-error" role="alert">
            {fieldErrors.password}
          </p>
        ) : null}
      </div>

      <div className="fieldGroup">
        <label htmlFor="setup-confirmation">{t("confirmLabel")}</label>
        <input
          ref={confirmationRef}
          id="setup-confirmation"
          name="confirmation"
          type={showPassword ? "text" : "password"}
          autoComplete="new-password"
          value={confirmation}
          aria-describedby="setup-confirmation-error"
          aria-invalid={Boolean(fieldErrors.confirmation)}
          onChange={(event) => setConfirmation(event.target.value)}
        />
        {fieldErrors.confirmation ? (
          <p
            className="fieldError"
            id="setup-confirmation-error"
            role="alert"
          >
            {fieldErrors.confirmation}
          </p>
        ) : null}
      </div>

      {apiMessage ? (
        <div className="apiError" role="alert">
          <ShieldCheck aria-hidden />
          <span>{apiMessage}</span>
        </div>
      ) : null}
      {completed ? (
        <div className="successNotice" role="status">
          <Check aria-hidden />
          <span>{t("success")}</span>
        </div>
      ) : null}

      <button
        className="buttonPrimary"
        type="submit"
        disabled={submitting || completed}
      >
        {submitting ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
