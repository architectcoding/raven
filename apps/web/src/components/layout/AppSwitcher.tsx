import type { ReactNode } from "react"
import { useFrappeGetCall } from "frappe-react-sdk"
import {
    BookOpenIcon, BriefcaseIcon, HomeIcon, LayersIcon, LayoutGridIcon, MessageCircleIcon,
    PenLineIcon, PercentIcon, ShoppingCartIcon, TrendingUpIcon, UsersIcon, WrenchIcon,
    type LucideIcon,
} from "lucide-react"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@components/ui/dropdown-menu"
import _ from "@lib/translate"

/**
 * The site's other apps, where the suite Raven is installed beside answers the
 * `raven_app_switcher` hook (raven/api/app_switcher.py). Opened from a phone app
 * shell, Raven had no way back: no address bar, and nothing in Raven leads out.
 * Raven never imports the suite; with no answer nothing is drawn.
 */

type SwitcherApp = { key: string, label: string, route: string, icon: string }

export const hasAppSwitcher = (): boolean => Boolean(window.frappe?.boot?.has_app_switcher)

// The suite names Feather icons; their lucide twins, and a grid for the rest.
const ICONS: Record<string, LucideIcon> = {
    "home": HomeIcon, "trending-up": TrendingUpIcon, "shopping-cart": ShoppingCartIcon,
    "layers": LayersIcon, "book-open": BookOpenIcon, "tool": WrenchIcon, "users": UsersIcon,
    "percent": PercentIcon, "edit-3": PenLineIcon, "message-circle": MessageCircleIcon,
    "briefcase": BriefcaseIcon,
}

/** `children` is the trigger (asChild); without a provider it renders alone. */
export const AppSwitcherMenu = ({ children, side = "bottom", align = "start" }: {
    children: ReactNode, side?: "top" | "right" | "bottom" | "left", align?: "start" | "center" | "end"
}) => {
    const enabled = hasAppSwitcher()
    const { data } = useFrappeGetCall<{ message: SwitcherApp[] }>(
        "raven.api.app_switcher.get_app_switcher",
        undefined,
        enabled ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    if (!enabled) return <>{children}</>

    // Raven itself is where you are: the list is where you can go.
    const apps = (data?.message ?? []).filter((app) => app.key !== "raven")

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>{children}</DropdownMenuTrigger>
            <DropdownMenuContent side={side} align={align} sideOffset={4} className="min-w-52">
                {apps.length ? apps.map((app) => {
                    const Icon = ICONS[app.icon] ?? LayoutGridIcon
                    return (
                        <DropdownMenuItem key={app.key} onSelect={() => { window.location.href = app.route }}>
                            <Icon /> {app.label}
                        </DropdownMenuItem>
                    )
                }) : (
                    <DropdownMenuItem disabled>{data ? _("No other apps") : _("Loading...")}</DropdownMenuItem>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    )
}
