import { DropdownMenu, Flex, IconButton } from '@radix-ui/themes'
import { BiPlus } from 'react-icons/bi'
import { RightToolbarButtonsProps } from '../RightToolbarButtons'
import { MdOutlineBarChart } from 'react-icons/md'
import AttachFile from './AttachFile'
import { useBoolean } from '@/hooks/useBoolean'
import CreatePollDrawer from './CreatePollDrawer'

// The GIF action was removed with the desktop one — the Tenor API it called was
// shut down by Google on 2026-06-30. See common/GIFPicker/GIFPicker.tsx.
const MobileInputActions = ({ fileProps, channelID }: RightToolbarButtonsProps) => {

    const [isPollOpen, { on: onPollOpen }, setIsPollOpen] = useBoolean()
    return (
        <>
            <DropdownMenu.Root>
                <DropdownMenu.Trigger>
                    <IconButton radius='full' color='gray' variant='soft' size='2' className='mb-1'>
                        <BiPlus size='20' />
                    </IconButton>
                </DropdownMenu.Trigger>
                <DropdownMenu.Content className='min-w-48' size='2'>
                    <DropdownMenu.Item onClick={onPollOpen} className='text-base !h-10'>
                        <Flex gap='2' className='items-center'>
                            <MdOutlineBarChart />
                            Poll
                        </Flex>
                    </DropdownMenu.Item>
                    {fileProps && <AttachFile fileProps={fileProps} />}
                </DropdownMenu.Content>
            </DropdownMenu.Root>
            {channelID && <CreatePollDrawer isOpen={isPollOpen} setIsOpen={setIsPollOpen} channelID={channelID} />}
        </>
    )
}

export default MobileInputActions