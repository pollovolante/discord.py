# -*- coding: utf-8 -*-

"""
The MIT License (MIT)

Copyright (c) 2015-2016 Rapptz

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

import textwrap
import itertools

from .core import GroupMixin, Command

# help -> shows info of bot on top/bottom and lists subcommands
# help command -> shows detailed info of command
# help command <subcommand chain> -> same as above

# <description>

# <command signature with aliases>

# <long doc>

# Cog:
#   <command> <shortdoc>
#   <command> <shortdoc>
# Other Cog:
#   <command> <shortdoc>
# No Category:
#   <command> <shortdoc>

# Type <prefix>help command for more info on a command.
# You can also type <prefix>help category for more info on a category.


class HelpFormatter:
    """The default base implementation that handles formatting of the help
    command.

    To override the behaviour of the formatter, :meth:`format`
    should be overridden. A number of utility functions are provided for use
    inside that method.

    Parameters
    -----------
    show_hidden : bool
        Dictates if hidden commands should be shown in the output.
        Defaults to ``False``.
    show_check_faiure : bool
        Dictates if commands that have their :attr:`Command.checks` failed
        shown. Defaults to ``False``.
    width : int
        The maximum number of characters that fit in a line.
        Defaults to 80.
    """
    def __init__(self, show_hidden=False, show_check_faiure=False, width=80):
        self.wrapper = textwrap.TextWrapper(width=width)
        self.show_hidden = show_hidden
        self.show_check_faiure = show_check_faiure

    def has_subcommands(self):
        """bool : Specifies if the command has subcommands."""
        return isinstance(self.command, GroupMixin)

    def is_bot(self):
        """bool : Specifies if the command being formatted is the bot itself."""
        return self.command is self.context.bot

    def shorten(self, text):
        """Shortens text to fit into the :attr:`width`."""
        tmp = self.wrapper.max_lines
        self.wrapper.max_lines = 1
        res = self.wrapper.fill(text)
        self.wrapper.max_lines = tmp
        del tmp
        return res

    @property
    def max_name_size(self):
        """int : Returns the largest name length of a command or if it has subcommands
        the largest subcommand name."""
        try:
            return max(map(lambda c: len(c.name), self.command.commands.values()))
        except AttributeError:
            return len(self.command.name)

    @property
    def clean_prefix(self):
        """The cleaned up invoke prefix. i.e. mentions are ``@name`` instead of ``<@id>``."""
        user = self.context.bot.user
        # this breaks if the prefix mention is not the bot itself but I
        # consider this to be an *incredibly* strange use case. I'd rather go
        # for this common use case rather than waste performance for the
        # odd one.
        return self.context.prefix.replace(user.mention, '@' + user.name)

    def get_command_signature(self):
        """Retrieves the signature portion of the help page."""
        result = []
        prefix = self.clean_prefix
        cmd = self.command
        if len(cmd.aliases) > 0:
            aliases = '|'.join(cmd.aliases)
            name = '{0}[{1.name}|{2}]'.format(prefix, cmd, aliases)
            result.append(name)
        else:
            result.append(prefix + cmd.name)

        params = cmd.clean_params
        if len(params) > 0:
            for name, param in params.items():
                cleaned_name = name.replace('_', '-')
                if param.default is not param.empty:
                    result.append('{0}={1}'.format(cleaned_name, param.default))
                elif param.kind == param.VAR_POSITIONAL:
                    result.append(cleaned_name + '...')
                else:
                    result.append(cleaned_name)

        return ' '.join(result)

    def get_ending_note(self):
        return "Type {0}help command for more info on a command.\n" \
               "You can also type {0}help category for more info on a category.".format(self.clean_prefix)

    def filter_command_list(self):
        """Returns a filtered list of commands based on the two attributes
        provided, :attr:`show_check_faiure` and :attr:`show_hidden`.

        Returns
        --------
        iterable
            An iterable with the filter being applied. The resulting value is
            a (key, value) tuple of the command name and the command itself.
        """
        def predicate(tuple):
            cmd = tuple[1]
            if cmd.hidden and not self.show_hidden:
                return False

            if self.show_check_faiure:
                # we don't wanna bother doing the checks if the user does not
                # care about them, so just return true.
                return True
            return cmd.can_run(self.context)

        return filter(predicate, self.command.commands.items())

    def _check_new_page(self):
        # be a little on the safe side
        if self._count > 1920:
            # add the page
            self._current_page.append('```')
            self._pages.append('\n'.join(self._current_page))
            self._current_page = ['```']
            self._count = 4

    def _add_subcommands_to_page(self, max_width, commands):
        for name, command in commands:
            if name in command.aliases:
                # skip aliases
                continue

            entry = '  {0:<{width}} {1}'.format(name, command.short_doc, width=max_width)
            shortened = self.shorten(entry)
            self._count += len(shortened)
            self._check_new_page()
            self._current_page.append(shortened)

    def format_help_for(self, context, command_or_bot):
        """Formats the help page and handles the actual heavy lifting of how
        the help command looks like. To change the behaviour, override the
        :meth:`format` method.

        Parameters
        -----------
        context : :class:`Context`
            The context of the invoked help command.
        command_or_bot : :class:`Command` or :class:`Bot`
            The bot or command that we are getting the help of.

        Returns
        --------
        list
            A paginated output of the help command.
        """
        self.context = context
        self.command = command_or_bot
        return self.format()

    def format(self):
        """Handles the actual behaviour involved with formatting.

        To change the behaviour, this method should be overridden.

        Returns
        --------
        list
            A paginated output of the help command.
        """
        self._pages = []
        self._count = 4 # ``` + '\n'
        self._current_page = ['```']

        # we need a padding of ~80 or so

        if self.command.description:
            # <description> portion
            self._current_page.append(self.command.description)
            self._current_page.append('')
            self._count += len(self.command.description)

        if not self.is_bot():
            # <signature portion>
            signature = self.get_command_signature()
            self._count += 2 + len(signature) # '\n' sig '\n'
            self._current_page.append(signature)
            self._current_page.append('')

            # <long doc> section
            if self.command.help:
                self._count += 2 + len(self.command.help)
                self._current_page.append(self.command.help)
                self._current_page.append('')
                self._check_new_page()

        if not self.has_subcommands():
            self._current_page.append('```')
            self._pages.append('\n'.join(self._current_page))
            return self._pages

        max_width = self.max_name_size

        def category(tup):
            cog = tup[1].cog_name
            # we insert the zero width space there to give it approximate
            # last place sorting position.
            return cog + ':' if cog is not None else '\u200bNo Category:'

        if self.is_bot():
            data = sorted(self.filter_command_list(), key=category)
            for category, commands in itertools.groupby(data, key=category):
                # there simply is no prettier way of doing this.
                commands = list(commands)
                if len(commands) > 0:
                    self._current_page.append(category)
                    self._count += len(category)
                    self._check_new_page()

                self._add_subcommands_to_page(max_width, commands)
        else:
            self._current_page.append('Commands:')
            self._count += 1 + len(self._current_page[-1])
            self._add_subcommands_to_page(max_width, self.filter_command_list())

        # add the ending note
        self._current_page.append('')
        ending_note = self.get_ending_note()
        self._count += len(ending_note)
        self._check_new_page()
        self._current_page.append(ending_note)

        if len(self._current_page) > 1:
            self._current_page.append('```')
            self._pages.append('\n'.join(self._current_page))

        return self._pages
