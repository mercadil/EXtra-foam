import os
import re
from setuptools import setup, find_packages


def find_version():
    with open(os.path.join('karaboFAI', '__init__.py')) as fp:
        for line in fp:
            m = re.search(r'__version__ = "(\d+\.\d+\.\d+[a-z]?\d+)"', line, re.M)
            if m is not None:
                return m.group(1)
        raise RuntimeError("Unable to find version string.")


setup(
    name='karaboFAI',
    version=find_version(),
    author='Jun Zhu',
    author_email='cas-support@xfel.eu',
    description='Azimuthal integration tool',
    long_description='Offline and online data analysis and visualization tool '
                     'for azimuthal integration of different data acquired '
                     'with various detectors at European XFEL.',
    url='',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'karaboFAI=karaboFAI.main_fai_gui:start',
            'karaboBDP=karaboFAI.main_bdp_gui:main_bdp_gui'
        ],
    },
    package_data={
        'karaboFAI': [
            'icons/*.png',
            'windows/icons/*.png'
        ]
    },
    install_requires=[
        'numpy>=1.16.1',
        'scipy>=1.1.0',
        'msgpack>=0.5.6',
        'msgpack-numpy>=0.4.4',
        'pyzmq>=17.1.2',
        'pyFAI>=0.17.0',
        'PyQt5>=5.12.0',
        'karabo-data>=0.2.0',
        'karabo-bridge>=0.2.0',
        'toolz',
        'silx>=0.9.0',
    ],
    extras_require={
        'docs': [
          'sphinx',
          'nbsphinx',
          'ipython',  # For nbsphinx syntax highlighting
        ],
        'test': [
          'pytest',
          'pytest-cov',
        ]
    },
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Scientific/Engineering :: Information Analysis',
        'Topic :: Scientific/Engineering :: Physics',
    ]
)
