from setuptools import setup, find_packages

setup(
    name='locallm',
    version='0.8.0',
    packages=find_packages(),
    install_requires=[
        'rich>=13.0.0',
        'click>=8.0.0',
        'colorama>=0.4.6',
    ],
    entry_points={
        'console_scripts': [
            'locallm=locallm.cli:main',
        ],
    },
    python_requires='>=3.8',
    author='LocalLM',
    description='本地知識庫終端機系統',
)
