from setuptools import setup, find_packages

setup(
    name='queuectl',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'click',
        'psycopg2-binary',
    ],
    entry_points={
        'console_scripts': [
            'queuectl = queuectl.cli:cli',
        ],
    },
)