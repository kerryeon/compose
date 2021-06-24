import functools
import operator
import tqdm

import context
import service


class SettingCase:
    def __init__(self, values: dict):
        self.values = values

    def condition(self, key: str, value: object):
        return SettingCase({key: value, **self.values})

    def patch(self, config: context.Config):
        def resolve(path: str, target):
            paths, targets = path.split('.'), [config]
            for path in paths:
                if isinstance(target, context.Services):
                    target = target.data[path]
                elif isinstance(target, dict):
                    target = target.get(path)
                elif isinstance(target, list):
                    found = False
                    for child in target:
                        if child['name'] == path:
                            found = True
                            target = child
                            break
                    if not found:
                        raise Exception(
                            f'failed to find instance from settings: {path}')
                else:
                    target = getattr(target, path)
                targets.append(target)
            return paths[-1], targets[-2], targets[-1]

        def replace(parent, key: str, value):
            if isinstance(parent, dict):
                parent[key] = value
            else:
                setattr(parent, key, value)

        config.logger.info(f'Doing patch')
        for name, value in self.values.items():
            key, parent, original = resolve(name, config)
            replace(parent, key, value)
            key, parent, original = resolve(name, config.context)
            replace(parent, key, value)
            config.logger.info(
                f'Patched \'{name}\': {repr(original)} --> {repr(value)}')
        print(config.context)
        exit(1)

    def __repr__(self) -> str:
        return repr(self.values)


class SettingValue:
    def __init__(self, value: object, children: list):
        self.value = value
        self.children = children

    def all(self, key: str, parents: list) -> list:
        if not parents:
            parents = [SettingCase({key: self.value})]
        else:
            parents = [p.condition(key, self.value) for p in parents]

        for child in self.children:
            parents = child.all(parents)
        return parents

    def __len__(self):
        return functools.reduce(operator.mul, (len(c) for c in self.children), 1)


class SettingNode:
    def __init__(self, name: str, values: list, is_atomic: bool):
        self.name = name
        self.values = values
        self.is_atomic = is_atomic

    def all(self, parents: list) -> list:
        if self.is_atomic:
            if not parents:
                return [SettingCase({self.name: v.value}) for v in self.values]
            return [p.condition(self.name, v.value) for p in parents for v in self.values]
        return sum((v.all(self.name, parents) for v in self.values), start=[])

    def __len__(self):
        if self.is_atomic:
            return len(self.values)
        return sum(len(v) for v in self.values)

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])

        values = context.get('values')
        if isinstance(values, list):
            values = [SettingValue(v, []) for v in values]
            return SettingNode(name, values, True)

        conditions = context.get('conditions')
        if isinstance(conditions, list):
            values = []
            for condition in conditions:
                children = [SettingNode.parse(c)
                            for c in condition['children']]
                values += [SettingValue(v, children)
                           for v in condition['values']]
            return SettingNode(name, values, False)

        raise Exception('malformed settings')


class Settings:
    def __init__(self, name: str, children: list, config: context.Config):
        self.name = name
        self.children = children
        self.config = config

        self.config.logger.info(f'Total settings: {len(self)}')
        self.config.mute_logger()

    def all(self) -> list:
        parents = []
        for child in self.children:
            parents = child.all(parents)
        return parents

    def solve(self):
        for case in tqdm.tqdm(self.all()):
            config = case.patch(self.config)
            service.solve(config)

    def __len__(self):
        return functools.reduce(operator.mul, (len(c) for c in self.children), 1)

    @classmethod
    def load(cls, name: str, context: list, config: context.Config):
        config.logger.info(f'Loading settings: {name}')
        children = [SettingNode.parse(c) for c in context]
        return Settings(name, children, config)
