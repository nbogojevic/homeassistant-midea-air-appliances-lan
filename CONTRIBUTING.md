# Contribution guidelines

Contributing to this project should be as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features

## Github is used for everything

Github is used to host code, to track issues and feature requests, as well as accept pull requests.

Pull requests are the best way to propose changes to the codebase.

1. Fork the repo and create your branch from `main`.
2. If you've changed something, update the documentation.
3. Make sure your code lints (using [black](https://pypi.org/project/black/) and [flake8](https://pypi.org/project/flake8/)).
4. Test you contribution.
5. Issue that pull request!

## Any contributions you make will be under the MIT Software License

In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using Github's [issues](../../issues)

GitHub issues are used to track public bugs.
Report a bug by [opening a new issue](../../issues/new/choose); it's that easy!

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

People *love* thorough bug reports.

## Use a Consistent Coding Style

Use [black](https://github.com/ambv/black) to make sure the code follows the style.

Use [flake8](https://pypi.org/project/flake8/) for linting.

## Test your code modification

Home Assistant 2026.11.0 or newer and Python 3.14.2 or newer are required.

Create a virtual environment and install the test dependencies:

```shell
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pytest
```

Tests use the official `pytest-homeassistant` package, which installs the matching
Home Assistant version. Upgrade them together. Do not install
`pytest-homeassistant-custom-component` in the same environment; if migrating an
existing environment, uninstall it before installing the test dependencies.
Custom integrations and shared fixtures are loaded automatically.

CI runs the suite against the minimum supported release (2026.11.0) and the
latest available `pytest-homeassistant` release.

This component comes with development environment in a container, easy to launch
if you use Visual Studio Code. With this container you will have a stand alone
Home Assistant instance running and already configured with the included
[`.devcontainer/configuration.yaml`](./.devcontainer/configuration.yaml)
file.

## License

By contributing, you agree that your contributions will be licensed under its MIT License.
