import paramiko


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
                 volumes: list):
        self.id = id
        self.name = name
        self.username = username
        self.password = password
        self.volumes = volumes

    def node_ip(self, plane: str) -> str:
        return f'{plane}.{self.id}'

    def command(self, logger, plane: str, script: str, env: dict):
        client = paramiko.SSHClient()
        client.load_system_host_keys()
        client.connect(self.node_ip(plane),
                       username=self.username,
                       password=self.password)

        stdin, stdout, stderr = client.exec_command(
            script, get_pty=True, environment=env)
        output = stdout.readlines()
        for line in output:
            logger.debug(line)
        for line in stderr.readlines():
            logger.error(line)
        stdin.close()
        client.close()
        return output

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

    def command(self, logger, name: str, plane: str, script: str, env: dict):
        return self.data[name].command(logger, plane, script, env)

    def workers(self) -> list:
        return [n for n in self.data if n != self.master]

    @classmethod
    def parse(cls, context: dict):
        master = str(context['master'])
        data = {n.name: n for n in [
            Node.parse(n) for n in context['desc']]}
        return Nodes(master, data)


class Planes:
    def __init__(self, data: dict):
        self.data = data

    @property
    def maintain(self) -> str:
        return self.data['maintain']

    @classmethod
    def parse(cls, context: dict):
        data = {str(k): str(v) for k, v in context.items()}
        return Planes(data)


class Service:
    def __init__(self, name: str, version: str):
        self.name = name
        self.version = version

    @classmethod
    def parse(cls, context: dict):
        name = str(context['name'])
        version = str(context['version'])
        return Service(name, version)


class Services:
    def __init__(self, data: dict):
        self.data = data

    def collect_dependencies(self) -> set:
        return set(self.data.keys())

    @classmethod
    def parse(cls, context: dict):
        data = {s.name: s for s in [
            Service.parse(s) for s in context]}
        return Services(data)


class BenchmarkCaseVolumes:
    def __init__(self, cas: str, metadata: str, osds_per_device: int):
        self.cas = cas
        self.metadata = metadata
        self.osds_per_device = osds_per_device

    def collect_dependencies(self) -> set:
        result = set()
        if self.cas is not None:
            result.add('cas')
        return result

    @classmethod
    def parse(cls, context: dict):
        cas = context.get('cas')
        cas = str(cas) if cas else None
        metadata = context.get('metadata')
        metadata = str(metadata) if metadata else None
        osds_per_device = context.get('osdsPerDevice')
        osds_per_device = int(osds_per_device) if osds_per_device else 1
        return BenchmarkCaseVolumes(cas, metadata, osds_per_device)


class BenchmarkCase:
    def __init__(self, nodes: list, volumes: BenchmarkCaseVolumes):
        self.nodes = nodes
        self.volumes = volumes

    def collect_dependencies(self) -> set:
        result = set()
        if self.volumes is not None:
            result.add('rook')
            result = result.union(self.volumes.collect_dependencies())
        return result

    @classmethod
    def parse(cls, context: dict):
        nodes = [str(n) for n in context['nodes']]
        volumes = context['volumes']
        volumes = BenchmarkCaseVolumes.parse(volumes) \
            if volumes is not None else volumes
        return BenchmarkCase(nodes, volumes)


class Benchmark:
    def __init__(self, name: str, cases: list, output: str):
        self.name = name
        self.cases = cases
        self.output = output

    def collect_dependencies(self) -> set:
        result = {self.name}
        for case in self.cases:
            result = result.union(case.collect_dependencies())
        return result

    @classmethod
    def parse(cls, context: dict):
        name = context['name']
        cases = [BenchmarkCase.parse(c) for c in context['cases']]
        output = context.get('output')
        output = str(output) if output is not None else './output'
        return Benchmark(name, cases, output)


class Config:
    def __init__(self, logger, nodes: Nodes, planes: Planes,
                 services: Services, benchmark: Benchmark):
        self.nodes = nodes
        self.planes = planes
        self.services = services
        self.benchmark = benchmark

        self.logger = logger

    def collect_dependencies(self) -> set:
        result = {'kubernetes'}
        result = result.union(self.services.collect_dependencies())
        result = result.union(self.benchmark.collect_dependencies())
        return result

    def command(self, name: str, script: str, **env):
        return self.nodes.command(self.logger, name, self.planes.maintain, script, env)

    def command_master(self, script: str, **env):
        env = {k: str(v) for k, v in env.items()}
        return self.nodes.command(self.logger, self.nodes.master, self.planes.maintain, script, env)

    def command_workers(self, script: str, **env):
        env = {k: str(v) for k, v in env.items()}
        return [(worker, self.nodes.command(self.logger, worker, self.planes.maintain, script, env))
                for worker in self.nodes.workers()]

    def command_all(self, script: str, **env):
        env = {k: str(v) for k, v in env.items()}
        return [(worker, self.nodes.command(self.logger, worker, self.planes.maintain, script, env))
                for worker in self.nodes.data]

    @classmethod
    def parse(cls, context: dict, logger):
        nodes = Nodes.parse(context['nodes'])
        planes = Planes.parse(context['planes'])
        services = Services.parse(context['services'])
        benchmark = Benchmark.parse(context['benchmark'])
        return Config(logger, nodes, planes, services, benchmark)

    @classmethod
    def load(cls, path: str, logger):
        logger.info(f'Loading config: {path}')
        import yaml
        with open(path) as f:
            context = yaml.load(f, Loader=yaml.FullLoader)
        return Config.parse(context, logger)
