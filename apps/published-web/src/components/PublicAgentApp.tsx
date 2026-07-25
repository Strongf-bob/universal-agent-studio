"use client";

import type {
  InputField,
  PublicAgentView,
  PublicRunEvent,
  PublicRunView,
} from "@universal-agent-studio/contracts";
import {FormEvent, useEffect, useMemo, useRef, useState} from "react";

import {
  createPublicTransport,
} from "@/lib/api";
import type {PublicAgentTransport as PublicAgentTransportPort} from "@/lib/api";
import {
  alternateLocale,
  getMessages,
  type Locale,
} from "@/lib/i18n";

type RunState = "ready" | "submitting" | "running" | "completed" | "failed";
type FieldValue = string | boolean;
export type PublicAgentTransport = PublicAgentTransportPort;

interface PublicAgentAppProps {
  agent: PublicAgentView;
  locale: Locale;
  transport?: PublicAgentTransport;
}

function fieldType(field: InputField): string {
  return typeof field.schema.type === "string" ? field.schema.type : "string";
}

function numberAttribute(
  field: InputField,
  key: "minimum" | "maximum",
): number | undefined {
  const value = field.schema[key];
  return typeof value === "number" ? value : undefined;
}

function enumValues(field: InputField): string[] {
  const value = field.schema.enum;
  return Array.isArray(value) && value.every((item) => typeof item === "string")
    ? value
    : [];
}

function initialValues(agent: PublicAgentView): Record<string, FieldValue> {
  return Object.fromEntries(
    agent.interface.input_fields.map((field) => [
      field.id,
      fieldType(field) === "boolean" ? false : "",
    ]),
  );
}

function submissionInput(
  fields: InputField[],
  values: Record<string, FieldValue>,
): Record<string, unknown> {
  const input: Record<string, unknown> = {};
  for (const field of fields) {
    const value = values[field.id];
    const type = fieldType(field);
    if (!field.required && value === "") {
      continue;
    }
    input[field.id] =
      type === "number" || type === "integer" ? Number(value) : value;
  }
  return input;
}

function resultText(output: Record<string, unknown> | null): string {
  if (!output) {
    return "";
  }
  const values = Object.values(output);
  if (values.length === 1 && ["string", "number", "boolean"].includes(typeof values[0])) {
    return String(values[0]);
  }
  return JSON.stringify(output, null, 2);
}

export function PublicAgentApp({
  agent,
  locale,
  transport: injectedTransport,
}: PublicAgentAppProps) {
  const messages = getMessages(locale);
  const transport = useMemo(
    () => injectedTransport ?? createPublicTransport(agent.agent_id, locale),
    [agent.agent_id, injectedTransport, locale],
  );
  const [values, setValues] = useState(() => initialValues(agent));
  const [state, setState] = useState<RunState>("ready");
  const [output, setOutput] = useState<Record<string, unknown> | null>(null);
  const capabilityRef = useRef<string | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const lastSequenceRef = useRef(0);

  useEffect(() => {
    const previous = document.documentElement.lang;
    document.documentElement.lang = locale;
    return () => {
      document.documentElement.lang = previous;
    };
  }, [locale]);

  useEffect(
    () => () => {
      controllerRef.current?.abort();
      capabilityRef.current = null;
    },
    [],
  );

  const completeFromRun = (run: PublicRunView) => {
    if (run.status === "completed") {
      setOutput(run.output);
      setState("completed");
      capabilityRef.current = null;
      return true;
    }
    if (run.status === "failed" || run.status === "cancelled") {
      setState("failed");
      capabilityRef.current = null;
      return true;
    }
    return false;
  };

  const handleEvent = (event: PublicRunEvent) => {
    lastSequenceRef.current = Math.max(lastSequenceRef.current, event.sequence);
    if (event.status === "completed") {
      setOutput(event.output);
      setState("completed");
      capabilityRef.current = null;
    } else if (event.status === "failed" || event.status === "cancelled") {
      setState("failed");
      capabilityRef.current = null;
    } else {
      setState("running");
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    capabilityRef.current = null;
    lastSequenceRef.current = 0;
    setOutput(null);
    setState("submitting");

    try {
      const run = await transport.create(
        submissionInput(agent.interface.input_fields, values),
      );
      if (completeFromRun(run)) {
        return;
      }
      if (!run.run_capability) {
        throw new Error("run_capability_missing");
      }
      capabilityRef.current = run.run_capability;
      setState("running");
      await transport.events({
        run,
        capability: run.run_capability,
        lastSequence: lastSequenceRef.current,
        signal: controller.signal,
        onEvent: handleEvent,
      });
    } catch (error) {
      if (!(error instanceof DOMException && error.name === "AbortError")) {
        setState("failed");
      }
      capabilityRef.current = null;
    }
  };

  const restart = () => {
    controllerRef.current?.abort();
    controllerRef.current = null;
    capabilityRef.current = null;
    lastSequenceRef.current = 0;
    setValues(initialValues(agent));
    setOutput(null);
    setState("ready");
  };

  const agentName = agent.localized_metadata.name[locale];
  const agentDescription = agent.localized_metadata.description[locale];
  const otherLocale = alternateLocale(locale);
  const modeLabel =
    agent.interface.mode === "chat"
      ? messages.modeChat
      : agent.interface.mode === "hybrid"
        ? messages.modeHybrid
        : messages.modeForm;

  return (
    <>
      <a className="skipLink" href="#agent-form">
        {messages.run}
      </a>
      <header className="publicHeader">
        <a className="brand" href={`/${locale}/agents/${agent.agent_id}`}>
          <span className="brandMark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span>
            <strong>{messages.brand}</strong>
            <small>{messages.publicLabel}</small>
          </span>
        </a>
        <a
          className="localeSwitch"
          href={`/${otherLocale}/agents/${agent.agent_id}`}
          hrefLang={otherLocale}
          aria-label={`${messages.language}: ${otherLocale}`}
        >
          {otherLocale === "ru-RU" ? "RU" : "EN"}
        </a>
      </header>

      <main className="publicMain">
        <section className="agentIntro" aria-labelledby="agent-title">
          <span className="eyebrow">{messages.publicLabel}</span>
          <h1 id="agent-title">{agentName}</h1>
          <p>{agentDescription}</p>
          <div className="versionNote">
            <span aria-hidden="true" />
            {messages.technicalNote}
          </div>
        </section>

        <section className="agentCard" aria-label={agentName}>
          <div className="cardHeading">
            <span className={`stateDot stateDot--${state}`} aria-hidden="true" />
            <div>
              <strong>
                {state === "completed"
                  ? messages.completed
                  : state === "failed"
                    ? messages.failed
                    : state === "ready"
                      ? messages.ready
                      : modeLabel}
              </strong>
              <small>{modeLabel}</small>
            </div>
          </div>

          <form id="agent-form" onSubmit={submit}>
            <fieldset disabled={state === "submitting" || state === "running"}>
              <legend className="visuallyHidden">{agentName}</legend>
              {agent.interface.input_fields.map((field) => {
                const type = fieldType(field);
                const options = enumValues(field);
                const inputId = `public-field-${field.id}`;
                const label = field.label[locale];

                if (type === "boolean") {
                  return (
                    <label className="booleanField" key={field.id}>
                      <input
                        id={inputId}
                        aria-label={label}
                        type="checkbox"
                        checked={Boolean(values[field.id])}
                        onChange={(change) =>
                          setValues((current) => ({
                            ...current,
                            [field.id]: change.target.checked,
                          }))
                        }
                      />
                      <span>
                        <strong>{label}</strong>
                        <small>{messages.booleanOn}</small>
                      </span>
                    </label>
                  );
                }

                return (
                  <div className="field" key={field.id}>
                    <label htmlFor={inputId}>
                      {label}
                      <small>
                        {field.required ? messages.required : messages.optional}
                      </small>
                    </label>
                    {options.length > 0 ? (
                      <select
                        id={inputId}
                        aria-label={label}
                        required={field.required}
                        value={String(values[field.id])}
                        onChange={(change) =>
                          setValues((current) => ({
                            ...current,
                            [field.id]: change.target.value,
                          }))
                        }
                      >
                        <option value="">{messages.select}</option>
                        {options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        id={inputId}
                        aria-label={label}
                        type={
                          type === "number" || type === "integer"
                            ? "number"
                            : "text"
                        }
                        required={field.required}
                        min={numberAttribute(field, "minimum")}
                        max={numberAttribute(field, "maximum")}
                        step={type === "integer" ? 1 : type === "number" ? "any" : undefined}
                        value={String(values[field.id])}
                        onChange={(change) =>
                          setValues((current) => ({
                            ...current,
                            [field.id]: change.target.value,
                          }))
                        }
                      />
                    )}
                  </div>
                );
              })}
            </fieldset>

            {state === "completed" ? (
              <button className="secondaryButton" type="button" onClick={restart}>
                {messages.restart}
              </button>
            ) : state === "failed" ? (
              <button className="secondaryButton" type="button" onClick={restart}>
                {messages.restart}
              </button>
            ) : (
              <button className="primaryButton" type="submit">
                {state === "submitting" || state === "running"
                  ? messages.running
                  : messages.run}
              </button>
            )}
          </form>

          <div
            className={`runStatus runStatus--${state}`}
            role="status"
            aria-live="polite"
            aria-atomic="true"
          >
            {state === "completed" ? (
              <>
                <span>{messages.completed}</span>
                <pre>{resultText(output)}</pre>
              </>
            ) : state === "submitting" || state === "running" ? (
              <span>{messages.running}</span>
            ) : state === "failed" ? (
              <span>{messages.failed}</span>
            ) : (
              <span>{messages.ready}</span>
            )}
          </div>
          {state === "failed" ? (
            <p className="errorMessage" role="alert">
              {messages.failed}
            </p>
          ) : null}
        </section>
      </main>
    </>
  );
}
