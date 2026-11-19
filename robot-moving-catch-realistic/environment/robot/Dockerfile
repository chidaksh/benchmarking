FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# System packages come from Debian's snapshot archive at a fixed time, so every build installs the same versions.
RUN sed -i -e 's|http://deb.debian.org/debian-security|http://snapshot.debian.org/archive/debian-security/20261116T212321Z|' \
    -e 's|http://deb.debian.org/debian$|http://snapshot.debian.org/archive/debian/20261116T203818Z|' /etc/apt/sources.list.d/debian.sources
# Camera images are rendered on the CPU.
RUN apt-get -o Acquire::Check-Valid-Until=false -o Acquire::Retries=5 update && apt-get install -y --no-install-recommends libosmesa6 libgl1 libglx-mesa0 \
    && rm -rf /var/lib/apt/lists/*
# Every Python package is pinned, the ones MuJoCo pulls in included.
RUN pip install --no-cache-dir mujoco==4.0.1 mujoco-core==4.0.1 mujoco-studio==4.0.1 mujoco-studio-wasm==4.0.1 \
    numpy==2.5.5 glfw==2.11.0 PyOpenGL==3.1.10 websockets==17.4
ENV MUJOCO_GL=osmesa PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /srv
COPY world.py cell.py sensing.py robot_service.py /srv/
# The seed fixes the arrangement of the cell. It exists only in this image.
CMD ["python3", "robot_service.py", "20261119", "/srv/data/robot-record.json", "8000"]
