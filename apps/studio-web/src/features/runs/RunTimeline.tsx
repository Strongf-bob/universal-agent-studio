"use client";

import type {RunEvent} from "@universal-agent-studio/contracts";
import {Ban, LoaderCircle, RotateCw} from "lucide-react";
import {useTranslations} from "next-intl";

import type {RunConnectionState} from "@/features/runs/useRunEvents";

type Props = {
  events: RunEvent[];
  connectionState: RunConnectionState;
  canCancel: boolean;
  cancelling: boolean;
  onCancel: () => void;
};

const EVENT_KEYS: Record<RunEvent["type"], string> = {
  "run.started": "runStarted",
  "node.started": "nodeStarted",
  "model.requested": "modelRequested",
  "model.completed": "modelCompleted",
  "tool.requested": "toolRequested",
  "tool.completed": "toolCompleted",
  "approval.required": "approvalRequired",
  "approval.resolved": "approvalResolved",
  "node.failed": "nodeFailed",
  "node.completed": "nodeCompleted",
  "run.completed": "runCompleted",
  "run.failed": "runFailed",
  "run.cancelled": "runCancelled",
};

export function RunTimeline({
  events,
  connectionState,
  canCancel,
  cancelling,
  onCancel,
}: Props) {
  const t = useTranslations("run.timeline");

  return (
    <section className="runPanel" aria-labelledby="timeline-title">
      <header className="panelHeader">
        <div>
          <p className="metaLabel">{t("eyebrow")}</p>
          <h2 id="timeline-title">{t("title")}</h2>
        </div>
        {canCancel ? (
          <button
            className="buttonSecondary buttonDanger"
            type="button"
            disabled={cancelling}
            onClick={onCancel}
          >
            <Ban aria-hidden />
            {cancelling ? t("cancelling") : t("cancel")}
          </button>
        ) : null}
      </header>

      <div
        className={`connectionState connectionState--${connectionState}`}
        role="status"
        aria-live="polite"
      >
        {connectionState === "reconnecting" ? (
          <RotateCw aria-hidden />
        ) : (
          <LoaderCircle aria-hidden />
        )}
        {t(`connection.${connectionState}`)}
      </div>

      <ol className="eventTimeline">
        {events.map((item) => (
          <li key={item.event_id}>
            <span
              className={`eventMarker eventMarker--${item.type.replaceAll(".", "-")}`}
              aria-hidden
            />
            <div>
              <strong>{t(`events.${EVENT_KEYS[item.type]}`)}</strong>
              <span>
                {item.node_id
                  ? t("nodeEvent", {
                      nodeId: item.node_id,
                      sequence: item.sequence,
                    })
                  : t("runEvent", {sequence: item.sequence})}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}
