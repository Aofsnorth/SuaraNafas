"use client";

import { useEffect, useRef, type MouseEvent, type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  labelledBy?: string;
  className?: string;
  children: ReactNode;
}

export function Modal({ open, onClose, labelledBy, className, children }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    // Handle initial state and state changes
    if (open) {
      if (!dialog.open) {
         // Use setTimeout to avoid 'dialog is already open' errors when rapidly switching between dialogs
         setTimeout(() => {
             if (ref.current && !ref.current.open) ref.current.showModal();
         }, 0)
      }
    } else {
      if (dialog.open) {
        dialog.close();
      }
    }
  }, [open]);

  // Sync state if closed via escape key
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;

    const handleCancel = (e: Event) => {
        e.preventDefault();
        onClose();
    }

    dialog.addEventListener('cancel', handleCancel);
    return () => dialog.removeEventListener('cancel', handleCancel);
  }, [onClose])

  const handleClick = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === ref.current) onClose();
  };

  return (
    <dialog
      ref={ref}
      className={cn("modal", className)}
      aria-labelledby={labelledBy}
      onClose={onClose}
      onClick={handleClick}
    >
      {children}
    </dialog>
  );
}
