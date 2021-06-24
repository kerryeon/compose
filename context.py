from datetime import datetime
import logging
import paramiko
import os
import sys
import time
import yaml

LOGGER = None
LOGGER_FS = None


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
        self.desc = {}

        self.usable = True

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        type = str(context['type'])
        return Volume(name, type)


class Node:
    def __init__(self, id: int, name: str,
                 username: str, password: str,
                 volumes: list):
        self.id = id
        self.name = name
        self.username = username
        self.password = password
        self.volumes = volumes

    def node_ip(self, plane: str) -> str:
        return f'{plane}.{self.id}'

    def command(self, logger, plane: str, script: str,
                env: dict, timeout: int, quiet: bool):
        env = '\n'.join(f'export {k}="{v}"' for k, v in env.items())
        script = env + '\n' + script.replace('\\\n', ' ')

        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.node_ip(plane),
                       username=self.username,
                       password=self.password)

        try:
            stdin, stdout, stderr = client.exec_command(
                script, get_pty=True, timeout=timeout)
        except paramiko.ssh_exception.SSHException as e:
            print(e, file=sys.stderr)
            raise Exception(f'Failed to connect to the node: {self.name}')

        outputs = []
        while True:
            escape = stdout.channel.eof_received
            while stdout.channel.recv_ready():
                line = stdout.readline()[:-1]
                if not quiet:
                    logger.debug(line)
                    outputs.append(line)
            while stderr.channel.recv_ready():
                line = stderr.readline()
                if not quiet:
                    logger.error(line)
            if escape:
                break
            time.sleep(0.01)
        stdin.close()
        client.close()
        return outputs

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

    def download(self, logger, plane: str, files: dict):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.node_ip(plane),
                       username=self.username,
                       password=self.password)

        ftp_client = client.open_sftp()
        for dst, src in files.items():
            logger.debug(f'Upload file: {src} --> {dst}')
            ftp_client.get(dst, src)
        ftp_client.close()
        client.close()

    @classmethod
    def parse(cls, context: dict):
        id = int(context['id'])
        name = str(context['name'])
        username = str(context['username'])
        password = context.get('password')
        password = str(password) if password is not None else password
        volumes = [Volume.parse(v) for v in context['volumes']]
        return Node(id, name, username, password, volumes)


class NodeMaster:
    def __init__(self, name: str, taint: bool):
        self.name = name
        self.taint = taint

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        taint = context.get('taint')
        taint = bool(taint) if taint is not None else False
        return NodeMaster(name, taint)


class Nodes:
    def __init__(self, master: NodeMaster, data: dict):
        self.master = master
        self.data = data

    def node_ip(self, name: str, plane: str) -> str:
        return self.data[name].node_ip(plane)

    def master_node_ip(self, plane: str) -> str:
        return self.node_ip(self.master.name, plane)

    def all(self) -> list:
        return list(self.data.keys())

    def workers(self) -> list:
        return [n for n in self.data if n != self.master.name]

    def volumes(self, name: str) -> list:
        return self.data[name].volumes

    def volumes_by_type(self, name: str, type: str) -> list:
        return [v for v in self.data[name].volumes if v.type == type]

    def command(self, logger, name: str, plane: str, script: str,
                env: dict, timeout: int, quiet: bool):
        return self.data[name].command(logger, plane, script, env,
                                       timeout, quiet)

    def upload(self, logger, name: str, plane: str, files: dict):
        return self.data[name].upload(logger, plane, files)

    def download(self, logger, name: str, plane: str, files: dict):
        return self.data[name].download(logger, plane, files)

    @classmethod
    def parse(cls, context: dict):
        master = NodeMaster.parse(context['master'])
        data = {n.name: n for n in [
            Node.parse(n) for n in context['desc']]}
        return Nodes(master, data)


class Planes:
    def __init__(self, data: dict):
        self.data = data
        self.primary = 'control'

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
    def __init__(self, name: str, version: str, desc: object):
        self.name = name
        self.version = version
        self.desc = desc
        self.enabled = True

    def collect_dependencies(self) -> set:
        collector = import_helper(self.name, 'collect_dependencies')
        return collector(self) if collector is not None else set()

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        version = str(context['version'])
        desc = context.get('desc')
        desc = desc if desc is not None else {}
        return Service(name, version, desc)


class Services:
    def __init__(self, data: dict):
        self.data = data

    def all(self):
        return {k: v for k, v in self.data.items() if v.enabled}

    def collect_dependencies(self) -> set:
        result = set()
        for name, service in self.all():
            result.add(name)
            result = result.union(service.collect_dependencies())
        return result

    @classmethod
    def parse(cls, context: dict):
        data = {s.name: s for s in [
            Service.parse(s) for s in context]}
        return Services(data)


class Benchmark:
    def __init__(self, name: str, data: dict):
        self.name = name
        self.data = data

    @classmethod
    def parse(cls, context):
        if isinstance(context, str):
            name = context
            data = {'name': name}
        elif isinstance(context, dict):
            name = str(context['name'])
            data = context
        else:
            raise Exception(f'malformed benchmark: Given type {type(context)}')
        return Benchmark(name, data)


class Config:
    def __init__(self, context: dict, logger, logger_fs,
                 work_time: str, work_name: str,
                 nodes: Nodes, planes: Planes,
                 services: Services, benchmark: Benchmark):
        self.nodes = nodes
        self.planes = planes
        self.services = services
        self.benchmark = benchmark

        self.work_time = work_time
        self.work_name = work_name

        self.context = context
        self.logger = logger
        self.logger_fs = logger_fs

    def master_node_ip(self):
        return self.nodes.master_node_ip(self.planes.primary_value)

    def node_ip(self, name: str):
        return self.nodes.node_ip(name, self.planes.primary_value)

    def volumes(self, name: str) -> list:
        return self.nodes.volumes(name)

    def volumes_by_type(self, name: str, type: str) -> list:
        return self.nodes.volumes_by_type(name, type)

    def volumes_str(self, name: str) -> str:
        return ' '.join(f'/dev/{v.name}' for v in self.volumes(name))

    def collect_dependencies(self) -> set:
        default = {'docker', 'kubernetes'}
        result = default.union(self.services.collect_dependencies())
        if self.benchmark is not None:
            default.add(self.benchmark)
        return result

    def command(self, name: str, script: str, timeout: int = None, quiet: bool = False, **env):
        return self.nodes.command(self.logger, name,
                                  self.planes.maintain, script, env,
                                  timeout, quiet)

    def command_master(self, script: str, timeout: int = None, quiet: bool = False, **env):
        env = {k: str(v) for k, v in env.items()}
        return self.nodes.command(self.logger, self.nodes.master.name,
                                  self.planes.maintain, script, env,
                                  timeout, quiet)

    def command_all(self, script: str, timeout: int = None, quiet: bool = False, **env):
        env = {k: str(v) for k, v in env.items()}
        return [(worker, self.nodes.command(self.logger, worker,
                                            self.planes.maintain, script, env,
                                            timeout, quiet))
                for worker in self.nodes.data]

    def upload_master(self, files: dict):
        return self.nodes.upload(self.logger, self.nodes.master.name, self.planes.maintain, files)

    def download_master(self, files: dict):
        return self.nodes.download(self.logger, self.nodes.master.name, self.planes.maintain, files)

    @classmethod
    def parse(cls, name: str, context: dict, logger):
        benchmark = context.get('benchmark')
        benchmark = Benchmark.parse(
            benchmark) if benchmark is not None else None

        work_time = datetime.now().strftime('Y%YM%mD%d-H%HM%MS%S')
        work_name = benchmark.name if benchmark is not None else 'compose'
        work_name = f'{work_name}-{work_time}'

        nodes = Nodes.parse(context['nodes'])
        planes = Planes.parse(context['planes'])
        services = Services.parse(context['services'])

        logger_fs = cls._init_logger_fs(work_name)
        logger_fs.info(f'Loading config: {name}')
        return Config(context, logger, logger_fs, work_time, work_name,
                      nodes, planes, services, benchmark)

    @classmethod
    def load(cls, name: str, context: dict):
        logger = cls._init_logger()
        logger.info(f'Loading config: {name}')
        return Config.parse(name, context, logger)

    def save(self, path: str):
        with open(path, 'w') as f:
            yaml.dump(self.context, f, Dumper=yaml.SafeDumper)

    def mute_logger(self):
        handler = self.logger.handlers[0]
        handler.flush()
        handler.stream = open(os.devnull, 'w')

    @classmethod
    def _create_logger(cls, stream, level, *, name=None):
        handler = logging.StreamHandler(stream)
        formatter = logging.Formatter(
            '[ %(levelname)s ] %(asctime)s -  %(message)s'
        )
        handler.setFormatter(formatter)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.addHandler(handler)
        return logger

    @classmethod
    def _init_logger(cls):
        global LOGGER
        if LOGGER is not None:
            return LOGGER

        LOGGER = cls._create_logger(sys.stdout, logging.INFO, name='compose')
        return LOGGER

    @classmethod
    def _init_logger_fs(cls, work_name: str):
        global LOGGER_FS, LOGGER_FS
        if LOGGER_FS is not None:
            return LOGGER_FS

        parent_dir = './outputs/logs'
        filename = f'{parent_dir}/{work_name}.log'

        os.makedirs(parent_dir, mode=0o755, exist_ok=True)
        LOGGER_FS = cls._create_logger(open(filename, 'w'), logging.NOTSET)
        return LOGGER_FS
