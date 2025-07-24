# napari-label-manager

[![License BSD-3](https://img.shields.io/pypi/l/napari-label-manager.svg?color=green)](https://github.com/Wenlab/napari-label-manager/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-label-manager.svg?color=green)](https://pypi.org/project/napari-label-manager)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-label-manager.svg?color=green)](https://python.org)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/napari-label-manager)](https://napari-hub.org/plugins/napari-label-manager)
[![npe2](https://img.shields.io/badge/plugin-npe2-blue?link=https://napari.org/stable/plugins/index.html)](https://napari.org/stable/plugins/index.html)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-inverted-border-purple.json)](https://github.com/copier-org/copier)

----------------------------------

This [napari] plugin was generated with [copier] using the [napari-plugin-template].

<!--
Don't miss the full getting started guide to set up your new package:
https://github.com/napari/napari-plugin-template#getting-started

and review the napari docs for plugin developers:
https://napari.org/stable/plugins/index.html
-->
## Description
This is a plugin for management of label colormap generation and opacity control.
- Select your label layer from the dropdown
- Generate a new colormap or use existing colors
- Specify target label IDs (e.g., "1-5,10,15-20")
- Adjust opacity for selected labels and background
- Apply changes to visualize your selection

## Features

### Label Management
- Batch management of label colors and opacity
- Random colormap generation with customizable seeds
- Support for label ID ranges and individual selections
- Quick presets for common label selections (first 10, even/odd IDs, all current)

### Label Annotation
- **NEW**: Excel-like annotation table for labeling digital IDs
- Fill ranges of label IDs automatically
- Load current layer's labels into annotation table
- Add custom annotations/descriptions for each label
- Export annotations to Excel format (.xlsx)

### Performance Optimizations
- Memory-efficient processing for large datasets
- Time-series optimization (processes current slice only)
- Smart sampling strategies for extremely large arrays
- Background computation to maintain UI responsiveness

## Installation

You can install `napari-label-manager` via [pip]:

```
pip install napari-label-manager
```

If napari is not already installed, you can install `napari-label-manager` with napari and Qt via:

```
pip install "napari-label-manager[all]"
```

### For Excel Export and Load Functionality

To enable Excel export features for label annotations, install the optional and pandas dependency:

```
pip install openpyxl pandas
```

Or install everything together:

```
pip install napari-label-manager openpyxl pandas
```



## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"napari-label-manager" is free and open source software

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

[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/
