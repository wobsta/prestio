# Copyright (C) 2020 André Wobst <project.prestio@wobsta.de>
#
# PyX is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# PyX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with PyX; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA


import base64, json, pathlib, shutil, configparser, os
import click
import requests
from bs4 import BeautifulSoup

class Prestio:

    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
        self.url_map = {}

    def get(self, src):
        r = requests.get(src, headers=self.headers, auth=(self.login, self.password))
        assert r.status_code == 200, r.text
        return json.loads(r.text)

    def post(self, dest, **data):
        r = requests.post(dest, headers=self.headers, json=data, auth=(self.login, self.password))
        assert r.status_code == 201, r.text
        return json.loads(r.text)

    def patch(self, dest, **data):
        r = requests.patch(dest, headers=self.headers, json=data, auth=(self.login, self.password))
        assert r.status_code == 204, r.text

    def dump(self, src, dest):
        data = self.get(src)
        if data['@type'] not in self.cfg:
            click.echo(f'ignore {data["@type"]} at {src}')
            return False
        click.echo(f'fetch {src}')
        dest = dest.joinpath(data['id'])
        dest.mkdir()
        for value_type in ['string', 'boolean', 'list', 'date', 'int', 'richtext', 'image', 'file', 'json', 'title_list', 'title_string', 'token_list', 'token_string']:
            if value_type in self.cfg['ALL']:
                keys = self.cfg['ALL'][value_type].split()
            else:
                keys = []
            if value_type in self.cfg[data['@type']]:
                for key in self.cfg[data['@type']][value_type].split():
                    if key.startswith('!'):
                        keys.remove(key[1:])
                    else:
                        assert key not in keys, "{key} already in {keys}".format(key=key, keys=keys)
                        keys.append(key)
            for key in keys:
                if key not in data or data[key] is None:
                    click.echo(f'missing key {key} for {data["@type"]} in {data["@id"]}')
                    continue
                if value_type in ['image', 'file']:
                    if value_type == 'image':
                        if not data[key]['content-type'].startswith('image/'):
                            click.echo(f'ignore {value_type} with content type {data[key]["content-type"]} at {src}')
                        suffix = '.' + data[key]['content-type'].split('/', 1)[1]
                    else:
                        if data[key]['content-type'] == 'application/pdf':
                            suffix = '.pdf'
                        elif data[key]['content-type'] == 'application/zip':
                            suffix = '.zip'
                        elif data[key]['content-type'] == 'application/msword' and data['@id'].endswith('.doc'):
                            suffix = '.doc'
                        elif data[key]['content-type'] == 'application/vnd.ms-excel' and data['@id'].endswith('.xls'):
                            suffix = '.xls'
                        elif data[key]['content-type'] == 'application/vnd.ms-powerpoint' and data['@id'].endswith('.ppt'):
                            suffix = '.ppt'
                        elif data[key]['content-type'] == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' and data['@id'].endswith('.docx'):
                            suffix = '.docx'
                        elif data[key]['content-type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' and data['@id'].endswith('.xlsx'):
                            suffix = '.xlsx'
                        elif data[key]['content-type'] == 'application/vnd.openxmlformats-officedocument.presentationml.presentation' and data['@id'].endswith('.pptx'):
                            suffix = '.pptx'
                        elif data[key]['content-type'] == 'text/css':
                            suffix = '.css'
                        else:
                            click.echo(f'ignore {value_type} with content type {data[key]["content-type"]} at {src}')
                            return False
                    r = requests.get(data[key]['download'], auth=(self.login, self.password))
                    assert r.status_code == 200, r.text
                    dest.joinpath('@' + key + suffix).open('wb').write(r.content)
                    if data['@type'] == 'Image':
                        json.dump(data['image']['scales'], dest.joinpath('@scales').open('w'))
                elif value_type == 'list':
                    if data[key]:
                        dest.joinpath('@' + key).open('w').write('\n'.join(data[key]))
                elif value_type == 'title_list':
                    if data[key]:
                        dest.joinpath('@' + key).open('w').write('\n'.join(value['title'] for value in data[key]))
                elif value_type == 'token_list':
                    if data[key]:
                        dest.joinpath('@' + key).open('w').write('\n'.join(value['token'] for value in data[key]))
                elif value_type == 'json':
                    if data[key]:
                        json.dump(data[key], dest.joinpath('@' + key + '.json').open('w'), sort_keys=True, indent=2)
                elif value_type == 'richtext':
                    if data[key]['content-type'] != 'text/html':
                        click.echo(f'rich text content for {key} with non-text/html content type {data[key]["content-type"]} at {src}')
                    dest.joinpath('@' + key).open('w').write(data[key]['data'])
                else:
                    assert value_type in ['string', 'boolean', 'date', 'int', 'title_string', 'token_string'], value_type
                    value = data[key]
                    if value_type in ['boolean', 'date', 'int']:
                        value = str(value)
                    elif value_type == 'title_string':
                        value = value['title']
                    elif value_type == 'token_string':
                        value = value['token']
                    if value:
                        assert isinstance(value, str), "invalid value {value} of type {value_type} for key {key} in {src_id}".format(key=key, value=value, value_type=type(value), src_id=data['@id'])
                        dest.joinpath('@' + key).open('w').write(value)
        sharing_data = json.dumps(self.get(src + '/@sharing'), sort_keys=True, indent=2)
        if data['@type'] != 'Plone Site':
            parent_sharing_data = json.dumps(self.get(data['parent']['@id'] + '/@sharing'), sort_keys=True, indent=2)
        else:
            parent_sharing_data = ''
        if sharing_data != parent_sharing_data:
            dest.joinpath('@sharing.json').open('w').write(sharing_data)
        if data['is_folderish']:
            items = []
            items_total = data['items_total']
            while items_total:
                for item in data['items']:
                    assert item['@id'].startswith(data['@id'])
                    items_total -= 1
                    if self.dump(item['@id'], dest):
                        items.append(item['@id'][len(data['@id'])+1:])
                if items_total:
                    data = self.get(data['batching']['next'])
            json.dump(items, dest.joinpath('@items').open('w'))
        return True

    def load(self, src, dest):
        data = {item.name[1:]: item.open('rb' if item.name.startswith('@file.') or item.name.startswith('@image.') else 'r').read() for item in src.glob('@*')}
        data['id'] = src.name
        old_url = data['@id']
        del data['@id']
        if data['@type'] == 'Image':
            scales = json.loads(data.pop('scales'))
        if data['@type'] == 'Folder':
            items = json.loads(data['items'])
            del data['items']
            data = self.post(dest, **data)
            dest += '/' + data['id']
            self.url_map[old_url] = 'resolveuid/%s' % data['UID']
            for item in items:
                self.load(src.joinpath(item), dest)
        else:
            click.echo('upload backup %s (%d bytes)' % (src, len(data['text']) if data['@type'] == 'Document' else len(data[data['@type'].lower()+src.suffix])))
            if data['@type'] == 'Document':
                data['text'] = {'data': data['text'], 'content-type': 'text/html'}
                if 'text_en' in data:
                    # dpg specific (bilingual)
                    data['text_en'] = {'data': data['text_en'], 'content-type': 'text/html'}
            elif data['@type'] in ['File', 'Image']:
                data[data['@type'].lower()] = {'data': base64.b64encode(data[data['@type'].lower()+src.suffix]).decode('ascii'), 'encoding': 'base64', 'content-type': {'.pdf': 'application/pdf', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png'}[src.suffix]}
                del data[data['@type'].lower()+src.suffix]
            else:
                click.echo('invalid/unknown type')
                data = None
            if data:
                data = self.post(dest, **data)
                self.url_map[old_url] = 'resolveuid/%s' % data['UID']
                if data['@type'] == 'Image':
                    for key, value in scales.items():
                        self.url_map[value['download']] = 'resolveuid/%s/@@images/image/%s' % (data['UID'], key)

    def fixlinks(self, url):
        def process_html(html):
            if html == '':
                return html
            soup = BeautifulSoup(html, 'lxml')
            for tag in soup.findAll(href=True):
                assert tag.name == 'a'
                if tag['href'] in self.url_map:
                    click.echo(f'replace href {tag["href"]} by {self.url_map[tag["href"]]}')
                    tag['href'] = self.url_map[tag['href']]
                else:
                    click.echo(f'not alter href {tag["href"]}')
            for tag in soup.findAll(src=True):
                assert tag.name == 'img'
                if tag['src'] in self.url_map:
                    if tag.parent.name == 'a': # skip uncaptioned images from alternation
                        assert tag.parent.name == 'a'
                        assert tag.parent.parent.name == 'dt'
                        assert tag.parent.parent.parent.name == 'dl'
                        click.echo(f'replace rendered captioned img {tag["src"]} by {self.url_map[tag["src"]]}')
                        p = soup.new_tag('p')
                        tag.parent.parent.parent.replaceWith(p)
                        img = soup.new_tag('img', src=self.url_map[tag['src']])
                        img['class'] = ['image-inline', 'captioned']
                        p.append(img)
                    else:
                        click.echo(f'replace img uncaptioned src {tag["src"]} by {self.url_map[tag["src"]]}')
                        tag['src'] = self.url_map[tag['src']]
                else:
                    click.echo(f'not alter src {tag["src"]}')
            html = str(soup)
            assert html.startswith('<html><body>'), html
            assert html.endswith('</body></html>'), html
            return str(html[12:-14])
        data = self.get(url)
        if data['@type'] == 'Folder':
            for item in data['items']:
                assert item['@id'].startswith(data['@id'])
                self.fixlinks(item['@id'])
        elif data['@type'] == 'Document':
            click.echo(f'fix links {url}')
            if 'text_en' in data:
                # dpg specific (bilingual)
                self.patch(url, text={'data': process_html(data['text']['data']), 'content-type': 'text/html'},
                                text_en={'data': process_html(data['text_en']['data']), 'content-type': 'text/html'})
            else:
                self.patch(url, text={'data': process_html(data['text']['data']), 'content-type': 'text/html'})


@click.group()
@click.option('--login', default='admin')
@click.option('--password', required=True)
@click.pass_context
def cli(ctx, login, password):
    ctx.obj['login'] = login
    ctx.obj['password'] = password


@cli.command(name='load')
@click.argument('sources', nargs=-1)
@click.argument('dest', nargs=1)
@click.pass_context
def cli_load(ctx, sources, dest):
    prestio = Prestio(**ctx.obj)
    for source in sources:
        prestio.load(pathlib.Path(source), dest)
    for source in sources:
        prestio.fixlinks(dest + '/' + source)


@cli.command(name='dump')
@click.option('--config', type=click.File(), default=os.path.join(os.path.dirname(__file__), 'prestio.cfg'))
@click.argument('sources', nargs=-1)
@click.argument('dest', nargs=1)
@click.pass_context
def cli_dump(ctx, config, sources, dest):
    prestio = Prestio(**ctx.obj)
    prestio.cfg = configparser.ConfigParser()
    prestio.cfg.read_file(config)
    for source in sources:
        prestio.dump(source, pathlib.Path(dest))


def entry():
    cli(obj={})


if __name__ == '__main__':
    cli(obj={})
