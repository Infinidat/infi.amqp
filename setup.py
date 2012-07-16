from setuptools import setup, find_packages
from os import path

verns = {}
with open(path.join(path.dirname(__file__), 'infi', 'amqp', '__version__.py')) as version_file:
    exec version_file.read() in verns
VERSION = verns['__version__']

setup(
    name = 'infi.amqp',
    version = VERSION,
    author = 'Amnon Grossman',
    author_email = 'amnong@gmail.com',

    license = 'BSD',
    description = 'Simple AMQP publisher and consumer',

    # http://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers = [
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
    ],

    namespace_packages = [
        'infi',
        ],
    packages = find_packages(exclude=["tests"]),
    install_requires = [
        'amqplib>=1.0.2',
        ],
    entry_points = dict(
        console_scripts = [
            ],
        ),
    )
