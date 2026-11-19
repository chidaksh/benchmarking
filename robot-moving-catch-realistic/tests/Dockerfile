FROM python@sha256:935c3c5b12357a7e10caa9c1e6ca5692344d97cf229832ef584be2cec9fc03df

# Every Python package is pinned, the ones MuJoCo pulls in included.
RUN pip install --no-cache-dir mujoco==4.0.1 mujoco-core==4.0.1 mujoco-studio==4.0.1 mujoco-studio-wasm==4.0.1 \
    numpy==2.5.5 glfw==2.11.0 PyOpenGL==3.1.10 websockets==17.4
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY . /tests/
