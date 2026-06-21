"""Package setup for AI Study Buddy."""
from setuptools import find_packages, setup

setup(
    name="ai-study-buddy",
    version="0.2.0",
    description="AI-Powered Study Assistant - Multi-model, geometry drawing, vision support",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    author="Kai / Liminal0426",
    url="https://github.com/Liminal0426/ai-study-buddy",
    license="MIT",
    python_requires=">=3.8",
    packages=find_packages(),
    install_requires=[
        "requests",
        "python-dotenv",
        "Pillow",
        "matplotlib",
        "numpy",
    ],
    entry_points={
        "console_scripts": [
            "study-buddy=study_buddy.__main__:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Education",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Education",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="study, assistant, ai, geometry, drawing, education, problem-solver",
)
