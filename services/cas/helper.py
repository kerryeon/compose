from context import *

DEPENDENCY_PROGRAM = 'casadm'


def compose(config: Config, service: Service):
    def get_volume_id(name: str, volume: str):
        return config.command(
            name,
            script=f'ls -al /dev/disk/by-id | grep {volume} | egrep -o \'nvme-[^ ]+\''
        )[0].strip()

    def update_cas_volume(config: Config, name: str, id: int, device: str):
        volume_name = config.command(
            name,
            script=f'sudo casadm -L | egrep \'core[ ]+{id}[ ]+/dev/{device}\' | grep -Po \'/dev/cas[\w-]+\''
        )[0].strip()[5:]
        volume_type = 'cas'

        volume = Volume(volume_name, volume_type)
        config.nodes.volumes(name).append(volume)

        return volume_name

    def mask_volume(name: str, volumes: list, real_volume: str, cas_volume: str):
        for volume in volumes:
            if volume.name == real_volume:
                volume.desc['cas'] = cas_volume
                volume.usable = False
                return
        raise Exception(
            f'Could not find the device: {name} - {real_volume}')

    # init
    shutdown(config, service)

    for id, content in enumerate(service.desc, 1):
        # load content
        cache = str(content['cache'])
        devices = [str(d) for d in content['devices']]
        mode = content.get('mode')
        mode = str(mode) if mode is not None else 'wt'

        # convert to uuid
        for name in config.nodes.all():
            content_caches = config.volumes_by_type(name, cache)
            if not content_caches:
                config.logger.info(f'Skipping cache: {name}')
                continue
            if len(content_caches) > 1:
                raise Exception(
                    f'2 or more Cache Devices at once is not supported: {name} - {content_caches}'
                )
            content_cache_name = content_caches[0].name
            content_cache_id = get_volume_id(name, content_cache_name)

            content_devices = [
                volume for type in devices
                for volume in config.volumes_by_type(name, type)
                if volume.usable
            ]
            if not content_devices:
                config.logger.info(f'Skipping cache: {name}')
                continue
            content_devices_ids = [(v.name, get_volume_id(name, v.name))
                                   for v in content_devices]

            # create
            config.logger.info(
                f'Creating OpenCAS Cache Device: {name} - {content_cache_id}'
            )
            config.command(
                name,
                script=f'sudo casadm -S -i {id} -c {mode} -d /dev/disk/by-id/{content_cache_id} --force'
            )
            for content_device_name, content_device_id in content_devices_ids:
                config.logger.info(
                    f'Creating OpenCAS Core Device: {name} - {content_device_id}'
                )
                config.command(
                    name,
                    script=f'''
                    sudo sgdisk -G /dev/disk/by-id/{content_device_id}
                    echo 'start=2048, type=20' | sudo sfdisk /dev/disk/by-id/{content_device_id}
                    sudo casadm -A -i {id} -d /dev/disk/by-id/{content_device_id}-part1
                    '''
                )

                # mask
                content_cas = update_cas_volume(
                    config, name, id, content_device_name
                )
                mask_volume(name, content_caches,
                            content_cache_name, None)
                mask_volume(name, content_devices,
                            content_device_name, content_cas)
                config.logger.info(
                    f'Created OpenCAS Core Device: {name} - {content_cas}'
                )


def shutdown(config: Config, service: Service):
    config.command_all('sudo casctl stop && sudo casctl init')
