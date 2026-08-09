/**
 * ORPHANED — nothing renders this any more, and it cannot work as written.
 *
 * Google discontinued the Tenor API on 2026-06-30 and stopped issuing new keys
 * on 2026-01-13, so every request below returns
 * `403 "Tenor API is discontinued"`. That is not a configuration problem and no
 * key fixes it: the button was removed from RightToolbarButtons.tsx and
 * MobileActions/MobileInputActions.tsx rather than left visible and broken.
 *
 * Kept, not deleted, because reviving GIFs is a small change rather than a
 * rewrite. Klipy (built by ex-Tenor staff) is close to a drop-in: swap the two
 * endpoint constants below for api.klipy.com, take the key from a new Raven
 * Settings field, and adjust the response mapping if their shape differs.
 * Both surviving vendors — Klipy and Giphy — require displaying their branding
 * and cap free keys at 100 calls/hour, which is the real decision to make
 * before wiring this back up, not the code.
 */
import { useDebounce } from "@/hooks/useDebounce"
import { Box, Flex, ScrollArea, TextField } from "@radix-ui/themes"
import { useState } from "react"
import { BiSearch } from "react-icons/bi"
import { GIFSearchResults } from "./GIFSearchResults"
import { GIFFeaturedResults } from "./GIFFeaturedResults"

export const TENOR_SEARCH_API_ENDPOINT_BASE = `https://tenor.googleapis.com/v2/search`
export const TENOR_FEATURED_API_ENDPOINT_BASE = `https://tenor.googleapis.com/v2/featured`
// @ts-expect-error
export const TENOR_API_KEY = window.frappe?.boot.tenor_api_key
// @ts-expect-error
export const TENOR_CLIENT_KEY = import.meta.env.DEV ? `dev::${window.frappe?.boot.sitename}` : window.frappe?.boot.sitename

export interface GIFPickerProps {
    onSelect: (gif: any) => void
}

/**
 * GIF Picker component (in-house) to search and select GIFs
 * @param onSelect - callback function to handle GIF selection
 */
const GIFPicker = ({ onSelect }: GIFPickerProps) => {
    // Get GIFs from Tenor API and display them
    // show a search bar to search for GIFs
    // on select, call onSelect with the gif URL

    const [searchText, setSearchText] = useState("")
    const debouncedText = useDebounce(searchText, 200)

    return (
        <Flex className="w-full justify-center">
            <Flex direction={'column'} gap='2' align='center' pt={'3'} width={'100%'} className="px-0.5 sm:px-4">
                <Box className="w-full">
                    <TextField.Root className="w-full mb-1"
                        onChange={(e) => setSearchText(e.target.value)}
                        value={searchText}
                        type='text'
                        placeholder='Search GIFs'>
                        <TextField.Slot side='left'>
                            <BiSearch />
                        </TextField.Slot>
                    </TextField.Root>
                </Box>
                <ScrollArea className="h-[74vh] sm:h-auto pb-6 sm:pb-10 ">
                    {debouncedText.length >= 2 ? (
                        <GIFSearchResults query={debouncedText} onSelect={onSelect} />
                    ) : (
                        <GIFFeaturedResults onSelect={onSelect} />
                    )}

                </ScrollArea>


                <Box position={'fixed'} className="bottom-0 py-2 bg-background w-full text-center">
                    <img
                        src="https://www.gstatic.com/tenor/web/attribution/PB_tenor_logo_blue_horizontal.png"
                        alt="Powered by Tenor"
                        width="100"
                    />
                </Box>
            </Flex>
        </Flex>
    )
}

export default GIFPicker