from types import SimpleNamespace
import unittest

import discord
from discord.ext import commands

from noodswap.app import _resolve_command_prefix


class AppPrefixTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bot = commands.Bot(command_prefix="ns ", intents=discord.Intents.none(), help_command=None)

    def test_resolve_prefix_matches_uppercase_long_prefix(self) -> None:
        message = SimpleNamespace(content="Ns help")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertIn("Ns ", prefixes)

    def test_resolve_prefix_matches_uppercase_short_prefix(self) -> None:
        message = SimpleNamespace(content="Nhelp")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertIn("N", prefixes)

    def test_resolve_prefix_ignores_non_prefix_content(self) -> None:
        message = SimpleNamespace(content="hello ns help")

        prefixes = _resolve_command_prefix(self.bot, message)

        self.assertNotIn("he", prefixes)
        self.assertNotIn("hello", prefixes)
