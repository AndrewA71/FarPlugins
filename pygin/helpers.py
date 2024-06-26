﻿"""
Helpers
"""
"""
helpers.py
"""
"""
Copyright 2017 Alex Alabuzhev
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions
are met:
1. Redistributions of source code must retain the above copyright
   notice, this list of conditions and the following disclaimer.
2. Redistributions in binary form must reproduce the above copyright
   notice, this list of conditions and the following disclaimer in the
   documentation and/or other materials provided with the distribution.
3. The name of the authors may not be used to endorse or promote products
   derived from this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

from functools import partial
from pygin import far

class Plugin:
    class Panel:
        def __init__(self, PanelId):
            self.PanelId = PanelId
            self.PanelControl = partial(far.PanelControl, self.PanelId)

    def __init__(self):
        self.GetMsg = partial(far.GetMsg, self.Guid)
        self.Message = partial(far.Message, self.Guid)
        self.InputBox = partial(far.InputBox, self.Guid)
        self.DialogRun= partial(far.DialogRun, self.Guid)
        self.Menu = partial(far.Menu, self.Guid)
        self.ShowHelp = partial(far.ShowHelp, self.Guid)
        self.AdvControl = partial(far.AdvControl, self.Guid)
        self.ActivePanel = self.Panel(far.Panels.Active)
        self.PassivePanel = self.Panel(far.Panels.Passive)
        self.Editor = partial(far.Editor, self.Guid)

class Console:
    def __enter__(self):
        self.__cmd(far.FileControlCommands.GetUserScreen)

    def __exit__(self, *args):
        self.__cmd(far.FileControlCommands.SetUserScreen)

    def __cmd(self, Command):
        far.PanelControl(far.Panels.Active, Command)
