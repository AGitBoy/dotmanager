#!/usr/bin/env python3
"""This module provides all functionality and base classes for
regression tests. It provides also all needed types and colors
as the test modules shall be independent from Dotmanager"""

# Copyright 2018 Erik Schulz
#
# This file is part of Dotmanager.
#
# Dotmanger is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Dotmanger is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Dotmanger.  If not, see <http://www.gnu.org/licenses/>.
#
# Diese Datei ist Teil von Dotmanger.
#
# Dotmanger ist Freie Software: Sie können es unter den Bedingungen
# der GNU General Public License, wie von der Free Software Foundation,
# Version 3 der Lizenz oder (nach Ihrer Wahl) jeder neueren
# veröffentlichten Version, weiter verteilen und/oder modifizieren.
#
# Dotmanger wird in der Hoffnung, dass es nützlich sein wird, aber
# OHNE JEDE GEWÄHRLEISTUNG, bereitgestellt; sogar ohne die implizite
# Gewährleistung der MARKTFÄHIGKEIT oder EIGNUNG FÜR EINEN BESTIMMTEN ZWECK.
# Siehe die GNU General Public License für weitere Details.
#
# Sie sollten eine Kopie der GNU General Public License zusammen mit diesem
# Programm erhalten haben. Wenn nicht, siehe <https://www.gnu.org/licenses/>.

import hashlib
import os
from abc import abstractmethod
from subprocess import PIPE
from subprocess import Popen
from typing import Dict
from typing import List
from typing import Tuple
from typing import Union

TestResult = Dict[str, Union[bool, str]]
CheckResult = Tuple[bool, str]
FileDescriptor = Dict[str, Union[bool, int, str]]
LinkDescriptor = FileDescriptor
FileList = List[FileDescriptor]
LinkList = List[LinkDescriptor]
DirDescriptor = Dict[str, Union[bool, int, FileList, LinkList]]
DirTree = Dict[str, DirDescriptor]

# Example for a DirTree
# {
#     "test/a": {
#         "files": [
#             {
#                 "name": "name.bla",
#                 "permission": 600,
#                 "rootuser": True,
#                 "rootgroup": True,
#                 "content": "b37b8487ac0b8f01e9e34949717b16d1"
#             }
#         ],
#         "links": [
#             {
#                 "name": "name.bla1",
#                 "target": "~/dotfiles/files/name1",
#                 "permission": 600,
#                 "rootuser": True,
#                 "rootgroup": True
#             },
#             {
#                 "name": "test.link",
#                 "target": "~/dotfiles/files/test",
#                 "permission": 777,
#                 "rootuser": False,
#                 "rootgroup": False
#             }
#         ],
#         "permission": 777,
#         "rootuser": True,
#         "rootgroup": True
#     },
#     "test/b": {...},
#     "test/b/c": {...},
# }
# Where the content property is optional for files


class RegressionTest():
    """This is the abstract base class for all regression tests.
    It provides simple start and check functionality"""
    def __init__(self, name: str, cmd_args: List[str], cleanup: bool = True):
        self.name = name
        self.cmd_args = ["../dotmanager.py"] + cmd_args
        self.cleanup = cleanup

    def start(self) -> TestResult:
        """Starts the test and runs all checks"""
        if self.cleanup:
            self.clean()
        pre_result, pre_cause = self.pre_check()
        if not pre_result:
            return {"success": False, "phase": "pre", "cause": pre_cause}
        process = Popen(self.cmd_args + ["--config", "test.ini"], stderr=PIPE)
        run_cause = process.communicate()
        if process.returncode != 0:
            return {"success": False, "phase": "run", "cause": run_cause}
        post_result, post_cause = self.post_check()
        if not post_result:
            return {"success": False, "phase": "post", "cause": post_cause}
        return {"success": True}

    def clean(self) -> None:
        pass

    @abstractmethod
    def pre_check(self) -> CheckResult:
        """The check executed before the test to make sure the test is
        run on the correct preconditions"""
        pass

    @abstractmethod
    def post_check(self) -> CheckResult:
        """The check executed after the test to make sure the test
        behave like expected"""
        pass

    def success(self) -> bool:
        """Execute this test. Expect it to be successful"""
        result = self.start()
        print(self.name + ": ", end="")
        if result["success"]:
            print('\033[92m' + "Ok" + '\033[0m')
        else:
            print('\033[91m\033[1m' + "FAILED" + '\033[0m'
                  + " in " + result["phase"])
            print("Cause: " + result["cause"])
        return result["success"]

    def fail_with_err(self, fail_result: TestResult) -> bool:
        """Execute this test. Expect a certain error"""
        result = self.start()
        print(self.name + ": ", end="")
        if not result["success"]:
            if result["cause"] != fail_result["cause"]:
                print('\033[91m\033[1m' + "FAILED!" + '\033[0m'
                      + " Expected error: " + fail_result["cause"]
                      + " but got error: " + result["cause"])
            else:
                print('\033[92m' + "Ok" + '\033[0m')
        else:
            print('\033[91m\033[1m' + "FAILED!" + '\033[0m'
                  + " Expected error in " + fail_result["phase"])
            print("Expected cause: " + result["cause"])
        return not result["success"]


class DirRegressionTest(RegressionTest):
    """Regression check if Dotmanager makes the expected
    changes to the filesystem"""
    def __init__(self, name: str, cmd_args: str, before: DirTree,
                 after: DirTree, cleanup: bool = True):
        super().__init__(name, cmd_args, cleanup)
        self.before = before
        self.after = after

    @staticmethod
    def dircheck(dir_tree: DirTree) -> CheckResult:
        """Checks if dir_tree matches the actual directory
        tree in the filesystem"""

        def check_owner(path: str, props: Union[DirDescriptor,
                                                LinkDescriptor,
                                                FileDescriptor],
                        is_link: bool = False) -> None:
            """For owner permissions we only look up if its a normal
            user or the root user because we can't create other
            users just for the sake of these tests"""
            stat = os.lstat if is_link else os.stat
            if bool(stat(path).st_uid) == props["rootuser"]:
                user = "user" if props["rootuser"] else "root"
                raise ValueError((False, f"{path} is a not owned by {user}"))
            if bool(stat(path).st_gid) == props["rootgroup"]:
                group = "group" if props["rootgroup"] else "root"
                raise ValueError((False, f"{path} is a not owned by {group}"))

        def check_permission(path: str, permission: int) -> None:
            perm_real = str(oct(os.stat(path).st_mode))[-3:]
            if perm_real != str(permission):
                raise ValueError((False, f"{path} has permission {perm_real}"))

        for dir_name, dir_props in dir_tree:
            # Directory existance
            if not os.path.isdir(dir_name):
                raise ValueError((False, dir_name + " is a not a directory"))
            # Directory permission
            check_permission(dir_name, dir_props["permission"])
            # Directory owner
            check_owner(dir_name, dir_props)
            # Files
            for file_props in dir_props["files"]:
                file_path = os.path.join(dir_name, file_props["name"])
                # File existance
                if not os.path.isfile(file_path):
                    raise ValueError((False, f"{file_path} is a not a file"))
                # File permission
                check_permission(file_path, file_props["permission"])
                # File owner
                check_owner(file_path, file_props)
                # File content
                md5 = hashlib.md5(open(file_path, "rb").read()).hexdigest()
                if "content" in file_props and md5 != file_props["content"]:
                    raise ValueError((False, f"{file_path} has wrong content"))
            # Links
            for link_props in dir_props["links"]:
                link_path = os.path.join(dir_name, link_props["name"])
                # Link existance
                if not os.path.islink(link_path):
                    raise ValueError((False, f"{link_path} is a not a link"))
                # Link permission
                check_permission(link_path, link_props["permission"])
                # Link owner
                check_owner(link_path, link_props, True)
                # Link target
                target_path = os.path.normpath(os.readlink(link_path))
                if target_path != os.path.normpath(link_props["target"]):
                    msg = f"{link_path} should point to {link_props['target']}"
                    msg += ", but points to {target_path}"
                    raise ValueError((False, msg))

    def pre_check(self) -> CheckResult:
        try:
            self.dircheck(self.before)
        except ValueError as err:
            return err.args[0]
        return (True, "")

    def post_check(self) -> CheckResult:
        try:
            self.dircheck(self.after)
        except ValueError as err:
            return err.args[0]
        return (True, "")
