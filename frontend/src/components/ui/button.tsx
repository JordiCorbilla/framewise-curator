import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

const variants = cva('inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-45 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#bdcdb1]', { variants: { variant: { default: 'bg-[#c4d2b8] text-[#182014] hover:bg-[#d5dfcc]', outline: 'border border-white/15 bg-white/3 text-[#dddeda] hover:bg-white/8', ghost: 'text-[#a5aaa3] hover:bg-white/6 hover:text-white', danger: 'bg-[#693e3c] text-white hover:bg-[#80514e]' }, size: { default: 'h-10 px-4', sm: 'h-8 px-3 text-xs', icon: 'h-9 w-9' } }, defaultVariants: { variant: 'default', size: 'default' } })
type Props = React.ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof variants> & { asChild?: boolean }
export function Button({ className, variant, size, asChild = false, ...props }: Props) { const Comp = asChild ? Slot : 'button'; return <Comp className={twMerge(clsx(variants({ variant, size }), className))} {...props} /> }
