import * as React from "react"
import { cn } from "@/lib/utils"

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "outline" | "ghost" | "danger"
  size?: "default" | "sm" | "lg" | "icon"
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "default", size = "default", ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          "btn",
          {
            "btn-primary text-black": variant === "default",
            "btn-outline text-white": variant === "outline",
            "btn-ghost text-white": variant === "ghost",
            "btn-error text-red-500 bg-red-500/10 hover:bg-red-500/20 glass": variant === "danger",
            "btn-sm": size === "sm",
            "btn-lg": size === "lg",
            "btn-square btn-sm": size === "icon",
          },
          className
        )}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button }
