import typing


def dict_merge(dict1: dict[str, typing.Any], dict2: dict[str, typing.Any]) -> None:
    for key in dict2.keys():
        if key in dict1:
            if isinstance(dict1[key], dict) and isinstance(dict2[key], dict):
                dict_merge(dict1[key], dict2[key])
        else:
            dict1[key] = dict2[key]


class ClassProperty:
    # ruff: noqa: ANN401
    def __init__(self, function: typing.Any) -> None:
        self.function: typing.Any = classmethod(function)

    def __get__(self, *args: typing.Any) -> typing.Any:
        return self.function.__get__(*args)()
