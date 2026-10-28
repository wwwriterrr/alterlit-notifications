import { useEffect, useRef } from 'react';

export default function Confirm({
  title,
  text,
  confirm,
  busy,
  onConfirm,
  onClose,
}: {
  title: string;
  text: string;
  confirm: string;
  busy?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
  }, []);
  return (
    <dialog ref={ref} className="nt-dialog" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}>
      <div className="nt-dialog-title" role="heading" aria-level={2}>
        {title}
      </div>
      <p>{text}</p>
      <div className="nt-dialog-actions">
        <button type="button" className="nt-btn" onClick={onClose}>
          Отмена
        </button>
        <button type="button" className="nt-btn nt-btn-danger" onClick={onConfirm} disabled={busy}>
          {confirm}
        </button>
      </div>
    </dialog>
  );
}
