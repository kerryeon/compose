import collections
import paramiko


def import_helper(name: str, attr: str):
    try:
        module = __import__(f'services.{name}.helper', fromlist=[attr])
        return getattr(module, attr)
    except:
        return None


class Volume:
    def __init__(self, name: str, type: str):
        self.name = name
        self.type = type

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        type = str(context['type'])
        return Volume(name, type)


class Node:
    def __init__(self, id: int, name: str,
                 username: str, password: str,
                 volumes: dict):
        self.id = id
        self.name = name
        self.username = username
        self.password = password
        self.volumes = volumes

    def node_ip(self, plane: str) -> str:
        return f'{plane}.{self.id}'

    def command(self, logger, plane: str, script: str,
                env: dict, timeout: bool = False):
        env = '\n'.join(f'export {k}={v}' for k, v in env.items())
        script = env + '\n' + script.replace('\\\n', ' ')
        timeout = 15 if timeout else None

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.node_ip(plane),
                       username=self.username,
                       password=self.password)

        stdin, stdout, stderr = client.exec_command(
            script, get_pty=True, timeout=timeout)
        output = stdout.readlines()
        for line in output:
            logger.debug(line[:-1])
        for line in stderr.readlines():
            logger.error(line[:-1])
        stdin.close()
        client.close()
        return output

    def upload(self, logger, plane: str, files: dict):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.node_ip(plane),
                       username=self.username,
                       password=self.password)

        ftp_client = client.open_sftp()
        for src, dst in files.items():
            logger.debug(f'Upload file: {src} --> {dst}')
            ftp_client.put(src, dst)
        ftp_client.close()
        client.close()

    @classmethod
    def parse(cls, context: dict):
        id = int(context['id'])
        name = str(context['name'])
        username = str(context['username'])
        password = context.get('password')
        password = str(password) if password is not None else password
        volumes = {v.name: v for v in [
            Volume.parse(v) for v in context['volumes']]}
        return Node(id, name, username, password, volumes)


class Nodes:
    def __init__(self, master: str, data: dict):
        self.master = master
        self.data = data

    def node_ip(self, name: str, plane: str) -> str:
        return self.data[name].node_ip(plane)

    def master_node_ip(self, plane: str) -> str:
        return self.node_ip(self.master, plane)

    def all(self) -> list:
        return list(self.data.keys())

    def workers(self) -> list:
        return [n for n in self.data if n != self.master]

    def volumes(self, name: str) -> dict:
        return self.data[name].volumes

    def command(self, logger, name: str, plane: str, script: str,
                env: dict, timeout: bool = False):
        return self.data[name].command(logger, plane, script, env, timeout)

    def upload(self, logger, name: str, plane: str, files: dict):
        return self.data[name].upload(logger, plane, files)

    @classmethod
    def parse(cls, context: dict):
        master = str(context['master'])
        data = {n.name: n for n in [
            Node.parse(n) for n in context['desc']]}
        return Nodes(master, data)


class Planes:
    def __init__(self, data: dict):
        self.data = data
        self.primary = 'maintain'

    @property
    def maintain(self) -> str:
        return self.data['maintain']

    @property
    def primary_value(self) -> str:
        return self.data[self.primary]

    @classmethod
    def parse(cls, context: dict):
        data = {str(k): str(v) for k, v in context.items()}
        return Planes(data)


class Service:
    def __init__(self, name: str, version: str, desc: dict):
        self.name = name
        self.version = version
        self.desc = desc

    def collect_dependencies(self) -> set:
        collector = import_helper(self.name, 'collect_dependencies')
        return collector(self) if collector is not None else set()

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        version = str(context['version'])
        desc = context.get('desc')
        desc = dict(desc) if desc is not None else {}
        return Service(name, version, desc)


class Services:
    def __init__(self, data: dict):
        self.data = data

    def all(self):
        return self.data.items()

    def collect_dependencies(self) -> set:
        result = set()
        for name, service in self.data.items():
            result.add(name)
            result = result.union(service.collect_dependencies())
        return result

    @classmethod
    def parse(cls, context: dict):
        data = {s.name: s for s in [
            Service.parse(s) for s in context]}
        return Services(data)


class Config:
    def __init__(self, logger, nodes: Nodes, planes: Planes,
                 services: Services, benchmark: str):
        self.nodes = nodes
        self.planes = planes
        self.services = services
        self.benchmark = benchmark

        self.logger = logger

    def master_node_ip(self):
        return self.nodes.master_node_ip(self.planes.primary_value)

    def node_ip(self, name: str):
        return self.nodes.node_ip(name, self.planes.primary_value)

    def volumes(self, name: str) -> dict:
        return self.nodes.volumes(name)

    def collect_dependencies(self) -> set:
        default = {'docker', 'kubernetes', self.benchmark}
        result = default.union(self.services.collect_dependencies())
        return result

    def command(self, name: str, script: str, timeout: bool = False, **env):
        return self.nodes.command(self.logger, name, self.planes.maintain, script, env, timeout)

    def command_master(self, script: str, timeout: bool = False, **env):
        env = {k: str(v) for k, v in env.items()}
        return self.nodes.command(self.logger, self.nodes.master, self.planes.maintain, script, env, timeout)

    def command_all(self, script: str, timeout: bool = False, **env):
        env = {k: str(v) for k, v in env.items()}
        return [(worker, self.nodes.command(self.logger, worker, self.planes.maintain, script, env, timeout))
                for worker in self.nodes.data]

    def upload_master(self, files: dict):
        return self.nodes.upload(self.logger, self.nodes.master, self.planes.maintain, files)

    @classmethod
    def parse(cls, context: dict, logger):
        nodes = Nodes.parse(context['nodes'])
        planes = Planes.parse(context['planes'])
        services = Services.parse(context['services'])
        benchmark = str(context['benchmark'])
        return Config(logger, nodes, planes, services, benchmark)

    @classmethod
    def load(cls, path: str, logger):
        logger.info(f'Loading config: {path}')
        import yaml
        with open(path) as f:
            context = yaml.load(f, Loader=yaml.FullLoader)
        return Config.parse(context, logger)
