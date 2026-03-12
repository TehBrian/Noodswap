import asyncio

from bot.command_gate import command_execution_gate


class CommandGateTests:
    async def test_command_gate_rejects_concurrent_same_key(self) -> None:
        first_entered = False
        second_entered = True
        release_first = asyncio.Event()

        async def first_call() -> None:
            nonlocal first_entered
            async with command_execution_gate(100, "monopoly_roll") as entered:
                first_entered = entered
                assert entered
                await release_first.wait()

        async def second_call() -> None:
            nonlocal second_entered
            # Ensure the first call entered before attempting the second one.
            await asyncio.sleep(0)
            async with command_execution_gate(100, "monopoly_roll") as entered:
                second_entered = entered

        task = asyncio.create_task(first_call())
        await asyncio.sleep(0)
        await second_call()
        release_first.set()
        await task

        assert first_entered
        assert not (second_entered)

    async def test_command_gate_allows_different_actions(self) -> None:
        async with command_execution_gate(100, "flip") as flip_entered:
            async with command_execution_gate(100, "slots") as slots_entered:
                assert flip_entered
                assert slots_entered
