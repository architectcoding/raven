import { DropdownMenu } from '@radix-ui/themes'
import { useFrappeGetCall } from 'frappe-react-sdk'
import { ReactNode } from 'react'
import {
    FiBookOpen, FiBriefcase, FiEdit3, FiGrid, FiHome, FiLayers, FiMessageCircle,
    FiPercent, FiShoppingCart, FiTool, FiTrendingUp, FiUsers,
} from 'react-icons/fi'
import { __ } from '@/utils/translations'

/**
 * The site's other apps, where the suite Raven is installed beside answers the
 * `raven_app_switcher` hook (raven/api/app_switcher.py). Opened from the ERPbio
 * phone app, Raven had no way back: no address bar, and nothing in Raven leads
 * out. Raven never imports the suite; with no answer nothing is drawn.
 */

type SwitcherApp = { key: string, label: string, route: string, icon: string }

// @ts-expect-error -- boot is set by raven.html before the bundle runs
export const hasAppSwitcher = (): boolean => !!window.frappe?.boot?.has_app_switcher

// The suite names Feather icons; the handful it uses, and a grid for the rest.
const ICONS: Record<string, typeof FiGrid> = {
    'home': FiHome, 'trending-up': FiTrendingUp, 'shopping-cart': FiShoppingCart,
    'layers': FiLayers, 'book-open': FiBookOpen, 'tool': FiTool, 'users': FiUsers,
    'percent': FiPercent, 'edit-3': FiEdit3, 'message-circle': FiMessageCircle,
    'briefcase': FiBriefcase,
}

/** `children` is the trigger (asChild); without a provider it renders alone. */
export const AppSwitcherMenu = ({ children, side = 'bottom', align = 'start' }: {
    children: ReactNode, side?: 'top' | 'right' | 'bottom' | 'left', align?: 'start' | 'center' | 'end'
}) => {

    const enabled = hasAppSwitcher()
    const { data } = useFrappeGetCall<{ message: SwitcherApp[] }>(
        'raven.api.app_switcher.get_app_switcher', undefined, enabled ? undefined : null,
        { revalidateOnFocus: false, revalidateIfStale: false }
    )

    if (!enabled) return <>{children}</>

    // Raven itself is where you are: the list is where you can go.
    const apps = (data?.message ?? []).filter((a) => a.key !== 'raven')

    return (
        <DropdownMenu.Root>
            <DropdownMenu.Trigger>
                {children}
            </DropdownMenu.Trigger>
            <DropdownMenu.Content variant='soft' side={side} align={align} className='min-w-52'>
                {apps.length ? apps.map((a) => {
                    const Icon = ICONS[a.icon] ?? FiGrid
                    return (
                        <DropdownMenu.Item key={a.key} color='gray' className='flex justify-normal gap-2'
                            onSelect={() => { window.location.href = a.route }}>
                            <Icon size='14' /> {a.label}
                        </DropdownMenu.Item>
                    )
                }) : (
                    <DropdownMenu.Item disabled color='gray'>{data ? __("No other apps") : __("Loading...")}</DropdownMenu.Item>
                )}
            </DropdownMenu.Content>
        </DropdownMenu.Root>
    )
}
