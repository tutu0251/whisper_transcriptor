from setuptools import setup, find_packages

        setup(
            name="video-audio-transcriber",
            version="1.0.0",
            author="Your Name",
            description="Transcribe video/audio with local Whisper models",
            long_description=open("README.md").read(),
            long_description_content_type="text/markdown",
            packages=find_packages(),
            install_requires=[line.strip() for line in open("requirements.txt").readlines() if line.strip() and not line.startswith("#")],
            entry_points={"console_scripts": ["transcriber=main:main"]},
            python_requires=">=3.8",
        )
        