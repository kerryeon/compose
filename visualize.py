#!/usr/bin/python3

from bs4 import BeautifulSoup
import tarfile


def _find_header(data: list) -> int:
    for index, line in enumerate(data):
        if line.find('cpu') != -1:
            return index


def _parse_header(data: list, index: int):
    fields = []
    num_fields = []

    # first line
    for word in data[index].split('.')[1:]:
        word_strip = word.strip()
        if not word_strip:
            continue
        fields.append((word_strip, []))
        num_fields.append(2 if word == word_strip and word != 'xfer' else 1)

    # second line
    index_field = 1  # skip the first field: Interval
    for word in data[index+1].split(' '):
        if not word:
            continue
        fields[index_field][1].append(word.strip())
        num_fields[index_field] -= 1
        if not num_fields[index_field]:
            index_field += 1

    result = ['rd_name']
    for name, contents in fields:
        for content in contents:
            result.append(f'{name}_{content}')
    return result


def _parse_data(data: list, index: int):
    result = []

    name = None
    values = None
    for line in data[index:]:
        line = line.strip()
        if not line:
            continue
        for word in line.split(' '):
            if not word:
                continue
            if word.startswith('RD='):
                name = word[3:-1]
                if not name.startswith('rd_'):
                    name = None
                break
            if word.startswith('avg_'):
                if not name:
                    break
                values = []
                continue
            if values is not None:
                values.append(word)
        if name and values:
            result.append((name, values))
            name = None
            values = None
    return result


def _print_data(header: list, data: list):
    print(''.join(f'{word:^16}' for word in header))
    for name, content in data:
        print(f'{name:^16}', end='')
        print(''.join(f'{word:^16}' for word in content))


if __name__ == '__main__':
    # load a file
    with tarfile.open('outputs/rook-Y2021M04D12-H01M05S29.tar') as tar:
        data = tar.extractfile('totals.html').read()

    # parse data
    soup = BeautifulSoup(data, 'html.parser')
    data = soup.prettify().split('\n')

    # find header
    header_index = _find_header(data)
    header = _parse_header(data, header_index)

    # find data
    data = _parse_data(data, header_index+2)

    # visualize
    _print_data(header, data)
