import {
  forwardRef,
  useId,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";

import { cx } from "@/lib/cx";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary: "bg-(--accent) text-white shadow-sm hover:brightness-110 active:brightness-95",
  secondary: "bg-white text-ink ring-1 ring-black/10 hover:bg-black/[0.03]",
  ghost: "text-(--accent-text) hover:bg-(--accent-soft)",
  danger: "bg-red-600 text-white hover:bg-red-700",
};

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  block?: boolean;
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", loading = false, block = false, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cx(
        "inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 py-2.5 font-bold transition disabled:cursor-not-allowed disabled:opacity-60",
        BUTTON_VARIANTS[variant],
        block && "w-full",
        className,
      )}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      {...props}
    >
      {loading && <Spinner className="size-4" />}
      {children}
    </button>
  );
});

export function Spinner({ className = "size-6" }: { className?: string }) {
  return (
    <span
      role="status"
      aria-label="Carregando"
      className={cx(
        "inline-block animate-spin rounded-full border-2 border-current border-r-transparent",
        className,
      )}
    />
  );
}

export function PageLoader() {
  return (
    <div className="flex min-h-[40vh] items-center justify-center text-(--accent)">
      <Spinner className="size-10" />
    </div>
  );
}

type FieldProps = {
  label: string;
  error?: string;
  hint?: string;
  children: (id: string) => ReactNode;
};

export function Field({ label, error, hint, children }: FieldProps) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-bold">
        {label}
      </label>
      {children(id)}
      {hint && !error && <p className="text-sm text-gray-500">{hint}</p>}
      {error && (
        <p role="alert" className="text-sm font-semibold text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

const INPUT_CLASSES =
  "block w-full rounded-2xl border-0 bg-white px-4 py-3 text-base ring-1 ring-black/10 placeholder:text-gray-400 focus:ring-2 focus:ring-(--accent) focus:outline-none aria-[invalid=true]:ring-red-500";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(
  function Input({ className, ...props }, ref) {
    return <input ref={ref} className={cx(INPUT_CLASSES, className)} {...props} />;
  },
);

export const TextArea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function TextArea({ className, ...props }, ref) {
  return <textarea ref={ref} className={cx(INPUT_CLASSES, "min-h-24", className)} {...props} />;
});

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={cx("rounded-3xl bg-white p-5 shadow-sm ring-1 ring-black/5", className)}>
      {children}
    </div>
  );
}

export function Alert({
  tone = "error",
  children,
}: {
  tone?: "error" | "info" | "success" | "warning";
  children: ReactNode;
}) {
  const tones = {
    error: "bg-red-50 text-red-800 ring-red-200",
    info: "bg-sky-50 text-sky-900 ring-sky-200",
    success: "bg-emerald-50 text-emerald-900 ring-emerald-200",
    warning: "bg-amber-50 text-amber-900 ring-amber-200",
  };
  return (
    <div
      role={tone === "error" ? "alert" : "status"}
      className={cx("rounded-2xl px-4 py-3 text-sm font-semibold ring-1", tones[tone])}
    >
      {children}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center gap-4 py-12 text-center">
      <span className="text-5xl" aria-hidden>
        😵
      </span>
      <p className="max-w-sm font-semibold">{message}</p>
      {onRetry && (
        <Button variant="secondary" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  );
}

export function EmptyState({
  emoji,
  title,
  children,
}: {
  emoji: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-10 text-center">
      <span className="text-5xl" aria-hidden>
        {emoji}
      </span>
      <p className="text-lg font-extrabold">{title}</p>
      {children && <div className="max-w-sm text-gray-600">{children}</div>}
    </div>
  );
}

export function Avatar({
  name,
  url,
  size = "size-10",
}: {
  name: string;
  url?: string | null;
  size?: string;
}) {
  const initials = name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return url ? (
    <img
      src={url}
      alt=""
      referrerPolicy="no-referrer"
      className={cx(size, "rounded-full object-cover")}
    />
  ) : (
    <span
      aria-hidden
      className={cx(
        size,
        "inline-flex shrink-0 items-center justify-center rounded-full bg-(--accent-soft) font-extrabold text-(--accent-text)",
      )}
    >
      {initials}
    </span>
  );
}
