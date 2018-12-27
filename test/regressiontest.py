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
FileList = List[Dict[str, Union[bool, int, str]]]
DirTree = Dict[str, Dict[str, Union[bool, int, FileList]]]

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
#                 "permission": 600,
#                 "rootuser": True,
#                 "rootgroup": True
#             },
#             {
#                 "name": "test.link",
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
# Where the content property for files is optional


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

        owd = os.getcwd()
        for dir_name, dir_props in dir_tree:
            # Directory existance
            if not os.path.isdir(dir_name):
                return (False, dir_name + " is a not a directory")
            # Directory permission

            # Directory owner
            # For owner permissions we only look up if its a normal
            # user or the root user because we can't create other
            # users just for the sake of these tests
            if bool(os.stat(dir_name).st_uid) == dir_props["rootuser"]:
                user = "user" if dir_props["rootuser"] else "root"
                return (False, dir_name + " is a not owned by " + user)
            if bool(os.stat(dir_name).st_gid) == dir_props["rootgroup"]:
                group = "group" if dir_props["rootgroup"] else "root"
                return (False, dir_name + " is a not owned by " + group)
            os.chdir(dir_name)
            # Files
            for file_props in dir_props["files"]:
                file_path = os.path.join(dir_name, file_props["name"])
                # File existance
                if not os.path.isfile(file_path):
                    return (False, file_path + " is a not a file")
                # File permission
                # File owner
                if bool(os.stat(file_path).st_uid) == file_props["rootuser"]:
                    user = "user" if file_props["rootuser"] else "root"
                    return (False, file_path + " is a not owned by " + user)
                if bool(os.stat(file_path).st_gid) == file_props["rootgroup"]:
                    group = "group" if file_props["rootgroup"] else "root"
                    return (False, file_path + " is a not owned by " + group)
                # File content
            # Links
            for link_props in dir_props["links"]:
                link_path = os.path.join(dir_name, link_props["name"])
                # Link existance
                if not os.path.islink(link_path):
                    return (False, link_path + " is a not a link")
                # Link permission
                # Link owner
                if bool(os.lstat(link_path).st_uid) == link_props["rootuser"]:
                    user = "user" if link_props["rootuser"] else "root"
                    return (False, link_path + " is a not owned by " + user)
                if bool(os.lstat(link_path).st_gid) == link_props["rootgroup"]:
                    group = "group" if link_props["rootgroup"] else "root"
                    return (False, link_path + " is a not owned by " + group)
            os.chdir(owd)
        return (True, "")

    def pre_check(self) -> CheckResult:
        return self.dircheck(self.before)

    def post_check(self) -> CheckResult:
        return self.dircheck(self.after)
