from pathlib import Path
import distutils.dir_util
import os
import subprocess

from hat import gui


DOIT_CONFIG = {'backend': 'sqlite3',
               'verbosity': 2}

root_dir = Path(__file__).parent
os.environ['PYTHONPATH'] = ':'.join([str(root_dir / 'src_py')])


def task_docs():
    """Build docs"""
    def run(args):
        args = args or []
        subprocess.run(['sphinx-build', 'docs', 'build/docs', '-q', *args])
    return {'actions': [run], 'pos_arg': 'args'}


def task_py_test():
    """Run all tests"""
    def run(args):
        args = args or []
        subprocess.run(
            ['python', '-m', 'pytest', '-s', '-p', 'no:cacheprovider', *args],
            cwd='test_pytest', check=True)

    return {'actions': [run], 'pos_arg': 'args'}


def task_js_deps():
    """Install js dependencies"""
    def patch():
        subprocess.run(['patch', '-r', '/dev/null', '--forward', '-p0',
                        '-i', 'node_modules.patch'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    return {'actions': ['yarn install --silent']}


def task_js_view():
    """Build js"""
    def run(args):
        gui_path = Path(gui.__file__).parent
        build_path = root_dir / 'build/views/'
        build_path.mkdir(parents=True, exist_ok=True)
        distutils.dir_util.copy_tree(str(gui_path / 'views/login'),
                                     str(build_path / 'login'))
        subprocess.run(
            [str(Path('node_modules/.bin/webpack')),
             '--config', str(root_dir / 'webpack.config.js'), *args])

    return {'actions': [run], 'pos_arg': 'args',
            'task_dep': ['js_deps']}
