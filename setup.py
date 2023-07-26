import os

from setuptools import setup

required_modules = []
linked_dependencies = []

try:
    # Use requirements.txt to build dependencies
    # We use this to make developers live easy :)
    with open(os.path.join(os.path.dirname(__file__), 'requirements.txt'), 'r') as file:
        requirements = file.readlines()

    # split dependencies from standard modules and git+...
    for p in requirements:
        if p.startswith("git+"):
            linked_dependencies.append(p)
            print(
                f"Warning: dependency_links for {p} may not work. Check https://peps.python.org/pep-0440/#direct-references")
        elif p.startswith("--index-url"):
            pass  # linked_dependencies.append(p[12:-1])
        elif p.startswith("--extra-index-url"):
            pass  # linked_dependencies.append(p[12:-1])
        elif p.startswith("#"):
            pass
        else:
            required_modules.append(p)
except:
    print(f"Warning, some goes wrong when trying to process 'requirements.txt' @ {os.path.dirname(__file__)}")

setup(
    install_requires=required_modules,
    dependency_links=linked_dependencies,
)
