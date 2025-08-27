# movformer-gui

[![License BSD-3](https://img.shields.io/pypi/l/movformer-gui.svg?color=green)](https://github.com/Akseli-Ilmanen/movformer-gui/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/movformer-gui.svg?color=green)](https://pypi.org/project/movformer-gui)
[![Python Version](https://img.shields.io/pypi/pyversions/movformer-gui.svg?color=green)](https://python.org)
[![tests](https://github.com/Akseli-Ilmanen/movformer-gui/workflows/tests/badge.svg)](https://github.com/Akseli-Ilmanen/movformer-gui/actions)
[![codecov](https://codecov.io/gh/Akseli-Ilmanen/movformer-gui/branch/main/graph/badge.svg)](https://codecov.io/gh/Akseli-Ilmanen/movformer-gui)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/movformer-gui)](https://napari-hub.org/plugins/movformer-gui)
[![npe2](https://img.shields.io/badge/plugin-npe2-blue?link=https://napari.org/stable/plugins/index.html)](https://napari.org/stable/plugins/index.html)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json)](https://github.com/copier-org/copier)

A labelling GUI for start and stop times of animal movements. Integrates with MovFormer, a workflow to use action segmentation transformers to predict movement segments.

----------------------------------

This [napari] plugin was generated with [copier] using the [napari-plugin-template].

<!--
Don't miss the full getting started guide to set up your new package:
https://github.com/napari/napari-plugin-template#getting-started

and review the napari docs for plugin developers:
https://napari.org/stable/plugins/index.html
-->

## Installation

You can install `movformer-gui` via [pip]:

```
conda create -n behavformer -c conda-forge movement
```

```
pip install movformer-gui
```

If napari is not already installed, you can install `movformer-gui` with napari and Qt via:

```
pip install "movformer-gui[all]"
```


To install latest development version :

```
pip install git+https://github.com/Akseli-Ilmanen/movformer-gui.git
```

JUST FOR ME: 

```
pip install -e.[all]
pip install pydub audioio thunderhopper
pip install imageio[pyav]
```



## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"movformer-gui" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[copier]: https://copier.readthedocs.io/en/stable/
[@napari]: https://github.com/napari
[MIT]: http://opensource.org/licenses/MIT
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[GNU GPL v3.0]: http://www.gnu.org/licenses/gpl-3.0.txt
[GNU LGPL v3.0]: http://www.gnu.org/licenses/lgpl-3.0.txt
[Apache Software License 2.0]: http://www.apache.org/licenses/LICENSE-2.0
[Mozilla Public License 2.0]: https://www.mozilla.org/media/MPL/2.0/index.txt
[napari-plugin-template]: https://github.com/napari/napari-plugin-template

[file an issue]: https://github.com/Akseli-Ilmanen/movformer-gui/issues

[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/
