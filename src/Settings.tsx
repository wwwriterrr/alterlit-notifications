import { useEffect, useRef } from 'react';
import { errorText, useSaveSettingsMutation, useSettingsQuery } from './api';
import * as Ic from './icons';
import type { SettingOption } from './types';

/** «Настройки уведомлений»: какие виды присылать. Выключенное не создаётся вовсе, полученное остаётся. */
export default function Settings({ onClose, onError }: { onClose: () => void; onError: (text: string) => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const { data, isLoading, isError, error, refetch } = useSettingsQuery();
  const [save] = useSaveSettingsMutation();

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);

  const groups = new Map<string, SettingOption[]>();
  for (const o of data?.options ?? []) groups.set(o.group, [...(groups.get(o.group) ?? []), o]);

  const toggle = async (o: SettingOption) => {
    try {
      await save({ [o.code]: !o.enabled }).unwrap();
    } catch (e) {
      onError(errorText(e));
    }
  };

  return (
    <dialog ref={ref} className="nt-dialog nt-settings" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="nt-settings-head">
        <div className="nt-dialog-title" role="heading" aria-level={2}>
          Настройки уведомлений
        </div>
        <button type="button" className="nt-icon-btn" aria-label="Закрыть" onClick={onClose}>
          <Ic.Close width={18} height={18} />
        </button>
      </div>
      <p className="nt-settings-note">Выключенные уведомления больше не будут приходить. Уже полученные останутся в списке.</p>

      {isLoading ? (
        <div className="nt-settings-loading">
          <span className="nt-spinner" aria-label="Загружаем" />
        </div>
      ) : isError ? (
        <div className="nt-settings-loading">
          <p>{errorText(error)}</p>
          <button type="button" className="nt-btn" onClick={() => refetch()}>
            Повторить
          </button>
        </div>
      ) : (
        [...groups].map(([group, options]) => (
          <div key={group} className="nt-settings-group" role="group" aria-label={group}>
            <div className="nt-settings-group-title">{group}</div>
            {options.map((o) => (
              <label key={o.code} className="nt-switch-row">
                <span>{o.label}</span>
                <button
                  type="button"
                  role="switch"
                  aria-checked={o.enabled}
                  className="nt-switch"
                  onClick={(e) => {
                    e.preventDefault();
                    toggle(o);
                  }}
                >
                  <i />
                </button>
              </label>
            ))}
          </div>
        ))
      )}

      <div className="nt-dialog-actions">
        <button type="button" className="nt-btn" onClick={onClose}>
          Готово
        </button>
      </div>
    </dialog>
  );
}
