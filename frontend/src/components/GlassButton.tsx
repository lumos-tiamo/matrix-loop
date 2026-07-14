import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "text-white bg-gradient-to-br from-blue1 to-blue2 shadow-[0_6px_16px_rgba(47,123,255,0.4)]",
  secondary: "bg-white/8 border border-white/12 text-txt",
  ghost: "bg-transparent text-muted2 hover:text-txt",
};

export function GlassButton({
  variant = "secondary",
  className = "",
  ...p
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      className={`rounded-xl px-4 py-2 text-[12.5px] font-medium transition ${VARIANTS[variant]} ${className}`}
      {...p}
    />
  );
}
