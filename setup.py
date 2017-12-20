
from setuptools import setup


info = {}
try:
    next = next
except NameError:
    def next(i):
        return i.next()
src = open("filelike/__init__.py")
lines = []
ln = next(src)
while "__version__" not in ln:
    lines.append(ln)
    ln = next(src)
while "__version__" in ln:
    lines.append(ln)
    ln = next(src)
exec("".join(lines),info)


NAME = "filelike"
VERSION = info["__version__"]
DESCRIPTION = "Classes for creating and wrapping file-like objects"
AUTHOR = "Ryan Kelly"
AUTHOR_EMAIL = "ryan@rfk.id.au"
URL = "http://www.rfk.id.au/software/filelike/"
LICENSE = "LGPL"
KEYWORDS = "file filelike file-like filter crypt compress"
LONG_DESC = info["__doc__"]


PACKAGES = [
    "filelike",
    "filelike.pipeline",
    "filelike.wrappers",
    "filelike.wrappers.tests",
]
EXT_MODULES = []
PKG_DATA = {}


setup(
    name=NAME,
    version=VERSION,
    author=AUTHOR,
    author_email=AUTHOR_EMAIL,
    url=URL,
    description=DESCRIPTION,
    long_description=LONG_DESC,
    keywords=KEYWORDS,
    packages=PACKAGES,
    ext_modules=EXT_MODULES,
    package_data=PKG_DATA,
    license=LICENSE,
    test_suite="filelike.tests.build_test_suite",
    tests_require=["PyCrypto"],
    use_2to3=True,
)

