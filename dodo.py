import os
import sys
from hat import json
from pathlib import Path
import subprocess


DOIT_CONFIG = {'backend': 'sqlite3',
               'verbosity': 2}

root_dir = Path(__file__).parent
os.environ['PYTHONPATH'] = ':'.join([str(root_dir)])


def task_schemas_json():
    """Build JSON schema repositories"""
    def run():
        repo = json.SchemaRepository(Path('schemas_json/'))
        json.encode_file(repo.to_json(), Path('aimm/json_schema_repo.json'))

    return {'actions': [run]}


def task_test():
    """Run all tests"""
    def run(args):
        args = args or []
        subprocess.run(
            ['python', '-m', 'pytest', '-s', '-p', 'no:cacheprovider', *args],
            cwd='test', check=True)

    return {'actions': [run],
            'pos_arg': 'args',
            'task_dep': ['schemas_json']}


def task_lint():
    """Check linting"""
    def run(args):
        args = args or []
        subprocess.run(
            ['flake8', 'aimm', 'test', 'setup.py', 'dodo.py', *args])
    return {'actions': [run], 'pos_arg': 'args'}


def task_check():
    """Pre-deployment check"""
    return {'actions': [], 'task_dep': ['test', 'lint']}


def task_docs():
    """Build docs"""
    def run(args):
        args = args or []
        subprocess.run(
            ['sphinx-build', 'docs', 'build/docs', '-q', *args])
    return {'actions': [run],
            'pos_arg': 'args',
            'task_dep': ['schemas_json']}


def task_build():
    """Build package"""
    return {'actions': [[sys.executable, 'setup.py', 'build']],
            'task_dep': ['schemas_json']}


def task_dist():
    """Generate dist"""
    return {'actions': [[sys.executable, '-m', 'build']],
            'task_dep': ['build']}
