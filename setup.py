"""
Distributed under the terms of the BSD 3-Clause License.

The full license is in the file LICENSE, distributed with this software.

Author: Jun Zhu <jun.zhu@xfel.eu>
Copyright (C) European X-Ray Free-Electron Laser Facility GmbH.
All rights reserved.
"""
import contextlib
import os
import os.path as osp
import re
import shutil
import sys
import sysconfig
import subprocess
from setuptools import setup, find_packages, Distribution, Extension
from setuptools.command.build_ext import build_ext
from setuptools.command.test import test as _TestCommand
from distutils.command.clean import clean
from distutils.version import LooseVersion
from distutils.util import strtobool


with open(osp.join(osp.abspath(osp.dirname(__file__)), 'README.md')) as f:
    long_description = f.read()


def find_version():
    with open(osp.join('extra_foam', '__init__.py')) as fp:
        for line in fp:
            m = re.search(r'^__version__ = "(\d+\.\d+\.\d[a-z]*\d*)"', line, re.M)
            if m is not None:
                return m.group(1)
        raise RuntimeError("Unable to find version string.")


@contextlib.contextmanager
def changed_cwd(dirname):
    oldcwd = os.getcwd()
    os.chdir(dirname)
    try:
        yield
    finally:
        os.chdir(oldcwd)


class CMakeExtension(Extension):
    def __init__(self, name, source_dir=''):
        super().__init__(name, sources=[])
        self.source_dir = os.path.abspath(source_dir)


ext_modules = [
    CMakeExtension("extra_foam"),
]


class BuildExt(build_ext):

    _thirdparty_files = [
        "extra_foam/thirdparty/bin/redis-server",
        "extra_foam/thirdparty/bin/redis-cli"
    ]

    description = "Build the C++ extensions for EXtra-foam"
    user_options = [
        ('with-tbb', None, 'build with intel TBB'),
        ('xtensor-with-tbb', None, 'build xtensor with intel TBB'),
        # https://quantstack.net/xsimd.html
        ('with-xsimd', None, 'build with XSIMD'),
        ('xtensor-with-xsimd', None, 'build xtensor with XSIMD'),
        ('with-tests', None, 'build cpp unittests'),
    ] + build_ext.user_options

    def initialize_options(self):
        super().initialize_options()

        self.with_tbb = strtobool(os.environ.get('FOAM_WITH_TBB', '1'))
        self.xtensor_with_tbb = strtobool(os.environ.get('XTENSOR_WITH_TBB', '1'))
        self.with_xsimd = strtobool(os.environ.get('FOAM_WITH_XSIMD', '1'))
        self.xtensor_with_xsimd = strtobool(os.environ.get('XTENSOR_WITH_XSIMD', '1'))
        self.with_tests = strtobool(os.environ.get('FAI_WITH_TESTS', '0'))

    def run(self):
        try:
            out = subprocess.check_output(['cmake', '--version'])
        except OSError:
            raise RuntimeError("CMake must be installed to build the "
                               "following extensions: " + ", ".join(
                e.name for e in self.extensions))

        cmake_version = LooseVersion(
            re.search(r'version\s*([\d.]+)', out.decode()).group(1))
        if cmake_version < '3.8.0':
            raise RuntimeError("CMake >= 3.8.0 is required!")

        # build third-party libraries, for example, Redis
        command = ["./build.sh", "-p", sys.executable]
        subprocess.check_call(command)
        for filename in self._thirdparty_files:
            self._move_file(filename)

        for ext in self.extensions:
            self.build_cmake(ext)

    def build_cmake(self, ext):
        ext_dir = osp.abspath(osp.dirname(self.get_ext_fullpath(ext.name)))
        build_type = 'debug' if self.debug else 'release'

        cmake_options = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={osp.join(ext_dir, 'extra_foam/cpp')}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            f"-DCMAKE_BUILD_TYPE={build_type}",
        ]

        if self.with_tbb:
            cmake_options.append('-DFOAM_WITH_TBB=ON')
        else:
            # necessary to switch from ON to OFF
            cmake_options.append('-DFOAM_WITH_TBB=OFF')

        if self.xtensor_with_tbb:
            # cmake option in thirdparty/xtensor
            cmake_options.append('-DXTENSOR_USE_TBB=ON')
        else:
            cmake_options.append('-DXTENSOR_USE_TBB=OFF')

        if self.with_xsimd:
            cmake_options.append('-DFOAM_WITH_XSIMD=ON')
        else:
            cmake_options.append('-DFOAM_WITH_XSIMD=OFF')

        if self.xtensor_with_xsimd:
            # cmake option in thirdparty/xtensor
            cmake_options.append('-DXTENSOR_USE_XSIMD=ON')
        else:
            cmake_options.append('-DXTENSOR_USE_XSIMD=OFF')

        if self.with_tests:
            cmake_options.append('-DBUILD_FOAM_TESTS=ON')
        else:
            cmake_options.append('-DBUILD_FOAM_TESTS=OFF')

        build_options = ['--', '-j4']

        if not os.path.exists(self.build_temp):
            os.makedirs(self.build_temp)

        with changed_cwd(self.build_temp):
            # generate build files
            print("-- Running cmake for extra-foam")
            self.spawn(['cmake', ext.source_dir] + cmake_options)
            print("-- Finished cmake for extra-foam")

            # build
            print("-- Running cmake --build for extra-foam")
            self.spawn(['cmake', '--build', '.'] + build_options)
            print("-- Finished cmake --build for extra-foam")

    def _move_file(self, filename):
        """Move file to the system folder."""
        src = filename
        dst = os.path.join(self.build_lib, filename)

        parent_directory = os.path.dirname(dst)
        if not os.path.exists(parent_directory):
            os.makedirs(parent_directory)

        if not os.path.exists(dst):
            self.announce(f"copy {src} to {dst}", level=1)
            shutil.copy(src, dst)


class TestCommand(_TestCommand):
    def _get_build_dir(self, dirname):
        version = sys.version_info
        return f"{dirname}.{sysconfig.get_platform()}-{version[0]}.{version[1]}"

    def run(self):
        # build and run cpp test
        build_temp = osp.join('build', self._get_build_dir('temp'))
        with changed_cwd(build_temp):
            self.spawn(['make', 'ftest'])

        # run Python test
        import pytest
        errno = pytest.main(['extra_foam'])
        sys.exit(errno)  # why do we need this?


class BinaryDistribution(Distribution):
    def has_ext_modules(self):
        return True


setup(
    name='EXtra-foam',
    version=find_version(),
    author='Jun Zhu',
    author_email='da-support@xfel.eu',
    description='Online analysis and monitoring tool at European XFEL',
    long_description=long_description,
    url='',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'extra-foam=extra_foam.services:application',
            'extra-foam-kill=extra_foam.services:kill_application',
            'extra-foam-stream=extra_foam.services:stream_file',
            'extra-foam-redis-cli=extra_foam.services:start_redis_client',
            'extra-foam-monitor=extra_foam.web.monitor:web_monitor'
        ],
    },
    ext_modules=ext_modules,
    tests_require=['pytest'],
    cmdclass={
        'clean': clean,
        'build_ext': BuildExt,
        'test': TestCommand,
    },
    distclass=BinaryDistribution,
    package_data={
        'extra_foam': [
            'gui/icons/*.png',
            'gui/icons/*.jpg',
            'geometries/*.h5'
        ]
    },
    install_requires=[
        'numpy>=1.16.1',
        'scipy>=1.2.1',
        'msgpack>=0.5.6',
        'msgpack-numpy>=0.4.4',
        'pyzmq>=17.1.2',
        'pyFAI>=0.15.0',
        'PyQt5>=5.12.0',
        'karabo-data>=0.6.2',
        'karabo-bridge>=0.3.0',
        'toolz>=0.9.0',
        'silx>=0.9.0',
        'hiredis>=1.0.0',
        'redis>=3.3.11',
        'psutil>=5.6.2',
        'imageio>=2.5.0',
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
        ],
        'web': [
            'dash>=1.1.0',
        ],
    },
    python_requires='>=3.6',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
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
