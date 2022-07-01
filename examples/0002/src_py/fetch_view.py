from hat import gui
from pathlib import Path
import distutils.dir_util


directory = Path(__file__).parents[1] / 'view'

distutils.dir_util.copy_tree(str(Path(gui.__file__).parent / 'views/login'),
                             str(directory / 'login'))
