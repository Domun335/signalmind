import * as React from "react"
import { cn } from "cn"

function Label({ className, ...props }) {
  return (
    <label
      data-slot="label"
      className={cn(
        "text-[10px] font-mono font-medium text-muted-foreground select-none leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70",
        className
      )}
      {...props}
    />
  )
}

export { Label }
