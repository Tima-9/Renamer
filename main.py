import mutagen
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3
import asyncio
import console
import json
import colorama
from colorama import Fore, Style
import os
import re

# all init
colorama.init(autoreset=True)
server_cycle = False
# open config with text
with open('config.json', 'r', encoding="utf-8") as file:
    config = json.load(file)


def limit_word(word, max_len):
    """
    set limits to word
    example:
    12345 : 12345
    123456789 : 123...
    """
    length = len(word)
    word__condition = length > max_len
    return (word[:((max_len - length - 3) if word__condition else max_len)] +  # '-3' to fix bug with useless chars
            ("..." if word__condition else " " * (max_len - length)))


class Renamer:
    def __init__(self, patterns__: str | re.Pattern, folder__path: str, pattern__names__: list[str] = None):
        self.patterns = re.compile(patterns__)
        self.pattern_names = (re.findall(r"\?P<(\w+)>", self.patterns.pattern)
                              if pattern__names__ is None else pattern__names__)
        self.path = folder__path

    @staticmethod
    def assign_arguments(argument: dict[str: list[str], str: list[str], str: list[str]] = None):
        def decorator(function):
            def wrapper(self__, input__command__: str, *args_, **kwargs_):
                # clear less spaces
                # 1,  2, 3, 4,5 --> 1,2,3,4,5
                # command_name -a  -b      --c c_args --> command_name -a -b --c c_args
                command = re.sub(r",\s+", ",", re.sub(r"\s+", " ", input__command__))
                # find default command arguments --> int, str and etc
                command_arguments = re.findall(r"\s(?<!-)+(\S+)", command)
                # find args --> -name
                args = re.findall(r"(?<!-)-[a-zA-Z_]+", command)
                # find kwargs --> --name value
                kwargs = {kwarg[0]: kwarg[1] for kwarg in re.findall(r"(--\w+)\s((?!-+[a-zA-Z]+)\S+)?", command)}
                # check if all commands ar in common
                if argument is not None:
                    if "command_arguments_count" in argument:
                        if len(command_arguments) > argument["command_arguments_count"]:
                            raise NameError(f"Excepted {argument['command_arguments_count']} argument(s) "
                                            f"but {len(command_arguments)} got")
                    if "args" in argument:
                        for arg_name in args:
                            if not (arg_name in argument["args"]):
                                raise NameError(f"arg: {arg_name} is not declarated")
                    if "kwargs" in argument:
                        for kwarg_name in kwargs:
                            if not (kwarg_name in argument["kwargs"]):
                                raise NameError(f"kwarg: {kwarg_name} is not declarated")
                # call function
                # TODO: add default values to dict
                result = function(self__, {
                    "command_arguments": command_arguments,
                    "args": args,
                    "kwargs": kwargs
                }, *args_, **kwargs_)
                return result

            return wrapper

        return decorator

    @assign_arguments({
        "args": ["-fix", "-show_correct"],
        "kwargs": ["--select"],
    })
    async def analize(self, input_command: str | dict[str: list[str]]):
        """analize all files in folder"""
        files_and_dirs = os.listdir(self.path)
        files = [os.path.join(self.path, f) for f in files_and_dirs if os.path.isfile(os.path.join(self.path, f))]
        # check if arg in function
        refresh = "-fix" in input_command["args"]

        # input command: diff --select 1
        # index check
        def selector_check(value: int) -> bool:
            """
            :param value: integer | integer:integer 'range' | integer,integer... 'couple'
            """
            if "--select" in input_command["kwargs"]:
                # replace less spaces: diff --select 1,  2,3, 4 --> diff --select 1,2,3,4
                command = re.sub(r",\s+", ",", re.sub(r"\s+", " ", input_command["kwargs"]["--select"]))
                pattern = re.compile(r'(?P<range>\d+:\d+)|(?P<couple>\d+(?:(?:,\d+)?)+)')
                # pattern searches: for example ['1:2', None]
                # remove None from searches
                arg = {"name": "", "value": None}
                for name_ in ["range", "couple"]:
                    search = pattern.search(command)
                    if search is not None:
                        if search.group(name_) is not None:
                            # arg (example): 1,2,3,4 | 1 | 1:2
                            arg = {"name": name_, "value": search.group(name_)}

                # match type of search
                match arg["name"]:
                    case "range":
                        indexes = list(map(lambda x: int(x), arg["value"].split(":")))
                        return any(list(map(lambda x: int(x) == value, list(range(min(indexes), max(indexes) + 1)))))
                    case "couple":
                        return any(list(map(lambda x: int(x) == value, arg["value"].split(","))))
                    case _:
                        if "*" == input_command["kwargs"]["--select"] or "" == input_command["kwargs"]["--select"]:
                            return True
                        return False
            else:
                return True

        errors_count = 0
        for i, file_name in enumerate(files):
            if selector_check(i + 1):
                # if file broken, fix it
                try:
                    ID3(file_name)
                except mutagen.MutagenError:
                    tags = ID3()
                    os.remove(file_name)
                    tags.save(file_name)
                # get file for attributes
                audio = EasyID3(file_name)

                # search with patterns
                searches = [self.patterns.search(audio[value_type][0]) for value_type in audio]
                # bool if something detected
                searches__bool__result = any([condition for search in searches if (condition := search is not None)])
                if searches__bool__result:
                    # get some data
                    song_name = audio["title"][0]
                    song_name__printable = limit_word(song_name, 15)
                    # get error name
                    error = {"error_name": "", "value": None}
                    for name in self.pattern_names:
                        search = [s for s in searches if s is not None][0]
                        if search is not None:
                            if search.group(name) is not None:
                                error = {"error_name": name, "value": search.group(name)}
                    # message for future send
                    analyze_message: str = config["analyzing"]["name/num/message"]
                    console_.log(analyze_message.format(
                        color1=Fore.BLUE,
                        file_name=song_name__printable,
                        color2=Fore.CYAN,
                        color_reset=Fore.RESET,
                        num=i + 1,
                        color3=Fore.RED,
                        message=f"Pattern [{error['error_name']}] detected"
                    ))

                    first_line: str = config["analyzing"]["first_line"]
                    console_.log(first_line.format(
                        style1=Style.BRIGHT,
                        color1=Fore.BLUE,
                        color_reset=Fore.RESET,
                        style_reset=Style.RESET_ALL
                    ))
                elif "-show_correct" in input_command["args"]:
                    # get some data
                    song_name = audio["title"][0]
                    song_name__printable = limit_word(song_name, 15)
                    # message for future send
                    analyze_message: str = config["analyzing"]["name/num/message"]
                    console_.log(analyze_message.format(
                        color1=Fore.BLUE,
                        file_name=song_name__printable,
                        color2=Fore.CYAN,
                        color_reset=Fore.RESET,
                        num=i + 1,
                        color3=Fore.GREEN,
                        message="All right"
                    ))

                # print warnings\messages
                for search, value_type in zip(searches, audio):
                    # if search result is not nothing
                    if search is not None:
                        warn_message1: str = config["analyzing"]["warning/message:1"]
                        console_.log(warn_message1.format(
                            style1=Style.BRIGHT,
                            color1=Fore.BLUE,
                            value1=value_type,
                            color_reset=Fore.RESET,
                            style_reset=Style.RESET_ALL,
                            value2=audio[value_type][0]
                        ))

                        warn_message2: str = config["analyzing"]["warning/message:2"]
                        console_.log(warn_message2.format(
                            style1=Style.BRIGHT,
                            color1=Fore.BLUE,
                            color_2=Fore.RED,
                            style_reset=Style.RESET_ALL,
                            spaces_count=(search.span()[0] + len(value_type) - 5) * ' ',
                            symbol_count=(search.span()[1] - search.span()[0]) * '^',
                            message="PATTERN"
                        ))

                if searches__bool__result:
                    help_message: str = config["analyzing"]["help_message"]
                    console_.log(help_message.format(
                        style1=Style.BRIGHT,
                        color1=Fore.BLUE,
                        color2=Fore.CYAN,
                        color_reset=Fore.RESET,
                        style_reset=Style.RESET_ALL,
                        message="Remove this ball shit"
                    ))

                if refresh and selector_check(i + 1):
                    for value_type in audio:
                        if len(audio[value_type]) > 0:
                            audio[value_type] = self.patterns.sub("", audio[value_type][0]).strip()
                    audio.save()
                    errors_count += 1
        else:
            if refresh:
                console_.log(f"Fixed ({errors_count}) errors")

    @assign_arguments({
        "command_arguments_count": 1
    })
    async def set_path(self, input_command: str | dict[str: list[str]]):
        # get & set path to local value
        self.path = input_command["command_arguments"][0]

    @assign_arguments({
        "command_arguments_count": 2
    })
    async def add_pattern(self, input_command: str | dict[str: list[str]]):
        # get pattern properties
        pattern_name, pattern_value = input_command['command_arguments']
        # add new pattern to main one
        self.patterns = re.compile(rf"{self.patterns.pattern}|(?P<{pattern_name}>{pattern_value})")
        # add it`s name to local list
        self.pattern_names.append(pattern_name)

    @assign_arguments({
        "command_arguments_count": 1
    })
    async def del_pattern(self, input_command: str | dict[str: list[str]]):
        # pattern to delete name
        pattern_name = input_command['command_arguments'][0]
        # get list of patters
        patterns_list = re.split(r"[|](?=[(])", self.patterns.pattern)
        # get index of element you want to delete
        index_to_delete = self.pattern_names.index(pattern_name)
        # delete name in both lists with names & values
        patterns_list.pop(index_to_delete)
        self.pattern_names.pop(index_to_delete)
        # save edits on main variable with patterns
        self.patterns = re.compile("|".join(patterns_list))

    @assign_arguments({
        "command_arguments_count": 2
    })
    async def edit_pattern(self, input_command: str | dict[str: list[str]]):
        # pattern to delete name
        pattern_name, pattern_value = input_command['command_arguments']
        # get list of patters
        patterns_list = re.split(r"[|](?=[(])", self.patterns.pattern)
        # get index of element you want to delete
        index_to_delete = self.pattern_names.index(pattern_name)
        # delete name in both lists with names & values
        patterns_list[index_to_delete] = rf"(?P<{pattern_name}>{pattern_value})"
        # save edits on main variable with patterns
        self.patterns = re.compile("|".join(patterns_list))


async def main():
    """Main function"""
    input_task = asyncio.create_task(console_.input_loop())
    _done, pending = await asyncio.wait([input_task], return_when=asyncio.FIRST_COMPLETED)
    for task in pending:
        task.cancel()


if __name__ == '__main__':
    # TODO: async, console
    # patterns = re.compile(r"(?P<name1>.?\b\S+\.(?:fm|net|me)\b.)|(?P<name2>360media(\.(?:com|ng))+)")
    patterns = re.compile(r"(?P<name1>.?\b\S+\.(?:fm|net|me)\b.)|(?P<name2>360media(\.(?:com|ng))+)")
    patterns_names: list[str] = ["name1", "name2"]
    folder_path_ = r"Tests\old_names"  # for tests: C:\Users\Tima\Music
    # you can use class call without pattern-names
    # *they will set up automatically*
    renamer = Renamer(patterns, folder_path_, pattern__names__=patterns_names)

    # example of using functions
    r"""
    renamer.add_pattern(r"add_pattern new_pattern 360media(\.(?:com|ng))+")
    renamer.analize("diff abcd --select * -show_correct")
    renamer.set_path(r"set_path Test\old_names")
    renamer.edit_pattern(r"edit new_pattern \b1\b")
    renamer.analize("diff abcd --select * -show_correct")
    """

    console_ = console.CommandLine(f"{Fore.CYAN}>>> ", {
        "diff": renamer.analize,
        "set_path": renamer.set_path,
        "add_pattern": renamer.add_pattern,
        "del_pattern": renamer.del_pattern,
        "edit_pattern": renamer.edit_pattern,
        "exit": console.break_console
    })

    asyncio.run(main())
