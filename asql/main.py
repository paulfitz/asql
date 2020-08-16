#!/usr/bin/env python

from __future__ import print_function

import argparse

from pygments.cmdline import main as _main
from catsql.main import catsql
import csv
from csvkit.utilities.csvlook import CSVLook
import docker
import json
import os
from pygments import highlight
from pygments.lexers import PythonLexer
from pygments.formatters import TerminalFormatter
import requests
import sqlite3
import sqlparse
import sys
import tempfile
import yaml

models = ['sqlova', 'irnet', 'valuenet']

class AsqlConfig(object):
    def __init__(self):
        self.fname = '_asql.yaml'
        if os.path.exists(self.fname):
            with open(self.fname, 'r') as fin:
                self.config = yaml.safe_load(fin)
        else:
            self.config = {}

    def save(self):
        with open(self.fname, 'w') as fout:
            yaml.dump(self.config, fout)

class Asql(object):
    def __init__(self):
        self.store = AsqlConfig()
        self.config = self.store.config
        self.verbose = False

    def reconfigure(self, args):
        changed = False
        if args.verbose or not args.words:
            self.verbose = True
        self.log('settings stored in {}'.format(self.store.fname))
        if args.db or args.pull:
            reset = False
            for key in ["cached_csv", "table_name"]:
                if key in self.config:
                    del self.config[key]
                    reset = True
            if 'api' in self.config:
                for api in self.config['api'].values():
                    if 'mode' in api:
                        del api['mode']
            if args.db:
                self.config["db"] = args.db[0]
            if not self.config["db"]:
                print('Please specify database to analyze with --db')
                exit(1)
            if "cached" in self.config:
                del self.config["cached"]
                self.log('resetting cache')
            ldb = "_asql.db"
            try:
                os.remove(ldb)
            except:
                pass
            catsql([self.config['db'], '--sqlite', ldb])
            self.config["cached"] = ldb
            self.log('loaded {} to {}'.format(self.config['db'], ldb), True)
            changed = True
        if args.api or args.docker:
            if args.api:
                tag, url = args.api
            else:
                tag = args.docker[0]
                url = self.getUrlFromDocker(tag)
            if 'api' not in self.config:
                self.config['api'] = {}
            self.config['api'][tag] = {
                'tag': tag,
                'url': url
            }
            self.config['tag'] = tag
            self.log('api set to {} and tagged as {}'.format(url, tag), True)
            changed = True
        if changed:
            self.store.save()
        return changed

    def run(self, args):
        self.reconfigure(args)
        if args.words:
            words = args.words
            if len(words) > 0:
                possible_tag = args.words[0]
                if 'api' in self.config:
                    for tag in self.config['api'].keys():
                        if tag == possible_tag:
                            if self.config.get('tag') != tag:
                                self.config['tag'] = tag
                                self.store.save()
                            words = words[1:]
                            break
            self.run_words(words)
        else:
            print("")

    def run_words(self, words):
        config = self.config
        if 'db' not in self.config:
            print('Please specify database to analyze with --db foo.csv, or --db foo.sqlite, or --db postgres://...')
            exit(1)
        if 'api' not in self.config:
            print('Please specify model api with --docker sqlova|valuenet|irnet, or --api tag http://localhost:5050')
            exit(1)
        if 'cached' not in self.config:
            print('Database not cached, please retry')
            exit(1)
        result = None
        service = self.get_service()
        mode = service.get('mode') or 'sqlite'
        fname = config['cached' if mode == 'sqlite' else 'cached_csv']
        with open(fname,'rb') as fin:
            if mode == 'csv':
                files = {mode: ('{}.csv'.format(config['table_name']), fin)}
            else:
                files = {mode: fin}
            data = {'q': ' '.join(words)}
            result = requests.post(service['url'], files=files, data=data)
        j = result.json()
        self.log('response is {}'.format(json.dumps(j)))
        if 'result' in j:
            j = j['result']
        if 'error' in j:
            if j['error'] == 'please include a csv file':
                if mode == 'sqlite':
                    self.rerun_with_csv(words)
                    return
        if 'sql' in j:
            sql = sqlparse.format(j['sql'], reindent=True, keyword_case='upper')
            fout = tempfile.NamedTemporaryFile('wb', delete=False, suffix=".sql")
            fout.write(sql.encode('utf-8'))
            fout.close()
            _main(["_", fout.name])
            if 'params' in j and len(j['params']) > 0:
                code = "  {}".format(json.dumps(j['params']))
                print(highlight(code, PythonLexer(), TerminalFormatter()), end='')
            fout2 = tempfile.NamedTemporaryFile('w', delete=False, suffix=".csv")
            writer = csv.writer(fout2)
            conn = sqlite3.connect(config['cached'])
            params = j.get('params') or []
            try:
                # SQLova setup assumes case insensitivity.
                # Should really mark all the columns, or update the SQL carefully,
                # but instead I just stick COLLATE NOCASE at the end and hope for
                # the best.
                result = conn.execute(sql + ' COLLATE NOCASE', params)
            except:
                result = conn.execute(sql, params)
            writer.writerow([d[0] for d in result.description])
            writer.writerows(result)
            fout2.close()
            try:
                CSVLook(['--no-inference', fout2.name]).run()
            except:
                # CSVLook can fail if a row is blank :(
                with open(fout2.name, 'r') as fin:
                    print(fin.read())
        else:
            print(json.dumps(j, indent=2))

    def rerun_with_csv(self, words):
        self.log("api supports single-table mode only - adapting...")
        csv = '_asql.csv'
        jcsv = '_asql.json'
        catsql([self.config['cached'], '--txt', csv])
        catsql([self.config['cached'], '--json', jcsv])
        with open(jcsv, 'r') as fin:
            table_name = json.load(fin)['meta']['name']
        self.config['cached_csv'] = csv
        self.get_service()['mode'] = 'csv'
        self.config['table_name'] = table_name
        self.store.save()
        self.run_words(words)

    def log(self, txt, force=False):
        if not (self.verbose or force):
            return
        print(highlight("# " + txt, PythonLexer(), TerminalFormatter()), end='')

    def get_service(self):
        tag = self.config['tag']
        return self.config['api'][tag]

    def getUrlFromDocker(self, tag):
        client = docker.from_env()
        result = None
        ports = set()
        for container in client.containers.list():
            try:
                if container.status != 'running':
                    continue
                image_name = container.attrs['Config']['Image']
                port = int(container.attrs['HostConfig']['PortBindings']['5050/tcp'][0]['HostPort'])
                ports.add(port)
                if tag == image_name.split('/')[-1]:
                    result = 'http://localhost:{}'.format(port)
            except Exception as e:
                # Any problems, move on to something recognizable.
                print(e)
                pass
        if result:
            client.close()
            return result
        known_tags = models
        if tag not in known_tags:
            print("tag not recognized:", tag)
            print("try one of:", known_tags)
            client.close()
            exit(1)
        image_name = 'paulfitz/{}'.format(tag)
        name = tag
        for container in client.containers.list(all=True):
            if container.name == name:
                try:
                    container.stop()
                except:
                    pass
                try:
                    container.remove()
                except:
                    pass
        for port in range(5050, 5100):
            if port not in ports:
                break
        self.log("trying to start {} on port {} with docker...".format(image_name, port))
        client.containers.run(image_name, detach=True, name=name,ports={'5050/tcp': port})
        client.close()
        return 'http://localhost:{}'.format(port)

def run(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('words',
                        nargs='*',
                        help='Just a whole bunch of human words.')
    parser.add_argument('--db', nargs=1, required=False, default=None,
                        help='Set database to ask questions from.')
    parser.add_argument('--api', nargs=2, metavar=('TAG', 'URL'), required=False, default=None,
                        help='label and URL for SQLova/ValueNet/IRNet/.... model')
    parser.add_argument('--docker', nargs=1, choices=models, required=False, default=None,
                        help='start or attach to model in docker')
    parser.add_argument('--pull', required=False, action='store_true',
                        help='pull from database to local cache')
    parser.add_argument('--verbose', required=False, action='store_true',
                        help='give details of steps')
    config = parser.parse_args(args)
    asql = Asql()
    asql.run(parser.parse_args(args))
    if len(args) == 0:
        parser.print_help(sys.stderr);
        exit(1)

def main():
    run(sys.argv[1:])
