from setuptools import setup, find_packages

setup(
    name='gvis3d',
    version='1.0.0',
    description='GVis3D - A desktop 3D viewer for GCode files',
    author='Joe Walnes',
    author_email='joe@walnes.com',
    packages=find_packages(),
    install_requires=[
        'PySide6>=6.0.0',
        'PyOpenGL>=3.1.0',
        'numpy>=1.20.0',
    ],
    entry_points={
        'console_scripts': [
            'gvis3d=main:main',
        ],
    },
    include_package_data=True,
    zip_safe=False,
)