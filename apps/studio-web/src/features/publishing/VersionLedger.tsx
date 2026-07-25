import type {PublicationState} from "@universal-agent-studio/contracts";
import {useTranslations} from "next-intl";

type Props = {
  state: PublicationState;
  busy: boolean;
  onRollback: (versionId: string) => void;
};

function digestPrefix(digest: string): string {
  return digest.slice(0, 12);
}

export function VersionLedger({state, busy, onRollback}: Props) {
  const t = useTranslations("publishing");

  return (
    <section
      className="publishingPanel publishingPanel--wide"
      aria-labelledby="version-history-title"
      aria-label={t("versions.title")}
    >
      <div className="publishingPanelHeader">
        <div>
          <span className="eyebrow">{t("versions.eyebrow")}</span>
          <h2 id="version-history-title">{t("versions.title")}</h2>
        </div>
        <span className="countBadge">{state.versions.length}</span>
      </div>

      <div className="publishingTableScroll">
        <table className="publishingTable">
          <caption className="visuallyHidden">{t("versions.title")}</caption>
          <thead>
            <tr>
              <th scope="col">{t("versions.version")}</th>
              <th scope="col">{t("versions.digest")}</th>
              <th scope="col">{t("versions.created")}</th>
              <th scope="col">{t("versions.traffic")}</th>
              <th scope="col">{t("versions.action")}</th>
            </tr>
          </thead>
          <tbody>
            {[...state.versions].reverse().map((version) => {
              const active = version.version_id === state.active_version_id;
              return (
                <tr key={version.version_id}>
                  <td>
                    <strong>v{version.version_number}</strong>
                    <small>{version.version_id}</small>
                  </td>
                  <td>
                    <code>{digestPrefix(version.digest)}</code>
                  </td>
                  <td>
                    <time dateTime={version.created_at}>
                      {new Intl.DateTimeFormat(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      }).format(new Date(version.created_at))}
                    </time>
                  </td>
                  <td>
                    {active ? (
                      <span className="trafficBadge">{t("versions.active")}</span>
                    ) : (
                      t("versions.inactive")
                    )}
                  </td>
                  <td>
                    {active || !state.active_version_id ? null : (
                      <button
                        className="textButton"
                        type="button"
                        disabled={busy}
                        onClick={() => onRollback(version.version_id)}
                        aria-label={t("versions.rollbackTo", {
                          versionId: version.version_id,
                        })}
                      >
                        {t("versions.switchTraffic")}
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="ledger">
        <h3>{t("ledger.title")}</h3>
        {state.events.length === 0 ? (
          <p className="emptyState">{t("ledger.empty")}</p>
        ) : (
          <div className="publishingTableScroll">
            <table className="publishingTable publishingTable--compact">
              <caption className="visuallyHidden">{t("ledger.title")}</caption>
              <thead>
                <tr>
                  <th scope="col">{t("ledger.event")}</th>
                  <th scope="col">{t("ledger.route")}</th>
                  <th scope="col">{t("ledger.created")}</th>
                </tr>
              </thead>
              <tbody>
                {state.events.map((event) => (
                  <tr key={event.event_id}>
                    <td>
                      <span className="eventKind">
                        {event.event_type === "publish"
                          ? t("ledger.publish")
                          : t("ledger.rollback")}
                      </span>
                    </td>
                    <td>
                      <code>
                        {event.previous_version_id ?? "∅"} →{" "}
                        {event.selected_version_id}
                      </code>
                    </td>
                    <td>
                      <time dateTime={event.created_at}>
                        {new Intl.DateTimeFormat(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        }).format(new Date(event.created_at))}
                      </time>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
