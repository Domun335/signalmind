import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cn } from "cn"

function Input({
  className,
  type,
  ...props
}) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "flex h-8 w-full rounded-md border border-border/70 bg-background/80 px-2.5 py-1 text-xs font-mono text-foreground shadow-xs transition-colors outline-none placeholder:text-muted-foreground/60 focus-visible:border-cyan-400 focus-visible:ring-1 focus-visible:ring-cyan-400/50 disabled:cursor-not-allowed disabled:opacity-50 aria-invalid:border-destructive aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    />
  )
}

export { Input }
