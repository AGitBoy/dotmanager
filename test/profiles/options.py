"""This module collects all profiles that are used to test the options"""
from dotmanager.profile import Profile

class NoOptions(Profile):
    def generate(self):
        link("name1", "name2", "name3")

class DirOption(Profile):
    def generate(self):
        link("name1")
        link("name2", directory="subdir")
        link("name3", directory="subdir/subsubdir")
        cd("subdir")
        link("name4", directory="subsubdir")
        link("name5", directory="..")
        links("name[67]", directory="../subdir2")

class NameOption(Profile):
    def generate(self):
        link("name1", name="name")
        link("name2", name="subdir/name")
        link("name3", directory="subdir", name="subsubdir/name")
        cd("subdir")
        link("name5", name="../name6", directory="subsubdir")
